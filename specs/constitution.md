# Ghag – Constitution (Non-Negotiable Principles)

> Version 1.0 | Ghag v1 | KP AI Innovation Challenge 2026

## P-1  Knowledge-Base Supremacy

Answers MUST derive exclusively from entries present in `kb/`.
The system MUST NOT invent, extrapolate, or hallucinate requirements, fees,
addresses, timelines, or document names.  Any fact not traceable to a KB entry
with a valid `source_id` is forbidden in a response.

## P-2  Source Traceability

Every answer payload MUST include a `source_id` field whose value matches
an `id` field in the active KB.  If no matching `source_id` can be found,
the system MUST return a handoff response (see P-3).

## P-3  Graceful Handoff on Uncertainty

If confidence < threshold (default 0.75) OR no KB entry covers the query,
the system MUST return `outcome: handoff` with a human-readable explanation
in the user's language.  It MUST NOT guess.

## P-4  Zero PII Storage

(a) Audio buffers MUST NOT be persisted to disk or database.
(b) Names, addresses, and phone numbers MUST NOT be logged.
(c) Any 13-digit sequence matching `\d{5}-\d{7}-\d{1}` (CNIC pattern) MUST
    be redacted to `[CNIC-REDACTED]` before writing to any log or DB column.
(d) The `interactions` table stores only: timestamp, detected language,
    outcome enum, source_id, and an anonymised question hash (SHA-256 of
    lowercased, stripped text — no raw question text stored).

## P-5  Requirement Traceability

Every user-facing feature MUST map to a numbered Functional Requirement
(FR-N) in `specs/spec.md` and an Acceptance Criterion in Given/When/Then
form.  No code may be merged for a feature that lacks both.

## P-6  Secrets via Environment Only

API keys, DB paths, and all configuration MUST be read from environment
variables (via `app/config.py` / `pydantic-settings`).  Hardcoding any
secret in source is a build-breaking violation.  `.env` MUST be in
`.gitignore`.

## P-7  Graceful Degradation

| Failure | Required behaviour |
|---------|-------------------|
| TTS unavailable | Return text answer; set `tts_available: false` in response |
| Groq API timeout / down | Return cached demo answer if `DEMO_MODE=true`; else `outcome: handoff` |
| Network loss at venue | Serve static fixture from `eval/demo_fixture.json` |
| SQLite locked | Queue write; never crash the request thread |

## P-8  Language Respect

The response language MUST match the detected input language (`ur` / `ps` / `en`).
Language detection is based on Whisper's `language` output or an explicit
`lang` parameter from the client.

## P-9  Scope Discipline

v1 covers ONLY the Domicile Certificate service.  Any query about another
service MUST return a polite out-of-scope message, NOT a guess.

## P-10  No Telephony, No Real SMS

Real phone calls and real SMS dispatch are explicitly out of scope for v1.
The UI simulates SMS display only; no gateway is ever called.

---

*Violations of P-1 through P-4 and P-6 are build-breaking.
All others are blocking PR review comments.*
