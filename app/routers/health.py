"""
Ghag – GET /api/v1/health router.

Returns live readiness state: Groq reachability, TTS, KB size, DB status.
Used by the UI to detect DEMO_MODE / offline state (P-7).
"""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings
from app.schemas import HealthResponse
from app.services import kb, logstore, tts

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["health"])

_GROQ_PROBE_URL = "https://api.groq.com"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse | JSONResponse:
    """Return system health status."""
    # DB check
    db_ok = True
    try:
        logstore.get_connection().close()
    except Exception as exc:  # noqa: BLE001
        log.error("Health: DB check failed: %s", exc)
        db_ok = False

    # KB size
    try:
        kb_entries = len(kb.get_kb())
    except RuntimeError:
        kb_entries = 0

    # Groq reachability (short timeout, non-fatal)
    groq_reachable = False
    if not settings.demo_mode and os.environ.get("GHAG_SKIP_GROQ_CHECK") != "1":
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.head(_GROQ_PROBE_URL)
                groq_reachable = r.status_code < 500
        except Exception:  # noqa: BLE001
            groq_reachable = False
    else:
        groq_reachable = False  # demo mode — no network

    # TTS per-language check
    tts_status = {"ur": True, "ps": True, "en": True}
    if not settings.demo_mode and os.environ.get("GHAG_SKIP_TTS_CHECK") != "1":
        try:
            tts_status = await tts.verify_voices()
        except Exception:  # noqa: BLE001
            pass
    overall_tts = any(tts_status.values())

    response = HealthResponse(
        status="ok" if db_ok else "degraded",
        demo_mode=settings.demo_mode,
        groq_reachable=groq_reachable,
        tts_available=overall_tts,
        tts=tts_status,
        kb_entries=kb_entries,
        db_ok=db_ok,
    )
    if not db_ok:
        return JSONResponse(content=response.model_dump(), status_code=503)
    return response
