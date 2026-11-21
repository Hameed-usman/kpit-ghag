"""
Ghag – Pydantic v2 request/response schemas.

All API request and response shapes are defined here.
Routers import from this module only — no inline model definitions.
See specs/api-contract.md for the authoritative contract.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


# ── Shared enums ───────────────────────────────────────────────────────────

class Lang(str, Enum):
    ur = "ur"
    ps = "ps"
    en = "en"


class Outcome(str, Enum):
    answered = "answered"
    handoff = "handoff"


# ── POST /ask ──────────────────────────────────────────────────────────────

class AskResponse(BaseModel):
    """Response from POST /api/v1/ask."""
    transcript: str
    lang: Lang
    answer: str
    outcome: Outcome
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    sms_text: str = Field(..., max_length=160)
    audio_b64: Optional[str] = None
    tts_available: bool = True


# ── POST /check ────────────────────────────────────────────────────────────

class CheckMissingItem(BaseModel):
    id: str
    label: str


class CheckRequest(BaseModel):
    """JSON Request body for POST /api/v1/check."""
    text: Optional[str] = None
    service: str = "domicile"
    lang: Optional[str] = None
    lang_hint: Optional[str] = "auto"


class ChecklistItemSchema(BaseModel):
    id: str
    label_en: str
    label_ur: str = ""
    label_ps: str = ""
    required: bool = True


class ChecklistResponse(BaseModel):
    available: bool
    items: list[ChecklistItemSchema] = Field(default_factory=list)


class CheckResponse(BaseModel):
    """Response from POST /api/v1/check."""
    lang: Lang
    heard: str
    matched: list[str] = Field(default_factory=list)
    missing: list[CheckMissingItem] = Field(default_factory=list)
    verdict: str  # "ready" | "missing" | "unsure" | "unavailable"
    spoken: str
    sms: str
    source_id: Optional[str] = "dom-checklist"
    tts_available: bool = True
    audio_b64: Optional[str] = None


# ── GET /dashboard/stats ───────────────────────────────────────────────────

class QuestionPreview(BaseModel):
    question_hash: str
    preview: str
    count: int


class PendingItem(BaseModel):
    id: int
    preview: str
    lang: Lang
    count: int


class DashboardStatsResponse(BaseModel):
    """Response from GET /api/v1/dashboard/stats."""
    total_interactions: int
    outcome_counts: dict[str, int]
    language_split: dict[str, int]
    top_questions: list[QuestionPreview]
    pending_unanswered: list[PendingItem]


# ── POST /dashboard/approve ────────────────────────────────────────────────

class ApproveRequest(BaseModel):
    """Request body for POST /api/v1/dashboard/approve."""
    pending_id: int
    answer_text: str = Field(..., min_length=1)
    source_url: str
    admin_token: str


class ApproveResponse(BaseModel):
    status: str
    kb_entry_id: str


# ── GET /health ────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Response from GET /api/v1/health."""
    status: str
    demo_mode: bool
    groq_reachable: bool
    tts_available: bool
    tts: dict[str, bool] = Field(default_factory=dict)
    kb_entries: int
    db_ok: bool
