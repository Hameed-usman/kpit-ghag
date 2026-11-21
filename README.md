# Ghag – KP Public Services Voice Assistant

> **KP AI Innovation Challenge 2026** | Demo: Sat 21 Nov 2026

A voice-first assistant for Khyber Pakhtunkhwa residents seeking information
about government services — starting with the **Domicile Certificate**.
Answers only from verified government-sourced documents. Urdu / Pashto / English.

---

## Quick Start (4 steps)

```powershell
# 1. Clone and enter the project
cd d:\KPIT-GHAG

# 2. Create virtual environment and install dependencies
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell

# NOTE: On Windows systems with Application Control enabled, run pip through python:
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env
# Edit .env — set GROQ_API_KEY and ADMIN_TOKEN

# 4. Ingest KB and start the server
.venv\Scripts\python.exe scripts/ingest_kb.py
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open **http://localhost:8000** in your web browser.

> **Note on Microphone Access**: Modern browsers restrict `navigator.mediaDevices.getUserMedia` to Secure Contexts (`localhost`, `127.0.0.1`, or HTTPS). Always access the demo via `http://localhost:8000` or `http://127.0.0.1:8000`.

---

## Running Tests & Smoke Checks

On Windows PowerShell where `pytest.exe` may be restricted by Application Control, always run pytest as a module:

```powershell
# Run the complete automated test suite
.venv\Scripts\python.exe -m pytest -v

# Run the end-to-end smoke verification against a live server
.venv\Scripts\python.exe scripts/smoke.py
```

---

## UI Features & Manual Testing Guide

The web interface at `http://localhost:8000` provides:
1. **Language Hint Selector**: Choose `Auto-detect`, `Urdu (اردو)`, `Pashto (پښتو)`, or `English`. When set, hints Whisper STT to avoid dialect misdetection.
2. **Ask Tab (🗣️)**:
   - **Voice Recording**: Click "Press to Speak", speak for up to 30 seconds (visual countdown), click to stop.
   - **Text Fallback**: Type question in Urdu, Pashto, or English and submit.
   - **Editable Transcript**: Displays "I heard:" with transcribed text. Edit and click "Send edited text" to re-query without re-recording.
   - **Audio Playback**: Auto-plays response voice (Urdu: `ur-PK-AsadNeural`, Pashto: `ps-AF-GulNawazNeural`, English: `en-US-AriaNeural`). Replay button and fallback speech available.
   - **Simulated SMS**: Displays a mobile phone bubble with concise message formatted for 160-char SMS.
   - **Source Citation**: Direct link to verified KP government portal source.
   - **Handoff Card**: Amber warning box showing Citizen Facilitation Center guidance if question is out-of-scope or unverified.
3. **Missing-Document Check Tab (📋)**:
   - Compares declared documents against official government checklist.
   - Unverified checklist state (P-1) displays warning banner and safely disables checks to prevent misleading citizens.
4. **Council Governance & Analytics Dashboard (`/dashboard.html`)**:
   - Access via the **Dashboard** button in the header or `http://localhost:8000/dashboard.html`.
   - Real-time KPIs: total citizen interactions, verified answer rate, handoff rate, and average latency.
   - Language breakdown (Urdu, Pashto, English) and Top Inquiries table.
   - **Knowledge Expansion Approval Queue**: Review unanswered or handoff queries and officially approve grounded KB updates with source citations in 1 click.
5. **Offline Demo Cache Mode**:
   - Capture real verified responses for live stage demo safety:
     ```powershell
     .venv\Scripts\python.exe scripts/capture_demo_cache.py
     ```
   - In the UI header, toggle **Demo Cache** switch. The UI instantly responds using captured data without calling the internet or Groq API, marked with a prominent `DEMO MODE ACTIVE` badge.

---

## Demo Mode (no internet / venue fallback)

```bash
# In .env:
DEMO_MODE=true
```

The app serves canned responses from `eval/demo_fixture.json`.
No Groq API calls are made.

---

## Running Tests

```bash
pytest -v
```

## Running the Eval Set

```bash
# Server must be running first
python scripts/run_eval.py --url http://localhost:8000
```

---

## Project Structure

```
app/            FastAPI application (routers + services)
kb/             Verified government KB content (source of truth)
specs/          All specification documents
tests/          pytest test suite
eval/           Evaluation set + demo fixture
scripts/        KB ingestion + eval runner
static/         Frontend HTML/JS (served by FastAPI)
.env.example    Environment variable template
requirements.txt Python dependencies
```

## Key Specs

| Document | Purpose |
|----------|---------|
| [specs/constitution.md](specs/constitution.md) | Non-negotiable principles |
| [specs/spec.md](specs/spec.md) | User stories + requirements |
| [specs/api-contract.md](specs/api-contract.md) | API endpoint schemas |
| [specs/plan.md](specs/plan.md) | Architecture + decisions |
| [specs/tasks.md](specs/tasks.md) | Task checklist by chunk |

## Stack

- **Python 3.11** + FastAPI + Pydantic v2
- **Groq**: whisper-large-v3 (STT) + llama-3.3-70b-versatile (LLM)
- **edge-tts**: text-to-speech (Urdu/English; Pashto fallback)
- **SQLite** (stdlib FTS5): KB + interaction log
- **Plain HTML/JS**: zero build step frontend

---

*Do not commit `.env` to version control.*
