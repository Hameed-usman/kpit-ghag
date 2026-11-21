"""
conftest.py – Session-wide test fixtures.

Sets env vars and skips network-bound startup checks so the test suite
runs fully offline.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="session")
def _base_env(tmp_path_factory):
    """Set env vars for the entire test session before any app import."""
    db = tmp_path_factory.mktemp("db") / "test.db"
    env = {
        "GROQ_API_KEY": "test-key",
        "ADMIN_TOKEN": "test-admin",
        "DEMO_MODE": "false",
        "DB_PATH": str(db),
        "TTS_VOICE_UR": "ur-PK-AsadNeural",
        "TTS_VOICE_PS": "ps-AF-LatifaNeural",
        "TTS_VOICE_EN": "en-US-AriaNeural",
        "GHAG_SKIP_TTS_CHECK": "1",
        "GHAG_SKIP_GROQ_CHECK": "1",
    }
    for k, v in env.items():
        os.environ[k] = v
    yield
    for k in env:
        os.environ.pop(k, None)


@pytest.fixture(scope="session")
def app(_base_env):
    """Create the FastAPI app once per session (after env is set)."""
    from app.main import create_app
    return create_app()


@pytest.fixture(scope="session")
def client(app):
    """Return a TestClient that runs the full lifespan once per session."""
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
