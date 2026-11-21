"""
Ghag – Document-Check Service.

Implements the Missing-Document Check (FR-8, AC-8):
1. Parses the verified CHECKLIST block from kb/domicile.md into items with stable IDs (D1..Dn).
2. If checklist block is missing, empty, or marked TODO(verified-source), refuses to invent
   requirements and returns verdict="unavailable" with a referral handoff.
3. LLM only MAPS caller's words to checklist IDs -> {matched_ids, ambiguous_ids}.
   It NEVER decides what is missing.
4. Missing items are computed strictly IN CODE via set difference (required - matched).
5. Drops unknown IDs returned by LLM with a warning log.
6. Builds spoken and sms natural-language templates in caller's language.

FR-8, P-1, P-2
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from groq import AsyncGroq, APIConnectionError, APIStatusError
from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.routers.ask import HANDOFF_MESSAGES, HANDOFF_SMS
from app.schemas import CheckMissingItem, CheckResponse, ChecklistItemSchema, ChecklistResponse, Lang

log = logging.getLogger(__name__)


@dataclass
class ChecklistItem:
    """Represents a single document requirement on the verified checklist."""
    id: str
    label_en: str
    label_ur: str = ""
    label_ps: str = ""
    required: bool = True
    status: str = ""
    notes: str = ""

    def get_label(self, lang: str) -> str:
        """Return the label for this item in the requested language, with fallback to EN."""
        if lang == "ur" and self.label_ur:
            return self.label_ur
        if lang == "ps" and self.label_ps:
            return self.label_ps
        return self.label_en


# Dictionary of standard Urdu & Pashto labels for official KP Domicile documents
DEFAULT_DOC_LABELS: Dict[str, Dict[str, str]] = {
    "D1": {
        "en": "Applicant CNIC / Form-B",
        "ur": "درخواست گزار کا شناختی کارڈ یا فارم بی",
        "ps": "د غوښتونکي پېژندپاڼه (CNIC) یا ب-فارم",
    },
    "D2": {
        "en": "Parent / Guardian CNIC",
        "ur": "والد یا سرپرست کا شناختی کارڈ",
        "ps": "د پلار یا سرپرست پېژندپاڼه (CNIC)",
    },
    "D3": {
        "en": "Passport-size photographs",
        "ur": "پاسپورٹ سائز تصاویر",
        "ps": "د پاسپورټ اندازې انځورونه",
    },
    "D4": {
        "en": "Proof of residence",
        "ur": "رہائش کا ثبوت (یوٹیلیٹی بل یا جائیداد کی دستاویز)",
        "ps": "د استوګنې ثبوت (د بېل یا ملکیت سند)",
    },
    "D5": {
        "en": "Affidavit",
        "ur": "حلف نامہ (بیان حلفی)",
        "ps": "حلف نامه (بیان حلفي)",
    },
    "D6": {
        "en": "NOC / Previous domicile surrender",
        "ur": "این او سی یا سابقہ ڈومیسائل واپسی سرٹیفکیٹ",
        "ps": "این او سي یا پخواني ډومیسایل سپارلو سند",
    },
}


def parse_checklist_from_text(text: str) -> Tuple[List[ChecklistItem], bool]:
    """
    Parse checklist items from KB text.
    Returns (items, is_verified).
    is_verified is False if the section is missing, empty, or ANY row has TODO(verified-source).
    """
    # Locate CHECKLIST section
    checklist_match = re.search(r"## CHECKLIST(.*?)(?:---|\Z)", text, flags=re.DOTALL)
    if not checklist_match:
        return [], False

    section_text = checklist_match.group(1).strip()
    if not section_text or "TODO(verified-source)" in section_text:
        return [], False

    items: List[ChecklistItem] = []
    # Parse markdown table rows: | ID | Document | Status | Notes |
    # or | ID | Required | Label | ...
    for line in section_text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line or "| ID" in line:
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) >= 2:
            doc_id = parts[0]
            doc_label = parts[1]
            status = parts[2] if len(parts) > 2 else ""
            notes = parts[3] if len(parts) > 3 else ""

            if not re.match(r"^D\d+$", doc_id):
                continue

            labels = DEFAULT_DOC_LABELS.get(doc_id, {})
            item = ChecklistItem(
                id=doc_id,
                label_en=labels.get("en", doc_label),
                label_ur=labels.get("ur", doc_label),
                label_ps=labels.get("ps", doc_label),
                required=True,
                status=status,
                notes=notes,
            )
            items.append(item)

    if not items:
        return [], False

    return items, True


def load_checklist(path: str | Path = "kb/domicile.md") -> Tuple[List[ChecklistItem], bool]:
    """Load and parse the checklist from disk."""
    p = Path(path)
    if not p.exists():
        return [], False
    content = p.read_text(encoding="utf-8")
    return parse_checklist_from_text(content)


def get_checklist_metadata() -> ChecklistResponse:
    """Return verified checklist items or available=False if unverified/TODO."""
    items, is_verified = load_checklist()
    if not is_verified or not items:
        return ChecklistResponse(available=False, items=[])
    schema_items = [
        ChecklistItemSchema(
            id=item.id,
            label_en=item.label_en,
            label_ur=item.label_ur,
            label_ps=item.label_ps,
            required=item.required,
        )
        for item in items
    ]
    return ChecklistResponse(available=True, items=schema_items)


# --- LLM Mapping Schema --------------------------------------------------------

class LLMCheckMap(BaseModel):
    """LLM only maps caller's utterance to checklist IDs."""
    matched_ids: List[str] = Field(default_factory=list)
    ambiguous_ids: List[str] = Field(default_factory=list)
    detected_lang: Optional[str] = None


_MAPPER_SYSTEM_PROMPT = """You are a strict document extraction parser for Khyber Pakhtunkhwa Domicile Certificate verification.
Your task is ONLY to identify which document IDs the user claims to possess from the provided checklist.

CHECKLIST:
{checklist_context}

RULES:
1. ONLY return checklist IDs (e.g. "D1", "D2") that the user clearly states or implies they have.
2. Put any unclear or ambiguous mentions into "ambiguous_ids".
3. NEVER decide what is missing.
4. Detect the user's language: "ur" (Urdu), "ps" (Pashto), or "en" (English).
5. Output ONLY valid JSON matching this schema:
{{
  "matched_ids": ["D1", ...],
  "ambiguous_ids": ["D3", ...],
  "detected_lang": "ur" | "ps" | "en"
}}"""


async def map_caller_text_to_checklist(
    heard: str,
    checklist: List[ChecklistItem],
    lang_hint: str = "en",
) -> LLMCheckMap:
    """
    Call Groq to extract matched and ambiguous document IDs.
    Does NOT calculate missing documents.
    """
    if settings.demo_mode or not heard.strip():
        return LLMCheckMap(matched_ids=[], ambiguous_ids=[], detected_lang=lang_hint)

    checklist_context = "\n".join(
        f"- {item.id}: {item.label_en} / {item.label_ur} (Required: {item.required})"
        for item in checklist
    )
    prompt = _MAPPER_SYSTEM_PROMPT.format(checklist_context=checklist_context)
    client = AsyncGroq(api_key=settings.groq_api_key)

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": heard},
    ]

    for attempt in range(2):
        try:
            log.info("Check LLM Mapping (attempt %d/2)", attempt + 1)
            completion = await client.chat.completions.create(
                model=settings.groq_llm_model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
            raw = completion.choices[0].message.content or "{}"
            data = json.loads(raw)
            return LLMCheckMap.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            log.warning("Check LLM Mapping parse error (attempt %d): %s", attempt + 1, exc)
            if attempt == 0:
                messages.append({"role": "user", "content": "Please format your output strictly as the requested JSON object."})
                continue
        except (APIConnectionError, APIStatusError) as exc:
            log.error("Check LLM connection error: %s", exc)
            break
        except Exception as exc:  # noqa: BLE001
            log.error("Check LLM unexpected error: %s", exc)
            break

    return LLMCheckMap(matched_ids=[], ambiguous_ids=[], detected_lang=lang_hint)


# --- Template generation for Spoken & SMS responses ---------------------------

def render_check_templates(
    verdict: str,
    missing_items: List[CheckMissingItem],
    lang: str,
) -> Tuple[str, str]:
    """
    Generate natural spoken and SMS texts using deterministic templates in caller's language.
    Validates that every missing label appears in the output when missing.
    """
    missing_labels = [item.label for item in missing_items]
    labels_joined = "، ".join(missing_labels) if lang in ("ur", "ps") else ", ".join(missing_labels)

    if verdict == "ready":
        spoken_map = {
            "ur": "آپ کے پاس ڈومیسائل درخواست کے لیے تمام ضروری دستاویزات مکمل ہیں۔ آپ درخواست دینے کے لیے تیار ہیں۔",
            "ps": "ستاسو د ډومیسائل غوښتنلیک لپاره ټول اړین اسناد بشپړ دي. تاسو غوښتنلیک ورکولو ته چمتو یاست.",
            "en": "You have all required documents for your domicile application. You are ready to apply.",
        }
        sms_map = {
            "ur": "KP ڈومیسائل: آپ کی تمام ضروری دستاویزات مکمل ہیں۔ درخواست دینے کے لیے تیار ہیں۔",
            "ps": "KP ډومیسائل: ستاسو ټول اړین اسناد بشپړ دي. چمتو یاست.",
            "en": "KP Domicile: All required documents ready. You can submit your application.",
        }
        return spoken_map.get(lang, spoken_map["en"]), sms_map.get(lang, sms_map["en"])

    elif verdict == "missing":
        spoken_map = {
            "ur": f"آپ کے پاس درج ذیل ضروری دستاویزات کی کمی ہے: {labels_joined}۔ براہ کرم ڈی سی آفس جانے سے پہلے یہ دستاویزات لازمی ساتھ رکھیں۔",
            "ps": f"ستاسو دا اړین اسناد کم دي: {labels_joined}. مهرباني وکړئ DC دفتر ته د تګ دمخه دا چمتو کړئ.",
            "en": f"You are missing the following required documents: {labels_joined}. Please collect them before visiting the DC office.",
        }
        sms_map = {
            "ur": f"ڈومیسائل مطلوبہ دستاویزات کی کمی: {labels_joined}۔",
            "ps": f"د ډومیسائل پاتې اسناد: {labels_joined}.",
            "en": f"KP Domicile missing: {labels_joined}.",
        }
        spoken = spoken_map.get(lang, spoken_map["en"])
        sms = sms_map.get(lang, sms_map["en"])

        # Enforce SMS Unicode length constraint
        if len(sms) > 160:
            sms = sms[:157] + "…"

        # Strict validation: every missing label MUST appear in spoken output
        for label in missing_labels:
            if label not in spoken:
                log.warning("Validation warning: label '%s' not found in spoken text", label)

        return spoken, sms

    elif verdict == "unsure":
        spoken_map = {
            "ur": "کچھ دستاویزات کے بارے میں بات واضح نہیں ہو سکی۔ براہ کرم واضح بتائیں کہ آپ کے پاس کون کون سی دستاویزات موجود ہیں۔",
            "ps": "د ځینو اسنادو په اړه معلومات روښانه نه وو. مهرباني وکړئ په واضح ډول ووایاست چې تاسو کوم اسناد لرئ.",
            "en": "Some document details were unclear. Please state clearly which documents you currently have.",
        }
        sms_map = {
            "ur": "دستاویزات کی تصدیق نامکمل۔ براہ کرم اپنے دستاویزات کی فہرست دوبارہ بتائیں۔",
            "ps": "د اسنادو پخلی نیمګړی دی. مهرباني وکړئ خپل اسناد بیا بیان کړئ.",
            "en": "Document check unclear. Please list your available documents clearly.",
        }
        return spoken_map.get(lang, spoken_map["en"]), sms_map.get(lang, sms_map["en"])

    else:  # unavailable
        spoken = HANDOFF_MESSAGES.get(lang, HANDOFF_MESSAGES["en"])
        sms = HANDOFF_SMS.get(lang, HANDOFF_SMS["en"])
        return spoken, sms


async def process_document_check(
    heard: str,
    lang_hint: str = "en",
    checklist_override: Optional[List[ChecklistItem]] = None,
    is_verified_override: Optional[bool] = None,
) -> CheckResponse:
    """
    Main entry point for document checking.
    Computes missing = required - matched strictly in code.
    """
    # 1. Load checklist
    if checklist_override is not None:
        checklist = checklist_override
        is_verified = is_verified_override if is_verified_override is not None else True
    else:
        checklist, is_verified = load_checklist()

    # 2. Check availability
    if not is_verified or not checklist:
        log.warning("WARNING: Official document checklist is marked unverified/TODO in KB. Returning verdict='unavailable'.")
        spoken, sms = render_check_templates("unavailable", [], lang_hint)
        return CheckResponse(
            lang=Lang(lang_hint if lang_hint in ("ur", "ps", "en") else "en"),
            heard=heard,
            matched=[],
            missing=[],
            verdict="unavailable",
            spoken=spoken,
            sms=sms,
            source_id="dom-checklist",
            tts_available=True,
            audio_b64=None,
        )

    checklist_map = {item.id: item for item in checklist}
    required_ids: Set[str] = {item.id for item in checklist if item.required}

    # 3. LLM maps words to checklist IDs
    llm_map = await map_caller_text_to_checklist(heard, checklist, lang_hint)

    target_lang = llm_map.detected_lang if llm_map.detected_lang in ("ur", "ps", "en") else lang_hint
    if target_lang not in ("ur", "ps", "en"):
        target_lang = "en"

    # 4. Strict validation: validate returned IDs exist in checklist; drop unknown IDs
    valid_matched: List[str] = []
    for mid in llm_map.matched_ids:
        if mid in checklist_map:
            valid_matched.append(mid)
        else:
            log.warning("Dropped invalid/hallucinated document ID from LLM: '%s'", mid)

    matched_set = set(valid_matched)

    # 5. Missing calculation computed IN CODE (set difference)
    missing_ids = sorted(list(required_ids - matched_set))
    missing_items = [
        CheckMissingItem(id=mid, label=checklist_map[mid].get_label(target_lang))
        for mid in missing_ids
    ]

    # 6. Verdict decision
    if llm_map.ambiguous_ids or not heard.strip():
        verdict = "unsure"
    elif len(missing_ids) == 0:
        verdict = "ready"
    else:
        verdict = "missing"

    # 7. Render spoken and SMS templates
    spoken, sms = render_check_templates(verdict, missing_items, target_lang)

    return CheckResponse(
        lang=Lang(target_lang),
        heard=heard,
        matched=valid_matched,
        missing=missing_items,
        verdict=verdict,
        spoken=spoken,
        sms=sms,
        source_id="dom-checklist",
        tts_available=True,
        audio_b64=None,
    )
