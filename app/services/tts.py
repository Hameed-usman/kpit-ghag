"""
Ghag – Text-to-Speech Service.

Synthesizes voice replies using edge-tts.
Voices:
- ur: ur-PK-UzmaNeural
- ps: ps-AF-LatifaNeural
- en: en-US-JennyNeural

Constitution P-7: If TTS fails, return null audio, never crash the text response.
FR-6
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Dict, Optional

import edge_tts

from app.config import settings

log = logging.getLogger(__name__)


FALLBACK_VOICES: dict[str, list[str]] = {
    "ps": [settings.tts_voice_ps, "ps-AF-GulNawazNeural", "ur-PK-AsadNeural"],
    "ur": [settings.tts_voice_ur, "ur-PK-UzmaNeural"],
    "en": [settings.tts_voice_en, "en-US-JennyNeural"],
}


async def synthesize(text: str, lang: str) -> Optional[bytes]:
    """
    Synthesize text into MP3 audio bytes using edge-tts.
    Tries primary voice, then automatic fallbacks.
    Returns MP3 bytes on success, or None on failure (graceful degradation).
    """
    if not text or not text.strip():
        return None

    # Clean text: remove raw bracket citations and markdown formatting for smoother TTS
    clean_text = text.replace("**", "").replace("__", "")
    target_lang = lang.lower().strip()
    candidate_voices = FALLBACK_VOICES.get(target_lang, [settings.tts_voice_en])

    for voice in candidate_voices:
        log.info("TTS: Synthesizing %d characters in '%s' with voice '%s'", len(clean_text), target_lang, voice)
        try:
            communicator = edge_tts.Communicate(text=clean_text, voice=voice)
            audio_stream = io.BytesIO()
            async for chunk in communicator.stream():
                if chunk["type"] == "audio":
                    audio_stream.write(chunk["data"])

            mp3_bytes = audio_stream.getvalue()
            if mp3_bytes and len(mp3_bytes) > 500:
                log.info("TTS: Generated %d MP3 audio bytes with voice '%s'", len(mp3_bytes), voice)
                return mp3_bytes
            log.warning("TTS: Synthesized audio stream was too small (%d bytes) for voice '%s'", len(mp3_bytes), voice)
        except Exception as exc:  # noqa: BLE001
            log.warning("TTS: Synthesis attempt failed for voice '%s': %s (trying fallback)", voice, exc)

    log.error("TTS: All candidate voices exhausted for language '%s' (graceful fallback)", target_lang)
    return None


def to_base64_data_uri(mp3_bytes: Optional[bytes]) -> Optional[str]:
    """Format MP3 bytes into a base64 data URI string for JSON response."""
    if not mp3_bytes:
        return None
    encoded = base64.b64encode(mp3_bytes).decode("ascii")
    return f"data:audio/mpeg;base64,{encoded}"


async def verify_voices() -> Dict[str, bool]:
    """
    Startup check to verify configured voices exist in edge-tts registry.
    Returns mapping of lang_code -> bool (e.g. {"ur": True, "ps": True, "en": True}).
    Logs a WARNING per missing language.
    """
    lang_to_voice = {
        "ur": settings.tts_voice_ur,
        "ps": settings.tts_voice_ps,
        "en": settings.tts_voice_en,
    }
    results: Dict[str, bool] = {}
    try:
        available_voices = await edge_tts.list_voices()
        available_names = {v.get("ShortName") for v in available_voices}
        for lang, voice in lang_to_voice.items():
            ok = voice in available_names
            results[lang] = ok
            if ok:
                log.info("TTS [%s] voice verified: %s", lang, voice)
            else:
                log.warning("WARNING: TTS [%s] voice '%s' NOT found in edge-tts registry!", lang, voice)
        return results
    except Exception as exc:  # noqa: BLE001
        log.error("TTS: Could not fetch registry voice list: %s", exc)
        for lang, voice in lang_to_voice.items():
            log.warning("WARNING: TTS [%s] voice '%s' check failed due to network/registry error", lang, voice)
            results[lang] = False
        return results
