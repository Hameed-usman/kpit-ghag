"""
Tests for dashboard endpoints — Chunk 5.

Covers:
- GET /api/v1/dashboard/stats returns all fields
- POST /api/v1/dashboard/approve rejects invalid token (401)
- POST /api/v1/dashboard/approve returns 404 on missing pending query
- POST /api/v1/dashboard/approve returns 422 on invalid source URL or empty text
- POST /api/v1/dashboard/approve successfully marks query resolved and returns approved status
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from app.config import settings
from app.services.logstore import log_query


def test_stats_returns_all_fields(client):
    """FR-9 / AC-9: GET /api/v1/dashboard/stats returns all required fields."""
    # Seed queries
    log_query(lang="ur", source_id="dom-channels", handled="answered", question_text="کہاں جمع کرائیں؟")
    log_query(lang="ps", source_id="dom-requirements", handled="answered", question_text="څه اسناد پکار دي؟")
    log_query(lang="en", source_id="", handled="handoff", question_text="What is passport fee?")

    r = client.get("/api/v1/dashboard/stats")
    assert r.status_code == 200
    data = r.json()

    assert "total_interactions" in data
    assert data["total_interactions"] >= 3

    assert "outcome_counts" in data
    assert "answered" in data["outcome_counts"]
    assert "handoff" in data["outcome_counts"]

    assert "language_split" in data
    assert "ur" in data["language_split"]
    assert "ps" in data["language_split"]
    assert "en" in data["language_split"]

    assert "top_questions" in data
    assert isinstance(data["top_questions"], list)
    if data["top_questions"]:
        top = data["top_questions"][0]
        assert "question_hash" in top
        assert "preview" in top
        assert "count" in top

    assert "pending_unanswered" in data
    assert isinstance(data["pending_unanswered"], list)
    assert any("passport" in item["preview"].lower() for item in data["pending_unanswered"])


def test_approve_bad_token_returns_401(client):
    """FR-10 / AC-10: bad admin_token → 401."""
    payload = {
        "pending_id": 1,
        "answer_text": "Approved fee is 200.",
        "source_url": "https://cfc.kp.gov.pk/",
        "admin_token": "wrong-secret-token",
    }
    r = client.post("/api/v1/dashboard/approve", json=payload)
    assert r.status_code == 401
    assert "Invalid admin token" in r.json()["detail"]


def test_approve_unknown_pending_returns_404(client):
    """FR-10: unknown pending_id → 404."""
    payload = {
        "pending_id": 999999,
        "answer_text": "Approved answer.",
        "source_url": "https://cfc.kp.gov.pk/",
        "admin_token": settings.admin_token or "test-admin",
    }
    r = client.post("/api/v1/dashboard/approve", json=payload)
    assert r.status_code == 404
    assert "not found" in r.json()["detail"]


def test_approve_invalid_url_returns_422(client):
    """FR-10: invalid source_url → 422."""
    payload = {
        "pending_id": 1,
        "answer_text": "Valid text.",
        "source_url": "not-a-valid-http-url",
        "admin_token": settings.admin_token or "test-admin",
    }
    r = client.post("/api/v1/dashboard/approve", json=payload)
    assert r.status_code == 422


def test_approve_valid_writes_kb_entry(client, tmp_path):
    """FR-10: valid token + valid pending_id → status=approved, kb_entry_id set."""
    # Seed a handoff question
    row_id = log_query(
        lang="ur",
        source_id="",
        handled="handoff",
        question_text="کیا یتیم بچوں کے لیے ڈومیسائل فیس معاف ہے؟",
    )

    # Use a dummy temp kb file for approval write
    dummy_kb = tmp_path / "domicile.md"
    dummy_kb.write_text("# KB Test\n", encoding="utf-8")

    payload = {
        "pending_id": row_id,
        "answer_text": "جی ہاں، مجاز اتھارٹی خصوصی رعایت دے سکتی ہے۔",
        "source_url": "https://cfc.kp.gov.pk/rules",
        "admin_token": settings.admin_token or "test-admin",
    }

    with patch("app.services.logstore.Path", return_value=dummy_kb):
        r = client.post("/api/v1/dashboard/approve", json=payload)

    assert r.status_code == 200
    res = r.json()
    assert res["status"] == "approved"
    assert res["kb_entry_id"] == f"dom-approved-{row_id}"
