"""
Ghag – Query Log Store.

Persists anonymous query logs to SQLite table 'queries'.
Enforces Constitution P-4:
- Audio is never stored.
- Any 13-digit CNIC pattern is redacted before storing.
- Zero personal identifiers retained.

T2-9, T2-10 | P-4, NFR-6
"""
from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from app.config import settings
from app.schemas import (
    DashboardStatsResponse,
    PendingItem,
    QuestionPreview,
)

log = logging.getLogger(__name__)

# CNIC matching:
# 1. 13 digits with hyphens (e.g. 17301-1234567-1)
# 2. 13 contiguous digits (e.g. 1730112345671)
_CNIC_DASHED_RE = re.compile(r"\b\d{5}-\d{7}-\d{1}\b")
_CNIC_RAW_RE = re.compile(r"\b\d{13}\b")
_CNIC_REPLACEMENT = "[CNIC-REDACTED]"

_DDL = """
CREATE TABLE IF NOT EXISTS queries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT    NOT NULL,
    lang          TEXT    NOT NULL,
    source_id     TEXT,
    handled       TEXT    NOT NULL,
    question_text TEXT    NOT NULL,
    is_demo       INTEGER NOT NULL DEFAULT 0,
    is_resolved   INTEGER NOT NULL DEFAULT 0
);
"""


def redact_cnic(text: str) -> str:
    """Redact any 13-digit CNIC sequence (with or without hyphens)."""
    if not text:
        return ""
    text = _CNIC_DASHED_RE.sub(_CNIC_REPLACEMENT, text)
    text = _CNIC_RAW_RE.sub(_CNIC_REPLACEMENT, text)
    return text


def get_connection() -> sqlite3.Connection:
    """Return SQLite connection with WAL enabled."""
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """Context manager for executing and committing SQLite transactions safely."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        log.error("DB error occurred, rolled back: %s", exc)
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str | Path] = None) -> None:
    """Initialize SQLite database and create tables if not present."""
    target_path = Path(db_path or settings.db_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with db_cursor() as cur:
        cur.executescript(_DDL)
        # Migrate schema if is_resolved is missing from older db
        try:
            cur.execute("ALTER TABLE queries ADD COLUMN is_resolved INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Already exists
    log.info("DB: Initialized database schema at %s", target_path)


def log_query(
    *,
    lang: str,
    source_id: Optional[str],
    handled: str,
    question_text: str,
    is_demo: bool = False,
) -> int:
    """
    Log an anonymized query.

    Strictly accepts text only (audio is forbidden).
    Applies CNIC redaction before persistence.
    """
    cleaned_question = redact_cnic(question_text)
    ts = datetime.now(timezone.utc).isoformat()
    norm_source = source_id.strip() if source_id else ""

    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO queries (ts, lang, source_id, handled, question_text, is_demo, is_resolved)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (ts, lang, norm_source, handled, cleaned_question, int(is_demo)),
        )
        row_id = cur.lastrowid or 0

    log.debug("DB: Logged query #%d (handled=%s, lang=%s)", row_id, handled, lang)
    return row_id


def get_dashboard_stats() -> DashboardStatsResponse:
    """Return aggregated, fully anonymized statistics for the council dashboard."""
    with db_cursor() as cur:
        # 1. Total interactions
        cur.execute("SELECT COUNT(*) FROM queries")
        total = cur.fetchone()[0] or 0

        # 2. Outcome counts
        cur.execute("SELECT handled, COUNT(*) FROM queries GROUP BY handled")
        outcome_counts: dict[str, int] = {"answered": 0, "handoff": 0}
        for row in cur.fetchall():
            outcome_counts[row[0]] = row[1]

        # 3. Language split
        cur.execute("SELECT lang, COUNT(*) FROM queries GROUP BY lang")
        lang_split: dict[str, int] = {"ur": 0, "ps": 0, "en": 0}
        for row in cur.fetchall():
            lang_split[row[0]] = row[1]

        # 4. Top questions
        cur.execute("""
            SELECT question_text, COUNT(*) as cnt
            FROM queries
            GROUP BY question_text
            ORDER BY cnt DESC
            LIMIT 10
        """)
        top_questions: list[QuestionPreview] = []
        for q_text, cnt in cur.fetchall():
            q_hash = hashlib.sha256(q_text.encode("utf-8")).hexdigest()[:8]
            preview = q_text[:60] + ("…" if len(q_text) > 60 else "")
            top_questions.append(QuestionPreview(
                question_hash=q_hash,
                preview=preview,
                count=cnt
            ))

        # 5. Pending unanswered (where handled == 'handoff' and is_resolved == 0)
        cur.execute("""
            SELECT id, question_text, lang, COUNT(*) as cnt
            FROM queries
            WHERE handled = 'handoff' AND is_resolved = 0
            GROUP BY question_text
            ORDER BY cnt DESC, id DESC
            LIMIT 20
        """)
        pending_items: list[PendingItem] = []
        for pid, q_text, q_lang, cnt in cur.fetchall():
            preview = q_text[:60] + ("…" if len(q_text) > 60 else "")
            valid_lang = q_lang if q_lang in ("ur", "ps", "en") else "ur"
            pending_items.append(PendingItem(
                id=pid,
                preview=preview,
                lang=valid_lang,  # type: ignore[arg-type]
                count=cnt
            ))

    return DashboardStatsResponse(
        total_interactions=total,
        outcome_counts=outcome_counts,
        language_split=lang_split,
        top_questions=top_questions,
        pending_unanswered=pending_items,
    )


def approve_pending_question(
    pending_id: int,
    answer_text: str,
    source_url: str,
    kb_path_override: Optional[Path] = None,
) -> str:
    """
    Approve a pending question and append to the KB markdown file.
    Marks the query as resolved and reloads the active KB.
    """
    with db_cursor() as cur:
        cur.execute("SELECT question_text FROM queries WHERE id = ? AND handled = 'handoff'", (pending_id,))
        row = cur.fetchone()
        if not row:
            raise KeyError(f"Pending query #{pending_id} not found")
        question_text = row[0]
        cur.execute("UPDATE queries SET is_resolved = 1 WHERE id = ?", (pending_id,))

    clean_id = f"dom-approved-{pending_id}"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_entry = (
        f"\n\n---\n"
        f"id: {clean_id}\n"
        f"title: Approved Q: {question_text[:35]}\n"
        f"source_url: {source_url}\n"
        f"last_verified: {today}\n"
        f"---\n\n"
        f"**Question**: {question_text}\n\n"
        f"**Answer**: {answer_text.strip()}\n"
    )

    kb_path = kb_path_override or Path("kb/domicile.md")
    if kb_path.exists():
        with open(kb_path, "a", encoding="utf-8") as f:
            f.write(new_entry)

        from app.services.kb import KnowledgeBase
        KnowledgeBase.load().reload(kb_path)
        log.info("Appended approved entry %s to %s and reloaded KB", clean_id, kb_path)

    return clean_id
