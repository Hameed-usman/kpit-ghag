"""
Ghag – FastAPI application factory.

Lifespan: initialise SQLite schema, load KB, check TTS voices at startup.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.services import kb, logstore, tts
from app.services.rate_limiter import rate_limiter, RATE_LIMIT_DETAIL

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
    docs_url = None if settings.public_mode else "/docs"
    redoc_url = None if settings.public_mode else "/redoc"
    openapi_url = None if settings.public_mode else "/openapi.json"

    app = FastAPI(
        title="Ghag – KP Public Services Assistant",
        version="1.0.0",
        description="Voice-first government services assistant for Khyber Pakhtunkhwa.",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # In-memory Rate Limiting Middleware (FR-16)
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        path = request.url.path
        is_rate_limited_path = (
            path in ("/api/v1/ask", "/api/v1/check")
            or path.startswith("/api/v1/ask/")
            or (path.startswith("/api/v1/check/") and not path.startswith("/api/v1/checklist"))
        )
        if is_rate_limited_path and os.environ.get("GHAG_SKIP_RATE_LIMIT") != "1" and settings.rate_limit_rpm > 0:
            forwarded = request.headers.get("x-forwarded-for", "")
            client_ip = forwarded.split(",")[0].strip() if forwarded else None
            if not client_ip and request.client:
                client_ip = request.client.host
            client_ip = client_ip or "127.0.0.1"

            allowed, retry_after = rate_limiter.check(client_ip, limit=settings.rate_limit_rpm)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": RATE_LIMIT_DETAIL, "retry_after": retry_after},
                    headers={"Retry-After": str(retry_after)},
                )
        return await call_next(request)

    # CORS configuration (FR-15: restricted to same origin when PUBLIC_MODE=true)
    if settings.public_mode:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[],
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Root alias for /dashboard/audit
    @app.api_route("/dashboard/audit", methods=["GET", "POST"], include_in_schema=False)
    async def root_dashboard_audit():
        if settings.public_mode:
            raise HTTPException(
                status_code=403,
                detail="Public demo mode: administrative audit access is disabled",
            )
        return {"status": "ok", "audit": "active"}

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
