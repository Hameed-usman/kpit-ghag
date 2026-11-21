"""
Tests for Chunk 6 (FR-15, FR-16, FR-17):
- PUBLIC_MODE guards on approve, audit, and docs
- In-memory client rate limiting (429 with friendly message)
- Glass-box explainability fields on /ask and /check
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app
from app.services.llm import AnswerResult
from app.services.rate_limiter import rate_limiter, RATE_LIMIT_DETAIL


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Ensure in-memory rate limiter is reset between tests."""
    rate_limiter.reset()
    yield
    rate_limiter.reset()


# ── 1. PUBLIC_MODE Tests (FR-15) ──────────────────────────────────────────────

class TestPublicMode:
    @pytest.fixture
    def public_client(self, monkeypatch):
        """Create a client with PUBLIC_MODE=true."""
        monkeypatch.setattr(settings, "public_mode", True)
        monkeypatch.setattr(settings, "admin_token", "secret-token-123")
        app = create_app()
        return TestClient(app)

    def test_approve_returns_403_in_public_mode_even_with_valid_token(self, public_client):
        """POST /api/v1/dashboard/approve returns 403 in public mode."""
        resp = public_client.post(
            "/api/v1/dashboard/approve",
            json={
                "pending_id": 1,
                "answer_text": "Public test answer",
                "source_url": "https://cfc.kp.gov.pk/",
                "admin_token": "secret-token-123",
            },
        )
        assert resp.status_code == 403
        assert "disabled" in resp.json()["detail"].lower()

    def test_audit_returns_403_in_public_mode(self, public_client):
        """Audit endpoints return 403 in public mode."""
        resp1 = public_client.get("/api/v1/dashboard/audit")
        assert resp1.status_code == 403

        resp2 = public_client.get("/dashboard/audit")
        assert resp2.status_code == 403

    def test_docs_and_openapi_disabled_in_public_mode(self, public_client):
        """Interactive docs and openapi.json are disabled (404) in public mode."""
        resp_docs = public_client.get("/docs")
        assert resp_docs.status_code == 404

        resp_openapi = public_client.get("/openapi.json")
        assert resp_openapi.status_code == 404


# ── 2. Rate Limiting Tests (FR-16) ────────────────────────────────────────────

class TestRateLimiting:
    def test_rate_limit_exceeded_returns_429(self, monkeypatch):
        """11th request from same IP within a minute returns 429."""
        monkeypatch.delenv("GHAG_SKIP_RATE_LIMIT", raising=False)
        monkeypatch.setattr(settings, "rate_limit_rpm", 5)
        monkeypatch.setattr(settings, "public_mode", False)
        rate_limiter.reset()

        app = create_app()
        client = TestClient(app)

        mock_ans = AnswerResult(
            lang="en",
            answer="Test answer",
            sms="Test sms",
            source_id="dom-authority",
            confident=True,
        )

        with patch("app.routers.ask.llm.grounded_answer", new_callable=AsyncMock, return_value=mock_ans), \
             patch("app.routers.ask.tts.synthesize", new_callable=AsyncMock, return_value=b"fake-audio"):

            # First 5 requests succeed
            for i in range(5):
                res = client.post("/api/v1/ask", data={"text": f"Question {i}"})
                assert res.status_code == 200, f"Request {i} failed: {res.text}"

            # 6th request hits limit
            res_limited = client.post("/api/v1/ask", data={"text": "Over the limit question"})
            assert res_limited.status_code == 429
            data = res_limited.json()
            assert "Too many requests" in data["detail"]
            assert "ډېرې غوښتنې وشوې" in data["detail"]
            assert "Retry-After" in res_limited.headers


# ── 3. Glass-Box Explainability Fields (FR-17) ─────────────────────────────────

class TestGlassBoxExplainability:
    def test_ask_returns_glass_box_fields(self, client):
        """POST /api/v1/ask returns all glass-box trace fields without hallucination."""
        mock_ans = AnswerResult(
            lang="en",
            answer="Apply at DC office.",
            sms="Apply at DC office.",
            source_id="dom-authority",
            confident=True,
        )

        with patch("app.routers.ask.llm.grounded_answer", new_callable=AsyncMock, return_value=mock_ans), \
             patch("app.routers.ask.tts.synthesize", new_callable=AsyncMock, return_value=b"audio"):

            res = client.post("/api/v1/ask", data={"text": "Where to apply for domicile?"})
            assert res.status_code == 200
            body = res.json()

            # Verify all glass-box fields
            assert body["transcript"] == "Where to apply for domicile?"
            assert body["lang"] == "en"
            assert body["source_id"] == "dom-authority"
            assert body["source_url"] == "https://cfc.kp.gov.pk/"
            assert body["last_verified"] == "2026-11-17"
            assert body["confident"] is True
            assert body["handoff_reason"] is None
            assert isinstance(body["latency_ms"], int)
            assert body["latency_ms"] >= 0

    def test_ask_handoff_returns_glass_box_fields(self, client):
        """POST /api/v1/ask on out-of-scope question reflects unconfident / refusal state."""
        mock_ans = AnswerResult(
            lang="en",
            answer="Outside KB.",
            sms="Outside KB.",
            source_id="invalid-id",
            confident=False,
        )

        with patch("app.routers.ask.llm.grounded_answer", new_callable=AsyncMock, return_value=mock_ans), \
             patch("app.routers.ask.tts.synthesize", new_callable=AsyncMock, return_value=b"audio"):

            res = client.post("/api/v1/ask", data={"text": "How to register motor car?"})
            assert res.status_code == 200
            body = res.json()

            assert body["outcome"] == "handoff"
            assert body["source_id"] is None
            assert body["source_url"] is None
            assert body["last_verified"] is None
            assert body["confident"] is False
            assert "verified government knowledge base" in body["handoff_reason"]
            assert isinstance(body["latency_ms"], int)

    def test_check_returns_glass_box_fields(self, client):
        """POST /api/v1/check returns glass-box trace fields."""
        with patch("app.routers.check.tts.synthesize", new_callable=AsyncMock, return_value=b"audio"):
            res = client.post(
                "/api/v1/check",
                json={"text": "I have applicant CNIC and 2 photos and bill", "service": "domicile"},
            )
            assert res.status_code == 200
            body = res.json()

            assert body["source_id"] == "dom-checklist"
            assert body["source_url"] == "https://cfc.kp.gov.pk/"
            assert body["last_verified"] == "2026-11-17"
            assert isinstance(body["confident"], bool)
            assert isinstance(body["latency_ms"], int)
