"""
Ghag – FastAPI application factory.

Lifespan: initialise SQLite schema, load KB, check TTS voices at startup.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.services import kb, logstore, tts

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, load KB, check TTS voices. Shutdown: nothing needed."""
    log.info("Ghag starting up…")
    # T2-10: init DB schema
    logstore.init_db()
    # T2-8: load KB into memory
    kb.init_kb("kb/domicile.md")
    log.info("KB sections loaded: %d", len(kb.get_kb()))
    # T2-6: verify TTS voice availability (non-fatal, skipped in test/demo mode)
    if not settings.demo_mode and os.environ.get("GHAG_SKIP_TTS_CHECK") != "1":
        voice_status = await tts.verify_voices()
        for lang, ok in voice_status.items():
            if not ok:
                log.warning("WARNING: TTS voice for language '%s' is unavailable!", lang)
            else:
                log.info("TTS voice for language '%s': OK", lang)
    else:
        log.info("TTS voice check skipped (DEMO_MODE or GHAG_SKIP_TTS_CHECK=1)")
    yield
    log.info("Ghag shutting down.")


def create_app() -> FastAPI:
    """Create and return the configured FastAPI application."""
    app = FastAPI(
        title="Ghag – KP Public Services Assistant",
        version="1.0.0",
        description="Voice-first government services assistant for Khyber Pakhtunkhwa.",
        lifespan=lifespan,
    )

    # Enable CORS for external frontends (e.g. Vercel, mobile, external clients)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from app.routers import ask, check, dashboard, health  # noqa: PLC0415
    app.include_router(ask.router)
    app.include_router(check.router)
    app.include_router(dashboard.router)
    app.include_router(health.router)

    # Serve frontend
    static_dir = Path("static")
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory="static", html=True), name="static")

    return app


app = create_app()
