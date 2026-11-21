# Ghag – API Contract

> Version 1.0 | Base path: `/api/v1`

---

## POST /api/v1/ask

Ask a question by voice or text.

**Request** – `multipart/form-data` OR `application/x-www-form-urlencoded`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `audio` | File | if no `text` | WAV, WebM, MP3, M4A, OGG, FLAC ≤ 10 MB |
| `text` | string | if no `audio` | pre-typed question |
| `lang` | string | no | backward-compatible language code |
| `lang_hint` | string | no | `auto` (default), `ur`, `ps`, `en`. Passed to Whisper when not auto |

**Response 200**
```json
{
  "transcript": "string",
  "lang": "ur|ps|en",
  "answer": "string",
  "outcome": "answered|handoff",
  "source_id": "string|null",
  "source_url": "string|null",
  "sms_text": "string (≤160 chars)",
  "audio_b64": "string|null",
  "tts_available": true
}
```

**Error cases**

| Code | Condition |
|------|-----------|
| 400 | Neither `audio` nor `text` provided |
| 413 | Audio file > 10 MB |
| 422 | Unsupported audio format or malformed form data |
| 503 | Groq unavailable and `DEMO_MODE=false` |

---

## POST /api/v1/check

Compare documents the user says they have against the verified checklist.

**Request** – `application/json` OR `multipart/form-data`

*JSON Request:*
```json
{
  "text": "I have my CNIC and passport photos",
  "service": "domicile",
  "lang": "en"
}
```

*Multipart Request:*
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `audio` | File | if no `text` | WAV, WebM, MP3, M4A, OGG, FLAC ≤ 10 MB |
| `text` | string | if no `audio` | Spoken or typed user explanation of what documents they possess |
| `service` | string | no | Service name (default: `"domicile"`) |
| `lang` | string | no | Backward-compatible language code |
| `lang_hint` | string | no | `auto` (default), `ur`, `ps`, `en`. Passed to Whisper when not auto |

**Response 200**
```json
{
  "lang": "ur|ps|en",
  "heard": "string – transcription or input text",
  "matched": ["D1", "D3"],
  "missing": [
    {"id": "D2", "label": "Parent / Guardian CNIC"},
    {"id": "D4", "label": "Proof of residence"}
  ],
  "verdict": "ready|missing|unsure|unavailable",
  "spoken": "string – spoken response template in user language",
  "sms": "string (≤160 chars) – summary in user language",
  "source_id": "dom-checklist",
  "tts_available": true,
  "audio_b64": "string|null"
}
```

**Verdict Values**
- `"ready"`: All required documents present, none ambiguous.
- `"missing"`: One or more required documents are missing.
- `"unsure"`: Caller statements were ambiguous or unclear.
- `"unavailable"`: Checklist in KB is unverified or missing (Constitution P-1).

**Error cases**

| Code | Condition |
|------|-----------|
| 400 | Neither `audio` nor `text` provided |
| 413 | Audio file > 10 MB |
| 422 | Unsupported audio format or malformed body |

---

## GET /api/v1/checklist

Retrieve the official document checklist for domicile applications.

**Response 200**
```json
{
  "available": false,
  "items": []
}
```
*When verified checklist exists:*
```json
{
  "available": true,
  "items": [
    {
      "id": "D1",
      "label_en": "Applicant CNIC / Form-B",
      "label_ur": "درخواست گزار کا شناختی کارڈ یا فارم بی",
      "label_ps": "د غوښتونکي پېژندپاڼه یا ب-فارم",
      "required": true
    }
  ]
}
```

---

## GET /api/v1/dashboard/stats

Return anonymised analytics for the council dashboard.
No auth required (read-only, anonymous).

**Response 200**
```json
{
  "total_interactions": 42,
  "outcome_counts": {"answered": 35, "handoff": 7},
  "language_split": {"ur": 20, "ps": 15, "en": 7},
  "top_questions": [
    {"question_hash": "abc123", "preview": "string (first 60 chars)", "count": 8}
  ],
  "pending_unanswered": [
    {"id": 1, "preview": "string", "lang": "ur", "count": 3}
  ]
}
```

> **Note:** `preview` is a truncated, non-identifying fragment of the question.
> Raw question text is never stored; preview is generated at log time.

---

## POST /api/v1/dashboard/approve

Approve a pending question by writing a KB answer draft.

**Request** – `application/json`
```json
{
  "pending_id": 1,
  "answer_text": "string",
  "source_url": "https://cfc.kp.gov.pk/",
  "admin_token": "string"
}
```

**Response 200**
```json
{
  "status": "approved",
  "kb_entry_id": "string"
}
```

**Error cases**

| Code | Condition |
|------|-----------|
| 401 | `admin_token` does not match `ADMIN_TOKEN` env var |
| 404 | `pending_id` not found in pending table |
| 422 | `answer_text` empty or `source_url` invalid |

---

## GET /api/v1/health

Liveness + readiness probe. Used by demo-mode detection in the UI.

**Response 200**
```json
{
  "status": "ok",
  "demo_mode": false,
  "groq_reachable": true,
  "tts_available": true,
  "tts": {
    "ur": true,
    "ps": true,
    "en": true
  },
  "kb_entries": 5,
  "db_ok": true
}
```

**Response 503** – returned when `db_ok: false` or critical init failed.

---

## Common Headers

| Header | Value |
|--------|-------|
| `Content-Type` | As specified per endpoint above |
| `X-Request-ID` | Optional; echoed in response for tracing |

## Versioning

All paths are prefixed `/api/v1/`.  Breaking changes bump to `/api/v2/`.
