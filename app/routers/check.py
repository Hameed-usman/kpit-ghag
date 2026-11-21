"""
Ghag – POST /api/v1/check router.

Accepts voice or text describing documents possessed by the user.
Maps to checklist strictly via code set-difference and template rendering.
Logs anonymous interaction with CNIC redaction (no audio stored).

FR-8, AC-8
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.config import settings
from app.schemas import CheckRequest, CheckResponse, ChecklistResponse
from app.services import check_service, logstore, stt, tts

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["check"])

_ALLOWED_AUDIO_EXTENSIONS = {"wav", "webm", "mp3", "ogg", "m4a", "flac"}


@router.get("/checklist", response_model=ChecklistResponse)
async def get_checklist() -> ChecklistResponse:
    """
    GET /api/v1/checklist endpoint.
    Returns available: true and list of items if verified in KB,
    or available: false and empty list if checklist is unverified/TODO.
    """
    return check_service.get_checklist_metadata()


@router.post("/check", response_model=CheckResponse)
async def check(
    request: Request,
    audio: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    service: Optional[str] = Form(None),
    lang: Optional[str] = Form(None),
    lang_hint: Optional[str] = Form(None),
) -> CheckResponse:
    """
    POST /api/v1/check endpoint.
    Accepts JSON body or multipart/form-data with optional audio.
    """
    t0 = time.perf_counter()
    heard_text = ""
    effective_hint: Optional[str] = None
    if lang_hint and lang_hint.lower().strip() != "auto":
        effective_hint = lang_hint.lower().strip()
    elif lang and lang.lower().strip() in ("ur", "ps", "en"):
        effective_hint = lang.lower().strip()

    lang_final = effective_hint or "en"

    # Support JSON input if Content-Type is application/json
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body_json = await request.json()
            req = CheckRequest.model_validate(body_json)
            heard_text = req.text or ""
            if req.lang_hint and req.lang_hint.lower().strip() != "auto":
                lang_final = req.lang_hint.lower().strip()
            elif req.lang:
                lang_final = req.lang
        except Exception as exc:  # noqa: BLE001
            log.warning("Malformed JSON in /check: %s", exc)
            raise HTTPException(status_code=422, detail="Malformed JSON body") from exc

    # Audio input path
    if audio is not None:
        audio_bytes = await audio.read()
        if len(audio_bytes) > settings.max_audio_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Audio file exceeds {settings.max_audio_bytes} bytes",
            )
        filename = audio.filename or "audio.wav"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext and ext not in _ALLOWED_AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported audio format: .{ext}",
            )

        try:
            stt_result = await stt.transcribe(audio_bytes, filename=filename, lang_hint=effective_hint)
            heard_text = str(stt_result)
            if hasattr(stt_result, "lang") and stt_result.lang in ("ur", "ps", "en"):
                lang_final = stt_result.lang
        except stt.STTError as exc:
            log.error("STT failed in /check: %s", exc)
            if not settings.demo_mode:
                raise HTTPException(status_code=503, detail="Speech service unavailable") from exc
            heard_text = "I have CNIC and pictures"
            lang_final = effective_hint or "en"
    elif text:
        heard_text = text.strip()

    if not heard_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Neither text nor audio was provided for document check.",
        )

    # Process Document Check
    response = await check_service.process_document_check(
        heard=heard_text,
        lang_hint=lang_final,
    )

    # Attach Glass-Box Explainability Fields (FR-17)
    response.latency_ms = max(1, int((time.perf_counter() - t0) * 1000))
    response.source_url = "https://cfc.kp.gov.pk/"
    response.last_verified = "2026-11-17"
    response.confident = (response.verdict in ("ready", "missing"))
    if response.verdict in ("unavailable", "unsure"):
        response.handoff_reason = "Official checklist unverified or citizen declarations ambiguous"
    else:
        response.handoff_reason = None

    # Synthesize Spoken Audio
    mp3_bytes = await tts.synthesize(response.spoken, lang=response.lang.value)
    response.audio_b64 = tts.to_base64_data_uri(mp3_bytes) if mp3_bytes else None
    response.tts_available = (mp3_bytes is not None)

    # Log query to logstore (PII safe, CNIC redacted)
    logstore.log_query(
        lang=response.lang.value,
        source_id=response.source_id,
        handled=f"check-{response.verdict}",
        question_text=heard_text,
        is_demo=settings.demo_mode,
    )

    return response
