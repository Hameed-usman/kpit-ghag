"""
Ghag – LLM Service.

Generates strictly grounded answers from the knowledge base using Groq llama-3.3-70b-versatile.
JSON mode, temperature 0, with 1 automatic retry on malformed JSON.
Enforces Constitution P-1, P-2, P-3, P-8.

FR-3, FR-4, FR-5, FR-7
"""
from __future__ import annotations

import json
import logging
from typing import Literal, Optional

from groq import AsyncGroq, APIConnectionError, APIStatusError
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import settings
from app.services.kb import KnowledgeBase

log = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM service failures."""


class LLMApiError(LLMError):
    """Raised when Groq returns an API error."""


class LLMConnectionError(LLMError):
    """Raised when network connection to Groq fails."""


class AnswerResult(BaseModel):
    """Pydantic v2 model representing structured response from LLM."""
    lang: Literal["ur", "ps", "en"] = Field(description="Language code: ur, ps, or en")
    answer: str = Field(description="Spoken answer, maximum 3 short sentences")
    sms: str = Field(description="SMS summary, strictly under 140 characters")
    source_id: str = Field(description="ID of the KB source used to answer")
    confident: bool = Field(description="True if answered from KB, False if unknown/unverified")

    @field_validator("sms")
    @classmethod
    def enforce_sms_limit(cls, v: str) -> str:
        """Enforce Unicode SMS limit of 140 chars."""
        clean = v.strip()
        if len(clean) > 140:
            return clean[:137] + "…"
        return clean


SYSTEM_PROMPT_TEMPLATE = """You are "Ghag", the official voice assistant for the Government of Khyber Pakhtunkhwa Citizen Facilitation Service (1700 Helpline), Pakistan.

YOUR SOLE PURPOSE is to answer citizen questions about the KP Domicile Certificate based on the VERIFIED GOVERNMENT KNOWLEDGE BASE below.

═══════════════════════════════════════════════════
MANDATORY RULES — NEVER VIOLATE THESE:
═══════════════════════════════════════════════════

RULE 1 — ALWAYS ANSWER DOMICILE QUESTIONS WITH CONFIDENCE:
You MUST set "confident": true for ANY question that relates to:
  - Domicile certificate documents / requirements / کاغذات / اسناد
  - Domicile fees / فیس / 500 روپے / payment
  - Domicile application procedure / طریقہ کار / steps / apply
  - Domicile eligibility / اہلیت / criteria / کون بنوا سکتا
  - Domicile processing time / timeline / کتنے دن / 7 days / RTPS
  - Domicile tracking / status / verification / تصدیق
  - DC Office / CFC / application channels / کہاں جمع کرائیں
  - Orphans / minors / special cases related to domicile fees (answer from dom-fees: no exemption exists)
  - Any variation or paraphrase of the above in Urdu, Pashto, or English

RULE 2 — ONLY REFUSE COMPLETELY UNRELATED TOPICS:
Only set "confident": false for questions about services COMPLETELY unrelated to domicile:
  - Driving license, passport, NADRA ID registration (not domicile)
  - Police verification, FIR, court matters
  - Vehicle registration, property tax
  - Medical, education, election queries
  When refusing, still politely inform the citizen to contact the DC Office.

RULE 3 — SOURCE ID IS MANDATORY WHEN CONFIDENT:
When "confident": true, you MUST provide the exact source_id:
  "dom-requirements" → documents, کاغذات, اسناد
  "dom-fees"         → fee, فیس, payment, 500, orphan fee query
  "dom-timeline"     → days, timeline, کتنے دن, 7 days, RTPS
  "dom-procedure"    → how to apply, طریقہ, steps, مراحل
  "dom-eligibility"  → who can apply, اہلیت, criteria
  "dom-tracking"     → track, verify, تصدیق, status
  "dom-channels"     → where to apply, کہاں, DC office, portal
  "dom-authority"    → issuing authority, DC office general
  "dom-important-notes" → important notes, reminders

RULE 4 — LANGUAGE:
  - Urdu question → reply in Urdu, set lang "ur"
  - Pashto question → reply in Pashto, set lang "ps"
  - English question → reply in English, set lang "en"
  - Mixed/unclear → default to Urdu, set lang "ur"

RULE 5 — BREVITY:
  "answer": maximum 3 short, clear, natural spoken sentences (TTS-ready).
  "sms": under 140 characters. Same language as answer.

═══════════════════════════════════════════════════
VERIFIED GOVERNMENT KNOWLEDGE BASE:
═══════════════════════════════════════════════════
{kb_text}

═══════════════════════════════════════════════════
CRITICAL EXAMPLES OF CORRECT BEHAVIOR:
═══════════════════════════════════════════════════
Q: "کیا یتیم بچوں کے لیے ڈومیسائل فیس معاف ہے؟"
→ confident: true, source_id: "dom-fees"
→ Answer: سرکاری ہدایات کے مطابق ڈومیسائل سرٹیفکیٹ کی فیس 500 روپے ہے۔ کسی بھی زمرے کے لیے فی الحال سرکاری فیس معافی کی کوئی دفعہ موجود نہیں ہے۔

Q: "ڈومیسائل کے لیے کون سے کاغذات درکار ہیں؟"
→ confident: true, source_id: "dom-requirements"
→ Answer: ڈومیسائل کے لیے آپ کا شناختی کارڈ، والد کا شناختی کارڈ، 2 تصاویر، بجلی یا گیس کا بل، اور 50 روپے کے اسٹامپ پیپر پر بیان حلفی درکار ہے۔

Q: "What documents do I need for domicile certificate?"
→ confident: true, source_id: "dom-requirements"
→ Answer: You need your CNIC or Form-B, father's CNIC copy, 2 passport photos, a utility bill for residence proof, and an affidavit on Rs. 50 stamp paper.

Q: "How long does it take to get domicile?"
→ confident: true, source_id: "dom-timeline"
→ Answer: Under KP RTPS Act 2014, the DC Office must issue your domicile certificate within 7 working days. If not, you have the right to file an appeal with the KP RTPS Commission.

Q: "What is the passport fee?"
→ confident: false (unrelated to domicile)

═══════════════════════════════════════════════════
OUTPUT FORMAT (respond ONLY with this JSON):
═══════════════════════════════════════════════════
{{
  "lang": "ur" | "ps" | "en",
  "answer": "Spoken answer string (max 3 sentences)",
  "sms": "SMS summary string (max 140 characters)",
  "source_id": "Exact source_id from KB or empty string",
  "confident": true | false
}}"""


def _demo_answer(lang: str) -> AnswerResult:
    """Return offline demo fixture answer."""
    fixtures = {
        "ur": AnswerResult(
            lang="ur",
            answer="آپ خیبرپختونخوا ڈومیسائل سرٹیفکیٹ کے لیے cfc.kp.gov.pk، موبائل ایپ یا ضلعی ڈی سی آفس سے درخواست دے سکتے ہیں۔",
            sms="KP ڈومیسائل: cfc.kp.gov.pk یا ڈی سی آفس سے درخواست دیں۔",
            source_id="dom-channels",
            confident=True,
        ),
        "ps": AnswerResult(
            lang="ps",
            answer="تاسو کولی شئ د ډومیسائل سرټیفیکیټ لپاره د cfc.kp.gov.pk پورټل، موبائل اپلیکیشن یا DC دفتر له لارې غوښتنه وکړئ۔",
            sms="KP ډومیسائل: cfc.kp.gov.pk یا DC دفتر څخه غوښتنه وکړئ۔",
            source_id="dom-channels",
            confident=True,
        ),
        "en": AnswerResult(
            lang="en",
            answer="You can apply for a KP Domicile Certificate through the Citizen Facilitation Portal at cfc.kp.gov.pk, the mobile app, or your district DC office.",
            sms="Apply for KP Domicile at cfc.kp.gov.pk or DC office.",
            source_id="dom-channels",
            confident=True,
        ),
    }
    return fixtures.get(lang, fixtures["en"])


async def grounded_answer(
    question: str,
    kb: KnowledgeBase,
    lang_hint: Optional[str] = None,
) -> AnswerResult:
    """
    Produce a grounded AnswerResult for the given question against the KB.

    Uses Groq llama-3.3-70b-versatile in JSON mode at temperature 0.
    Retries once on malformed JSON or validation errors.
    """
    if settings.demo_mode:
        log.info("LLM: DEMO_MODE=True, returning canned demo answer")
        return _demo_answer(lang_hint or "en")

    kb_text = kb.render_for_prompt()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(kb_text=kb_text)

    client = AsyncGroq(api_key=settings.groq_api_key)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            log.info("LLM: Generating grounded answer (attempt %d/2)", attempt + 1)
            completion = await client.chat.completions.create(
                model=settings.groq_llm_model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content or "{}"
            data = json.loads(content)
            result = AnswerResult.model_validate(data)
            log.info("LLM: Answer generated. confident=%s, source_id=%s, lang=%s",
                     result.confident, result.source_id, result.lang)
            return result

        except (json.JSONDecodeError, ValidationError) as exc:
            log.warning("LLM: JSON/validation error on attempt %d: %s", attempt + 1, exc)
            last_error = exc
            if attempt == 0:
                # Add instruction to strictly adhere to JSON format on retry
                messages.append({"role": "user", "content": "Your previous response was not valid JSON matching the schema. Please output ONLY the exact valid JSON object."})
                continue
        except APIConnectionError as exc:
            log.error("LLM connection error: %s", exc)
            raise LLMConnectionError(f"Cannot connect to Groq LLM: {exc}") from exc
        except APIStatusError as exc:
            log.error("LLM API status error %s: %s", exc.status_code, exc.message)
            raise LLMApiError(f"Groq LLM API error ({exc.status_code}): {exc.message}") from exc
        except Exception as exc:
            log.error("LLM unexpected error: %s", exc)
            raise LLMError(f"LLM generation failed: {exc}") from exc

    log.warning("LLM: Both attempts failed to return valid JSON. Falling back to unconfident handoff.")
    safe_lang: Literal["ur", "ps", "en"] = "en"
    if lang_hint in ("ur", "ps", "en"):
        safe_lang = lang_hint  # type: ignore[assignment]
    return AnswerResult(
        lang=safe_lang,
        answer="I'm sorry, I could not process an authoritative answer for your query.",
        sms="Contact Deputy Commissioner Office or cfc.kp.gov.pk.",
        source_id="",
        confident=False,
    )
