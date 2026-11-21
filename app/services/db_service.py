"""
Ghag – Database Service (stub).

Responsibilities (to be implemented in Chunk 2 / T2-10):
- Create SQLite schema on startup (WAL mode, FTS5 tables).
- Provide interaction logging: anonymise query (SHA-256 hash + 60-char
  preview), store lang, outcome, source_id, timestamp — NO raw question text,
  NO audio, NO PII (P-4).
- Provide stats queries for the dashboard (FR-9).
- Provide pending_unanswered table for handoff questions (FR-9, FR-10).
- CNIC redaction applied before any write (P-4c).

SQLite tables (schema defined here, created by init_db):
  kb_entries  (FTS5): id, title, content, source_url, last_verified
  interactions:       id, ts, lang, outcome, source_id, question_hash, preview
  pending:            id, ts, lang, preview, question_hash, count

Constitution references: P-4, P-6.
"""
from __future__ import annotations
import sqlite3


CNIC_PATTERN = r'\d{5}-\d{7}-\d{1}'
CNIC_REDACTED = '[CNIC-REDACTED]'


def init_db(db_path: str) -> sqlite3.Connection:
    """
    Create the SQLite database and all tables.  Enable WAL mode.

    Should be called once at application startup (lifespan).

    TODO(chunk-2): implement
    """
    raise NotImplementedError


def redact_cnic(text: str) -> str:
    """
    Replace all CNIC-pattern substrings in text with [CNIC-REDACTED].

    Pattern: 5 digits - 7 digits - 1 digit (13 digits total with dashes).

    TODO(chunk-2): implement
    """
    raise NotImplementedError


def log_interaction(
    lang: str,
    outcome: str,
    source_id: str | None,
    question_text: str,
) -> None:
    """
    Log an anonymised interaction to the interactions table.

    Stores SHA-256 hash of lowercased question and a 60-char preview.
    Never stores raw question text, audio, names, or CNICs.

    TODO(chunk-2): implement
    """
    raise NotImplementedError


def get_stats() -> dict:
    """
    Return aggregated stats for the dashboard.

    Returns dict matching DashboardStatsResponse schema.

    TODO(chunk-5): implement
    """
    raise NotImplementedError


def get_pending_unanswered() -> list[dict]:
    """
    Return pending handoff questions for the dashboard.

    TODO(chunk-5): implement
    """
    raise NotImplementedError


def approve_pending(pending_id: int, answer_text: str, source_url: str) -> str:
    """
    Mark a pending question as answered; return new KB entry id.

    TODO(chunk-5): implement
    """
    raise NotImplementedError
