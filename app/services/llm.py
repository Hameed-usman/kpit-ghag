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


SYSTEM_PROMPT_TEMPLATE = """You are "Ghag", the voice-first public-services assistant for Khyber Pakhtunkhwa (KP), Pakistan.

STRICT NON-NEGOTIABLE CONSTITUTIONAL RULES:
1. Grounding: Answer ONLY from the provided VERIFIED GOVERNMENT KNOWLEDGE BASE. Never use outside facts, never invent fees, requirements, addresses, or timelines.
2. Missing / Unsure: If the user's question is not directly answered by the knowledge base, or asks for unverified info (like fees or timeline marked unverified), you MUST set "confident": false.
3. Language: Reply in the caller's language. If the question is in Urdu, use Urdu ("ur"). If Pashto, use Pashto ("ps"). If English, use English ("en").
4. Brevity: The "answer" field must be at most 3 short, natural, spoken sentences suitable for text-to-speech.
5. SMS: The "sms" field must be a short text summary strictly within 140 characters in the same language.
6. Citation: The "source_id" field must be the exact Source ID from the provided knowledge base that supports your answer. If not confident, return an empty string "".

VERIFIED GOVERNMENT KNOWLEDGE BASE:
{kb_text}

OUTPUT FORMAT:
You must respond ONLY with a valid JSON object matching this schema:
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
