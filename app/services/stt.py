"""
Ghag – Speech-to-Text Service.

Transcribes audio using Groq whisper-large-v3, temperature 0, auto-detect language.
Zero PII / audio persistence (Constitution P-4).

FR-2
"""
from __future__ import annotations

import logging
from io import BytesIO
from typing import Optional

from groq import AsyncGroq, APIConnectionError, APIStatusError

from app.config import settings

log = logging.getLogger(__name__)


class STTError(Exception):
    """Base exception for STT failures."""


class STTApiError(STTError):
    """Raised when Groq Whisper API returns an error."""


class STTConnectionError(STTError):
    """Raised when network/connection to Groq Whisper fails."""


class STTText(str):
    """Transcript string that also carries the detected language code."""
    lang: str

    def __new__(cls, text: str, lang: str = "en") -> STTText:
        obj = str.__new__(cls, text)
        obj.lang = lang
        return obj


_LANG_MAP: dict[str, str] = {
    "urdu": "ur",
    "ur": "ur",
    "pashto": "ps",
    "pushto": "ps",
    "ps": "ps",
    "english": "en",
    "en": "en",
}


_WHISPER_PROMPT = (
    "د خیبر پختونخوا ډومیسائل سرټیفیکیټ، پېښور، اسناد، شناختي کارډ، فارم-بی، "
    "خیبر پختونخوا ڈومیسائل سرٹیفکیٹ، DC Office Peshawar Domicile Certificate citizen facilitation requirements."
)


async def transcribe(
    audio_bytes: bytes,
    filename: str = "audio.wav",
    lang_hint: Optional[str] = None,
) -> STTText:
    """
    Transcribe audio_bytes into text using Groq whisper-large-v3.

    Temperature is fixed to 0. If lang_hint is provided and in {'ur', 'ps', 'en'},
    it is passed to Whisper as the target language parameter.
    Logs a warning if the detected language differs from the hint.
    Audio bytes are held only in memory (BytesIO) and never written to disk.
    """
    effective_hint: Optional[str] = None
    if lang_hint and lang_hint.lower().strip() in ("ur", "ps", "en"):
        effective_hint = lang_hint.lower().strip()

    if settings.demo_mode:
        log.info("STT: DEMO_MODE=True, returning demo fixture")
        return STTText("ڈومیسائل سرٹیفکیٹ کے لیے کیا کرنا ہوگا؟", effective_hint or "ur")

    if not audio_bytes:
        raise STTError("Audio buffer is empty")

    log.info("STT: Transcribing %d bytes (%s), lang_hint=%s", len(audio_bytes), filename, effective_hint)
    try:
        client = AsyncGroq(api_key=settings.groq_api_key)
        kwargs = {
            "file": (filename, BytesIO(audio_bytes)),
            "model": settings.groq_stt_model,
            "temperature": 0,
            "response_format": "verbose_json",
            "prompt": _WHISPER_PROMPT,
        }
        if effective_hint:
            kwargs["language"] = effective_hint

        response = await client.audio.transcriptions.create(**kwargs)
        raw_lang: str = getattr(response, "language", "") or ""
        detected_lang = _LANG_MAP.get(raw_lang.lower().strip(), "en")
        text = response.text.strip()

        if effective_hint and detected_lang != effective_hint:
            log.warning(
                "STT discrepancy: Whisper detected '%s', but user hint was '%s'",
                detected_lang,
                effective_hint,
            )

        log.info("STT: Transcribed (%d chars), detected lang: %s", len(text), detected_lang)
        return STTText(text, detected_lang)

    except APIConnectionError as exc:
        log.error("STT connection failure: %s", exc)
        raise STTConnectionError(f"Cannot connect to Groq Whisper: {exc}") from exc
    except APIStatusError as exc:
        log.error("STT API status error %s: %s", exc.status_code, exc.message)
        raise STTApiError(f"Groq Whisper API error ({exc.status_code}): {exc.message}") from exc
    except Exception as exc:
        log.error("STT unexpected error: %s", exc)
        raise STTError(f"Transcription failed: {exc}") from exc
