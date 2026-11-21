# Ghag – Task Checklist

> Chunk = implementation session. Each task has ID, linked FR, Definition of Done.
> Current time: 17 Nov 2026 (4 days to demo on 21 Nov).

## Chunk 1 – Scaffolding & Specs ✅ (this session)

| ID | FR | Task | DoD |
|----|-----|------|-----|
| T1-1 | — | Write all 5 spec files | Reviewed & approved by dev |
| T1-2 | P-6 | Repo scaffold + stubs | All stubs importable; `pytest --collect-only` exits 0 |
| T1-3 | P-1 | Populate `kb/domicile.md` | All `TODO(verified-source)` resolved or explicitly flagged |

## Chunk 2 – Voice Pipeline ✅

| ID | FR | Task | DoD |
|----|-----|------|-----|
| T2-1 | FR-1 | `POST /ask` multipart handler | Accepts audio+text; returns 400 if both missing ✅ |
| T2-2 | FR-2 | `stt.py` – Groq Whisper | Returns transcript + lang for WAV; auto-detect lang ✅ |
| T2-3 | FR-2 | DEMO_MODE stub in `stt` | `DEMO_MODE=true` returns fixture transcript without API call ✅ |
| T2-4 | FR-3 | `llm.py` – KB-only prompt | System prompt blocks outside knowledge; passes pytest ✅ |
| T2-5 | FR-5 | Handoff logic in LLM & ask router | Low-confidence or invalid source_id → `outcome: handoff`; tested ✅ |
| T2-6 | FR-6 | `tts.py` – edge-tts | Voices in config; MP3 audio returned or graceful fallback ✅ |
| T2-7 | FR-7 | SMS formatter | `sms_text` ≤ 140/160 chars; truncates gracefully ✅ |
| T2-8 | FR-4 | `kb.py` – parse & render KB | Parses sections; excludes TODO; valid source citation ✅ |
| T2-9 | P-4 | CNIC redaction in logstore | Any 13-digit sequence redacted to `[CNIC-REDACTED]` before store ✅ |
| T2-10 | NFR-6 | `logstore.py` SQLite queries table | Schema created on startup; persists queries text-only ✅ |

## Chunk 3 – Document Check + Eval ✅

| ID | FR | Task | DoD |
|----|-----|------|-----|
| T3-1 | FR-8 | `check_service.py` missing-doc diff | Code set-difference (required - matched); drops invalid IDs; tested ✅ |
| T3-2 | FR-8 | `POST /check` router | Accepts JSON or multipart audio; returns verdict & missing labels per contract ✅ |
| T3-3 | FR-8 | Multilingual spoken/sms for check | Urdu, Pashto, English templates validated in code and tests ✅ |
| T3-4 | NFR-3 | `eval/eval_set.json` – 30 Q&A & check cases | Covers /ask (20 cases, 5 out-of-KB) & /check (10 cases) across ur/ps/en ✅ |
| T3-5 | NFR-3 | `scripts/run_eval.py` runner | Throttled runner with 429 backoff; writes `eval/report.md` ✅ |
| T3-6 | NFR-1 | Smoke testing tool (`scripts/smoke.py`) | Python stdlib smoke runner for text and audio requests ✅ |

## Chunk 4 – Frontend & Interactive Capabilities ✅

| ID | FR | Task | DoD |
|----|-----|------|-----|
| T4-1 | FR-10 | Backend: `lang_hint` support in `/ask` and `/check` | Accepts `lang_hint` in {auto, ur, ps, en}; passes to Whisper when not auto; discrepancy logged ✅ |
| T4-2 | FR-11 | Backend: `GET /api/v1/checklist` endpoint | Returns `{available, items}` from KB; `{available: false, items: []}` when unverified; tested ✅ |
| T4-3 | FR-9 | Backend: Serve `static/` at `/` | Serves `index.html` at root without shadowing `/api/v1/*`, `/docs`, `/openapi.json` ✅ |
| T4-4 | FR-9 | UI layout, tabs & language selector | Single-screen dark theme, no CDN/Google fonts; "Ask" and "Check" tabs; language selector ✅ |
| T4-5 | FR-9 | Voice input with MediaRecorder | MIME auto-detect, tap start/stop, 30s countdown, mic permission error handling, text fallback ✅ |
| T4-6 | FR-9 | Interactive Ask view | Editable transcript ("I heard:") with "Send again"; audio autoplay + replay; SMS bubble; latency badge ✅ |
| T4-7 | FR-9, FR-11 | Interactive Check view | Tick-boxes from `/checklist` when available; disabled banner when unavailable; green/red result banner ✅ |
| T4-8 | FR-9 | Accessibility & RTL | Native `dir="rtl"` for Urdu/Pashto, system Arabic fonts, aria-live regions ✅ |
| T4-9 | FR-12 | Pre-recorded demo cache & UI toggle | `scripts/capture_demo_cache.py` captures real responses; UI toggle replays cache with badge ✅ |
| T4-10 | — | Smoke tool update & pytest suite | Smoke script prints WARN on unverified check without failure; pytest covers all new features ✅ |

## Chunk 5 – Dashboard + Hardening ✅ (Final MVP)

| ID | FR | Task | DoD |
|----|-----|------|-----|
| T5-1 | FR-9 | `GET /dashboard/stats` router | All fields returned; tested with seeded DB ✅ |
| T5-2 | FR-10 | `POST /dashboard/approve` router | Rejects bad token (401); writes KB draft on success ✅ |
| T5-3 | FR-9 | Dashboard HTML page | Shows top questions, language split, pending list ✅ |
| T5-4 | P-4 | Full PII audit | Grep logs: 0 CNICs, 0 names after full test run ✅ |
| T5-5 | NFR-6 | End-to-end demo rehearsal | Full flow works with `DEMO_MODE=true` (no internet) ✅ |
| T5-6 | — | README run steps verified | Fresh venv → `pip install` → `uvicorn` succeeds in < 2 min ✅ |
| T5-7 | — | pytest full suite green | 0 failures, 0 warnings on `pytest -v` ✅ |
