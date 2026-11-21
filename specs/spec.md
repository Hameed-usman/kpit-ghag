# Ghag – Software Requirements Specification

> Version 1.0 | Target demo: Sat 21 Nov 2026

## 1. User Stories

| ID | As a… | I want to… | So that… |
|----|-------|------------|----------|
| US-1 | KP resident | speak or type a question about Domicile Certificates | I get an instant, accurate answer in my language |
| US-2 | KP resident | list the documents I already have | the system tells me exactly what is missing so I don't waste a trip |
| US-3 | KP resident | hear the answer read aloud | I can use this without being fully literate |
| US-4 | KP resident | receive a short SMS-style summary | I have a written reference to take with me |
| US-5 | Council official | view a dashboard of top questions | I know what residents struggle with most |
| US-6 | Council official | see unanswered questions | I can write KB entries to fill gaps |
| US-7 | Council official | approve a pending KB answer | verified answers enter the live KB |

## 2. Functional Requirements

### FR-1  Voice/Text Input
The system MUST accept either (a) a multipart audio file (WAV/WebM ≤ 10 MB)
or (b) a plain-text string via `POST /ask`.

### FR-2  Transcription
Audio input MUST be transcribed using Groq whisper-large-v3.  The detected
language (`ur`, `ps`, `en`) MUST be returned and stored.

### FR-3  KB-Grounded Answer
The LLM MUST answer using only KB context injected into the prompt.
The system prompt MUST explicitly forbid the model from using outside knowledge.

### FR-4  Source Citation
Every answer MUST include `source_id` (matches a KB entry id) and `source_url`.

### FR-5  Confidence & Handoff
If the LLM signals low confidence or no KB passage covers the question,
return `outcome: handoff` with a human-readable referral message in user's lang.

### FR-6  Voice Output
The answer text MUST be synthesised with `edge-tts` and returned as a
base-64 audio/mpeg string. Configured voices:
- Urdu (`ur`): `ur-PK-AsadNeural` (fallback `ur-PK-UzmaNeural`)
- English (`en`): `en-US-AriaNeural` (fallback `en-US-JennyNeural`)
- Pashto (`ps`): `ps-AF-LatifaNeural` (fallback `ps-AF-GulNawazNeural`)
If TTS fails or is unavailable for a language, the response still returns text
with `tts_available: false`.

### FR-7  Simulated SMS
The response MUST include `sms_text` (≤ 160 chars) displayed in the UI
as a styled SMS bubble.  No real gateway is called.

### FR-8  Document Check
`POST /api/v1/check` accepts user input via JSON (`text`, `service`) or multipart audio (`audio`), with optional `lang_hint`.
It compares what the user states they have against the verified KB checklist:
- Checklist items have stable IDs (`D1..Dn`), multilingual labels, and required flags.
- If the checklist in the KB is marked `TODO(verified-source)` or missing, returns `verdict: "unavailable"` and referral handoff.
- LLM strictly extracts/maps spoken/written user items to checklist IDs (`matched_ids`, `ambiguous_ids`). It does NOT decide what is missing.
- Code calculates `missing = required - matched` via set difference. Unknown IDs from LLM are validated and dropped.
- Verdict is `"ready"` (all required matched, none ambiguous), `"missing"` (one or more required missing), `"unsure"` (ambiguous items present or unclear), or `"unavailable"` (checklist unverified).
- Returns structured JSON with `heard`, `matched`, `missing`, `verdict`, natural `spoken` audio, and `sms`.

### FR-9  Web User Interface
A single-screen, mobile-friendly web application served from `/` with clean dark theme and zero external CDN/font dependencies.
- Header with app title, connection/demo badge, and language selector for input.
- "Ask" and "Check my documents" tabs.
- Voice recording via MediaRecorder with visible 30s countdown and MIME auto-detection; text input fallback.
- Editable "I heard:" transcript with "Send again" action to fix mis-heard words live.
- Audio playback of base64 TTS response with autoplay and manual replay button.
- Simulated phone-style SMS bubble component.
- Visual human-handoff state card.
- Native RTL rendering for Urdu and Pashto with system Arabic/Urdu fonts.

### FR-10  Language Hint
`POST /api/v1/ask` and `POST /api/v1/check` accept an optional `lang_hint` in `{"auto", "ur", "ps", "en"}` (default `"auto"`).
When not `"auto"`, the hint is passed to Groq Whisper as its `language` parameter to improve accuracy on low-resource languages (e.g. Pashto). The system logs when Whisper's detected language differs from the hint.

### FR-11  Checklist Metadata Endpoint
`GET /api/v1/checklist` returns `{available: bool, items: [{id, label_en, label_ur, label_ps, required}]}` from verified KB sections.
If the checklist in `kb/domicile.md` is missing or marked `TODO(verified-source)`, it returns `{available: false, items: []}`. Never invents items.

### FR-12  Pre-recorded Demo Mode
Offline demo mode operating from captured real responses in `static/cache.json`:
- Captured via `scripts/capture_demo_cache.py` by calling a running server against real cases.
- Toggle in web UI replays matching cached responses when enabled or upon network failure, with a visible "DEMO MODE: pre-recorded real responses" badge.
- Backend `DEMO_MODE` is disabled by default and cannot be enabled through the UI.

### FR-13  Dashboard – Stats
`GET /api/v1/dashboard/stats` returns top questions, language distribution,
outcome breakdown, and unanswered pending questions (all anonymised).

### FR-14  Dashboard – Approve
`POST /api/v1/dashboard/approve` lets a council user mark a pending question as
answered by writing a new KB entry draft.  Requires `ADMIN_TOKEN` env var.

### FR-15  Public Mode Protection (`PUBLIC_MODE`)
When `PUBLIC_MODE=true` (default `false`):
- `POST /api/v1/dashboard/approve` and `GET/POST /api/v1/dashboard/audit` (and `/dashboard/audit`) return 403 Forbidden regardless of token.
- Administrative modifications and seed/admin endpoints are disabled.
- Interactive documentation (`/docs`, `/redoc`) and API schema (`/openapi.json`) are disabled.
- CORS is restricted to same-origin.

### FR-16  In-Memory Client Rate Limiting
- Per client IP in-memory rate limiter with zero external dependencies.
- Configurable via `RATE_LIMIT_RPM` (default: 10 requests per minute).
- Enforces max audio payload size (`MAX_AUDIO_BYTES`, default 10 MB) and duration cap (30 s).
- Exceeding the rate limit returns `429 Too Many Requests` with a friendly multilingual message displayed in the UI.

### FR-17  Glass-Box Explainability Panel
A collapsible "How Ghag decided" section in the citizen UI for every `/ask` and `/check` result.
- Displays ONLY fields present in the verified API response:
  - Heard text (`transcript` / `heard`)
  - Detected language (`lang`)
  - Matched source citation (`source_id`, `source_url`, `last_verified`)
  - Grounding confidence (`confident: true/false` or verdict)
  - Handoff reason (`handoff_reason` if applicable)
  - Latency (`latency_ms`)
- Displays label: *"Try to make Ghag guess: it will refuse if the source doesn't cover it."*
- Strictly zero invented values.

## 3. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | End-to-end latency (audio path) | p95 ≤ 6 s on 4G / flaky WiFi |
| NFR-2 | End-to-end latency (text path) | p95 ≤ 3 s |
| NFR-3 | Pashto STT accuracy | WER ≤ 35 % on eval set (best-effort) |
| NFR-4 | Availability | Runs fully on a single laptop; no cloud DB |
| NFR-5 | Payload size | Audio response ≤ 300 KB (edge-tts compressed) |
| NFR-6 | Demo resilience | DEMO_MODE serves canned answers if Groq is down |

## 4. Acceptance Criteria

**FR-1 / AC-1**
Given a multipart POST with a valid audio file,
When the file is ≤ 10 MB and WAV/WebM,
Then a 200 response is returned within 6 s containing `transcript` and `answer`.

**FR-3 / AC-3**
Given the LLM prompt contains only KB context,
When the question is answerable from the KB,
Then `answer` text is grounded in KB content and `source_id` is non-null.

**FR-5 / AC-5**
Given a question with no matching KB entry,
When the LLM cannot ground an answer,
Then `outcome` = `handoff` and `answer` contains a referral message.

**FR-7 / AC-7**
Given any answered response,
When `sms_text` is included,
Then `len(sms_text) <= 160`.

**FR-8 / AC-8**
Given a request to `POST /api/v1/check` with text or audio describing possessed documents,
When verified checklist items D1–D6 exist,
Then `missing` is computed strictly in code as `required - matched`, and `verdict` matches the document completeness state.
When the checklist is marked `TODO(verified-source)`,
Then `verdict` is `"unavailable"` and no requirements are invented.

**FR-9 / AC-9**
Given a web client requesting `/`,
When index.html loads without internet/CDN access,
Then the UI displays with tabs, dark theme, audio recorder, transcript editor, and RTL support, without breaking API endpoints at `/api/v1/*`.

**FR-10 / AC-10**
Given a voice request with `lang_hint="ps"`,
When audio is sent to `POST /api/v1/ask` or `POST /api/v1/check`,
Then Whisper is invoked with `language="ps"` and a discrepancy log is generated if auto-detected language differs from the hint.

**FR-11 / AC-11**
Given a request to `GET /api/v1/checklist`,
When the KB checklist is unverified or marked TODO,
Then the response is `{available: false, items: []}`.
When verified items exist,
Then all items with stable IDs and multilingual labels are returned.

**FR-12 / AC-12**
Given `static/cache.json` containing captured real responses,
When "Demo Mode" is enabled in the UI,
Then questions matching cached cases replay immediately with a visible demo badge and zero server network requests.

**FR-13 / AC-13**
Given at least 1 interaction in the DB,
When `GET /api/v1/dashboard/stats` is called,
Then response includes `top_questions`, `language_split`, `outcome_counts`.

**FR-14 / AC-14**
Given a POST with an invalid `admin_token`,
When `/api/v1/dashboard/approve` is called,
Then a 401 is returned and no KB entry is written.

**FR-15 / AC-15**
Given `PUBLIC_MODE=true`,
When `/api/v1/dashboard/approve` or `/dashboard/audit` is called,
Then a 403 Forbidden is returned regardless of token, and `/docs` / `/openapi.json` return 404.

**FR-16 / AC-16**
Given client IP making requests above `RATE_LIMIT_RPM`,
When the limit is reached,
Then a 429 Too Many Requests response is returned with a friendly multilingual notice.

**FR-17 / AC-17**
Given any `/ask` or `/check` response in the web UI,
When the glass-box accordion is toggled,
Then it renders heard text, detected language, citation, confidence, handoff reason, and latency matching the exact JSON fields without hallucinated values.

## 5. Explicit Out-of-Scope (v1)

- Real telephony (IVR, SIP, PSTN)
- Real SMS gateway (Twilio, Jazz, Telenor, etc.)
- Authentication / user accounts
- Services other than Domicile Certificate
- Vector DB / semantic search (keyword FTS5 only for v1)
- Automated KB scraping / crawling
- Mobile native app
- Production deployment, SSL, reverse proxy
- Multi-district DC office contact directory

## 6. Open Questions

| # | Question | Owner | Deadline |
|---|----------|-------|----------|
| OQ-1 | Exact document checklist D1–D6 from official portal – confirmed? | Dev | 18 Nov |
| OQ-2 | Will venue WiFi allow outbound HTTPS to api.groq.com? | Dev | 20 Nov |
| OQ-3 | Pashto TTS voice available in edge-tts? (fallback to Urdu?) | Dev | 18 Nov |
| OQ-4 | ADMIN_TOKEN for dashboard approve – how is it shared at demo? | Dev | 20 Nov |
| OQ-5 | Maximum audio clip length for demo (suggested: 30 s hard cap) | Dev | 18 Nov |
