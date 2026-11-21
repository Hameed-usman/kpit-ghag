"""
Ghag – POST /api/v1/ask router.

Accepts voice or text queries.
Answers strictly from verified KB entries.
Validates source_id in code — forces human handoff if unconfident or source is invalid.
Returns JSON with text, simulated SMS, and base64 TTS audio.

FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.config import settings
from app.schemas import AskResponse, Lang, Outcome
from app.services import kb, llm, logstore, stt, tts

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["ask"])

HANDOFF_MESSAGES: dict[str, str] = {
    "ur": "معذرت، میں اس سوال کا جواب سرکاری دستاویزات سے نہیں دے سکتا۔ براہ کرم اپنے ضلعی ڈی سی آفس یا cfc.kp.gov.pk سے رابطہ کریں۔",
    "ps": "بخښنه غواړم، زه نشم کولی د رسمي اسنادو له مخې د دې پوښتنې ځواب ورکړم. مهرباني وکړئ د خپلې ولسوالۍ DC دفتر یا cfc.kp.gov.pk سره اړیکه ونیسئ۔",
    "en": "I'm sorry, I cannot find verified official information to answer this question. Please contact your local Deputy Commissioner (DC) Office or visit cfc.kp.gov.pk.",
}

HANDOFF_SMS: dict[str, str] = {
    "ur": "معلومات دستیاب نہیں۔ DC آفس یا cfc.kp.gov.pk سے رابطہ کریں۔",
    "ps": "معلومات نشته. DC دفتر یا cfc.kp.gov.pk سره اړیکه ونیسئ.",
    "en": "Info unavailable in verified KB. Contact DC Office or visit cfc.kp.gov.pk.",
}

_ALLOWED_AUDIO_EXTENSIONS = {"wav", "webm", "mp3", "ogg", "m4a", "flac"}


@router.post("/ask", response_model=AskResponse)
async def ask_endpoint(
    request: Request,
    audio: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    lang: Optional[str] = Form(None),
    lang_hint: Optional[str] = Form(None),
) -> AskResponse:
    """
    Core voice/text question-answering endpoint.
    Accepts multipart form-data (audio + optional text/lang) or application/json.
    """
    t0 = time.perf_counter()

    # If client submitted application/json, parse JSON body
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            json_body = await request.json()
            if isinstance(json_body, dict):
                text = text or json_body.get("text") or json_body.get("question")
                lang = lang or json_body.get("lang")
                lang_hint = lang_hint or json_body.get("lang_hint")
        except Exception as e:
            log.warning("Failed to parse JSON body in /ask: %s", e)

    # 1. Validation
    if audio is None and (not text or not text.strip()):
        raise HTTPException(
            status_code=400,
            detail="Neither audio nor text was provided. Please speak or type your question.",
        )

    # Determine effective language hint
    effective_hint: Optional[str] = None
    if lang_hint and lang_hint.lower().strip() != "auto":
        effective_hint = lang_hint.lower().strip()
    elif lang and lang.lower().strip() in ("ur", "ps", "en"):
        effective_hint = lang.lower().strip()

    transcript: str = ""
    detected_lang: str = effective_hint or "en"

    # 2. STT Path
    if audio is not None:
        audio_bytes = await audio.read()
        if len(audio_bytes) > settings.max_audio_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Audio file exceeds maximum allowed size ({settings.max_audio_bytes} bytes).",
            )

        filename = audio.filename or "audio.wav"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext and ext not in _ALLOWED_AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported audio format: '.{ext}'. Supported: {', '.join(_ALLOWED_AUDIO_EXTENSIONS)}",
            )

        try:
            stt_result = await stt.transcribe(audio_bytes, filename=filename, lang_hint=effective_hint)
            transcript = str(stt_result)
            if hasattr(stt_result, "lang") and stt_result.lang in ("ur", "ps", "en"):
                detected_lang = stt_result.lang
        except stt.STTError as exc:
            log.error("STT failed: %s", exc)
            if not settings.demo_mode:
                raise HTTPException(
                    status_code=503,
                    detail="Voice transcription service temporarily unavailable.",
                ) from exc
            transcript = "ڈومیسائل سرٹیفکیٹ کے لیے کیا کرنا ہوگا؟"
            detected_lang = effective_hint or "ur"
    else:
        # Text Path
        transcript = (text or "").strip()
        if detected_lang not in ("ur", "ps", "en"):
            detected_lang = "en"

    # 3. Grounded LLM Generation
    active_kb = kb.get_kb()
    try:
        answer_result = await llm.grounded_answer(
            question=transcript,
            kb=active_kb,
            lang_hint=detected_lang,
        )
    except llm.LLMError as exc:
        log.error("LLM generation failed: %s", exc)
        if not settings.demo_mode:
            raise HTTPException(
                status_code=503,
                detail="Language reasoning service temporarily unavailable.",
            ) from exc
        answer_result = llm._demo_answer(detected_lang)

    # 4. Strict Validation in Code: Never trust the LLM on source_id!
    valid_source = active_kb.source_id_valid(answer_result.source_id)
    is_confident = answer_result.confident and valid_source

    response_lang = answer_result.lang if answer_result.lang in ("ur", "ps", "en") else detected_lang

    # 5. Route to Handoff vs Answered
    if not is_confident:
        if answer_result.confident and not valid_source:
            log.warning(
                "P-2 Violation Intercepted: LLM claimed confidence but provided invalid source_id '%s'. Forcing handoff.",
                answer_result.source_id,
            )
        handoff_answer = HANDOFF_MESSAGES.get(response_lang, HANDOFF_MESSAGES["en"])
        handoff_sms = HANDOFF_SMS.get(response_lang, HANDOFF_SMS["en"])

        # Try TTS for handoff message
        audio_bytes = await tts.synthesize(handoff_answer, lang=response_lang)
        audio_b64 = tts.to_base64_data_uri(audio_bytes) if audio_bytes else None

        # Log query
        logstore.log_query(
            lang=response_lang,
            source_id=None,
            handled="handoff",
            question_text=transcript,
            is_demo=settings.demo_mode,
        )

        latency_ms = max(1, int((time.perf_counter() - t0) * 1000))
        return AskResponse(
            transcript=transcript,
            lang=Lang(response_lang),
            answer=handoff_answer,
            outcome=Outcome.handoff,
            source_id=None,
            source_url=None,
            last_verified=None,
            confident=False,
            handoff_reason="Out of verified government knowledge base scope",
            latency_ms=latency_ms,
            sms_text=handoff_sms,
            audio_b64=audio_b64,
            tts_available=audio_b64 is not None or audio_bytes is not None,
        )

    # 6. Answered Path
    source_url = active_kb.get_source_url(answer_result.source_id)
    last_verified = active_kb.get_last_verified(answer_result.source_id)
    latency_ms = max(1, int((time.perf_counter() - t0) * 1000))

    # Synthesize speech
    mp3_bytes = await tts.synthesize(answer_result.answer, lang=response_lang)
    audio_b64 = tts.to_base64_data_uri(mp3_bytes) if mp3_bytes else None
    tts_available = (mp3_bytes is not None)

    # Log query
    logstore.log_query(
        lang=response_lang,
        source_id=answer_result.source_id,
        handled="answered",
        question_text=transcript,
        is_demo=settings.demo_mode,
    )

    return AskResponse(
        transcript=transcript,
        lang=Lang(response_lang),
        answer=answer_result.answer,
        outcome=Outcome.answered,
        source_id=answer_result.source_id,
        source_url=source_url,
        last_verified=last_verified,
        confident=True,
        handoff_reason=None,
        latency_ms=latency_ms,
        sms_text=answer_result.sms,
        audio_b64=audio_b64,
        tts_available=tts_available,
    )
