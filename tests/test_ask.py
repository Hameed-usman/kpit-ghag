"""
Tests for POST /api/v1/ask — Chunk 2.

All Groq and edge-tts calls are mocked.
Cases:
- valid answer
- handoff on confident=false
- handoff on invalid source_id
- invalid-JSON retry
- TTS failure still returns text
- text-only path
- CNIC redaction
"""
from __future__ import annotations

import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.llm import AnswerResult, grounded_answer


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mock_answer(
    answer: str = "Apply at cfc.kp.gov.pk.",
    source_id: str = "dom-channels",
    confident: bool = True,
    lang: str = "en",
    sms: str = "Apply at cfc.kp.gov.pk.",
) -> AnswerResult:
    return AnswerResult(
        lang=lang,  # type: ignore[arg-type]
        answer=answer,
        sms=sms,
        source_id=source_id,
        confident=confident,
    )


# ── Text Path (FR-1, FR-3, FR-4) ─────────────────────────────────────────────

class TestTextPath:
    def test_valid_text_answer(self, client):
        """User sends text question, gets grounded 200 answer."""
        mock_llm = AsyncMock(return_value=_mock_answer())
        mock_tts = AsyncMock(return_value=b"\xff\xfb\x90\x44" * 50)

        with (
            patch("app.routers.ask.llm.grounded_answer", mock_llm),
            patch("app.routers.ask.tts.synthesize", mock_tts),
        ):
            r = client.post("/api/v1/ask", data={"text": "How do I apply?", "lang": "en"})

        assert r.status_code == 200
        body = r.json()
        assert body["outcome"] == "answered"
        assert body["source_id"] == "dom-channels"
        assert body["transcript"] == "How do I apply?"
        assert body["lang"] == "en"
        assert len(body["sms_text"]) <= 160
        assert body["audio_b64"] is not None
        assert body["tts_available"] is True

    def test_no_input_returns_400(self, client):
        """Empty request without audio or text returns 400 Bad Request."""
        r = client.post("/api/v1/ask", data={})
        assert r.status_code == 400
        assert "Neither audio nor text" in r.json()["detail"]


# ── Audio Path (FR-1, FR-2) ──────────────────────────────────────────────────

class TestAudioPath:
    def test_audio_accepted_returns_200(self, client):
        """Audio file uploaded, transcribed, and answered."""
        from app.services.stt import STTText

        mock_stt = AsyncMock(return_value=STTText("How to apply for domicile?", lang="en"))
        mock_llm = AsyncMock(return_value=_mock_answer())
        mock_tts = AsyncMock(return_value=b"\xff\xfb" * 20)

        fake_wav = b"RIFF" + b"\x00" * 100
        with (
            patch("app.routers.ask.stt.transcribe", mock_stt),
            patch("app.routers.ask.llm.grounded_answer", mock_llm),
            patch("app.routers.ask.tts.synthesize", mock_tts),
        ):
            r = client.post(
                "/api/v1/ask",
                files={"audio": ("question.wav", fake_wav, "audio/wav")},
            )

        assert r.status_code == 200
        body = r.json()
        assert body["transcript"] == "How to apply for domicile?"
        assert body["outcome"] == "answered"

    def test_oversized_audio_returns_413(self, client):
        """Audio file > 10 MB returns 413."""
        big_audio = b"0" * (10 * 1024 * 1024 + 10)
        r = client.post(
            "/api/v1/ask",
            files={"audio": ("big.wav", big_audio, "audio/wav")},
        )
        assert r.status_code == 413

    def test_unsupported_audio_format_returns_422(self, client):
        """Unsupported file format returns 422."""
        r = client.post(
            "/api/v1/ask",
            files={"audio": ("sample.exe", b"fake binary", "application/octet-stream")},
        )
        assert r.status_code == 422


# ── Handoff Logic (FR-5, P-2, P-3) ───────────────────────────────────────────

class TestHandoff:
    def test_handoff_on_confident_false(self, client):
        """When LLM is unsure, system returns handoff in user's language."""
        mock_llm = AsyncMock(
            return_value=_mock_answer(
                answer="I don't know",
                source_id="",
                confident=False,
                lang="ur",
            )
        )
        with (
            patch("app.routers.ask.llm.grounded_answer", mock_llm),
            patch("app.routers.ask.tts.synthesize", AsyncMock(return_value=None)),
        ):
            r = client.post("/api/v1/ask", data={"text": "پاسپورٹ کیسے بنے گا؟", "lang": "ur"})

        assert r.status_code == 200
        body = r.json()
        assert body["outcome"] == "handoff"
        assert body["source_id"] is None
        assert body["source_url"] is None
        assert "معذرت" in body["answer"]

    def test_handoff_on_invalid_source_id(self, client):
        """Never trust LLM: if LLM claims confident but provides an invalid source_id, force handoff."""
        mock_llm = AsyncMock(
            return_value=_mock_answer(
                answer="Fake requirement",
                source_id="invented-fake-id",
                confident=True,
                lang="en",
            )
        )
        with (
            patch("app.routers.ask.llm.grounded_answer", mock_llm),
            patch("app.routers.ask.tts.synthesize", AsyncMock(return_value=None)),
        ):
            r = client.post("/api/v1/ask", data={"text": "Fee details please?", "lang": "en"})

        assert r.status_code == 200
        body = r.json()
        assert body["outcome"] == "handoff"
        assert body["source_id"] is None
        assert "I'm sorry" in body["answer"]


# ── TTS Failure Graceful Degradation (P-7, FR-6) ─────────────────────────────

class TestTTSFailure:
    def test_tts_failure_still_returns_text(self, client):
        """If edge-tts raises exception or fails, return 200 with text and audio_b64=null."""
        mock_llm = AsyncMock(return_value=_mock_answer())
        mock_tts = AsyncMock(return_value=None)  # TTS returned None

        with (
            patch("app.routers.ask.llm.grounded_answer", mock_llm),
            patch("app.routers.ask.tts.synthesize", mock_tts),
        ):
            r = client.post("/api/v1/ask", data={"text": "Where to submit?", "lang": "en"})

        assert r.status_code == 200
        body = r.json()
        assert body["outcome"] == "answered"
        assert body["answer"] == "Apply at cfc.kp.gov.pk."
        assert body["audio_b64"] is None
        assert body["tts_available"] is False


# ── CNIC Redaction (P-4c) ────────────────────────────────────────────────────

class TestCNICRedaction:
    def test_redact_cnic_unit(self):
        from app.services.logstore import redact_cnic

        text_dashed = "My CNIC is 17301-1234567-1."
        text_raw = "My CNIC is 1730112345671."
        assert redact_cnic(text_dashed) == "My CNIC is [CNIC-REDACTED]."
        assert redact_cnic(text_raw) == "My CNIC is [CNIC-REDACTED]."

    def test_cnic_never_stored_in_db(self, client):
        """End-to-end: question containing CNIC has CNIC redacted in database queries table."""
        from app.config import settings

        mock_llm = AsyncMock(return_value=_mock_answer())
        mock_tts = AsyncMock(return_value=None)

        with (
            patch("app.routers.ask.llm.grounded_answer", mock_llm),
            patch("app.routers.ask.tts.synthesize", mock_tts),
        ):
            r = client.post(
                "/api/v1/ask",
                data={"text": "Check status for CNIC 17301-7654321-9 please", "lang": "en"},
            )

        assert r.status_code == 200

        conn = sqlite3.connect(settings.db_path)
        rows = conn.execute("SELECT question_text FROM queries").fetchall()
        conn.close()

        stored_texts = [row[0] for row in rows]
        assert any("[CNIC-REDACTED]" in t for t in stored_texts)
        assert not any("17301-7654321-9" in t for t in stored_texts)


# ── Invalid JSON Retry (FR-3, LLM Service) ───────────────────────────────────

class TestInvalidJSONRetry:
    @pytest.mark.asyncio
    async def test_invalid_json_retry_succeeds(self):
        """When LLM returns malformed JSON on attempt 1, it retries and parses attempt 2."""
        from app.services.kb import KnowledgeBase

        kb = KnowledgeBase.load()

        attempt = 0

        async def fake_create(*args, **kwargs):
            nonlocal attempt
            attempt += 1
            choice = MagicMock()
            if attempt == 1:
                choice.message.content = "INVALID NON-JSON OUTPUT {{"
            else:
                choice.message.content = json.dumps({
                    "lang": "en",
                    "answer": "Submit application to the DC office.",
                    "sms": "Submit to DC office.",
                    "source_id": "dom-procedure",
                    "confident": True,
                })
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        with patch("groq.resources.chat.completions.AsyncCompletions.create", fake_create):
            result = await grounded_answer("How to submit?", kb, "en")

        assert attempt == 2
        assert result.confident is True
        assert result.source_id == "dom-procedure"
        assert "DC office" in result.answer


# ── KB Integrity Checks (P-1, FR-3, FR-4) ────────────────────────────────────

class TestKBIntegrity:
    def test_todo_sections_are_ignored(self):
        """Sections marked TODO(verified-source) must not be loaded."""
        from app.services.kb import KnowledgeBase

        kb = KnowledgeBase.load()
        assert "dom-sample-unverified" not in kb.sections
        assert "dom-authority" in kb.sections
        assert "dom-channels" in kb.sections
        assert "dom-procedure" in kb.sections
        assert "dom-tracking" in kb.sections
        assert "dom-important-notes" in kb.sections
        assert "dom-fees" in kb.sections

    def test_source_id_validity(self):
        """source_id_valid only accepts verified loaded IDs."""
        from app.services.kb import KnowledgeBase

        kb = KnowledgeBase.load()
        assert kb.source_id_valid("dom-authority") is True
        assert kb.source_id_valid("dom-channels") is True
        assert kb.source_id_valid("dom-fees") is True
        assert kb.source_id_valid("dom-sample-unverified") is False
        assert kb.source_id_valid("random-fake-id") is False
        assert kb.source_id_valid("") is False
        assert kb.source_id_valid(None) is False


# ── Pashto TTS & Audio Formats & Health Tests ─────────────────────────────────

class TestPashtoTTS:
    def test_pashto_tts_unavailable_still_returns_text(self, client):
        """If Pashto TTS fails/unavailable, /ask returns 200 with text and tts_available=false."""
        mock_llm = AsyncMock(
            return_value=_mock_answer(
                answer="تاسو کولی شئ د DC دفتر ته عریضه ورکړئ.",
                source_id="dom-procedure",
                confident=True,
                lang="ps",
                sms="د DC دفتر ته عریضه ورکړئ.",
            )
        )
        with (
            patch("app.routers.ask.llm.grounded_answer", mock_llm),
            patch("app.routers.ask.tts.synthesize", AsyncMock(return_value=None)),  # TTS failure
        ):
            r = client.post("/api/v1/ask", data={"text": "څنګه غوښتنلیک ورکړم؟", "lang": "ps"})

        assert r.status_code == 200
        body = r.json()
        assert body["outcome"] == "answered"
        assert body["lang"] == "ps"
        assert "DC دفتر" in body["answer"]
        assert body["audio_b64"] is None
        assert body["tts_available"] is False


class TestAudioFormats:
    def test_ask_accepts_m4a_format(self, client):
        """Groq Whisper supports m4a. /ask must accept .m4a."""
        from app.services.stt import STTText

        mock_stt = AsyncMock(return_value=STTText("How to apply?", lang="en"))
        mock_llm = AsyncMock(return_value=_mock_answer())
        mock_tts = AsyncMock(return_value=None)

        with (
            patch("app.routers.ask.stt.transcribe", mock_stt),
            patch("app.routers.ask.llm.grounded_answer", mock_llm),
            patch("app.routers.ask.tts.synthesize", mock_tts),
        ):
            r = client.post(
                "/api/v1/ask",
                files={"audio": ("voice.m4a", b"fake-m4a-data", "audio/m4a")},
            )
        assert r.status_code == 200
        assert r.json()["transcript"] == "How to apply?"

    def test_ask_accepts_flac_format(self, client):
        """Groq Whisper supports flac. /ask must accept .flac."""
        from app.services.stt import STTText

        mock_stt = AsyncMock(return_value=STTText("How to apply?", lang="en"))
        mock_llm = AsyncMock(return_value=_mock_answer())
        mock_tts = AsyncMock(return_value=None)

        with (
            patch("app.routers.ask.stt.transcribe", mock_stt),
            patch("app.routers.ask.llm.grounded_answer", mock_llm),
            patch("app.routers.ask.tts.synthesize", mock_tts),
        ):
            r = client.post(
                "/api/v1/ask",
                files={"audio": ("voice.flac", b"fLaC" + b"\x00" * 40, "audio/flac")},
            )
        assert r.status_code == 200


class TestHealthEndpoint:
    def test_health_reports_tts_per_language(self, client):
        """GET /api/v1/health reports tts dictionary per language."""
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        data = r.json()
        assert "tts" in data
        assert isinstance(data["tts"], dict)
        assert "ur" in data["tts"]
        assert "ps" in data["tts"]
        assert "en" in data["tts"]
        assert data["tts"]["ur"] is True
        assert data["tts"]["en"] is True


class TestStaticAndHint:
    def test_static_index_served_at_root(self, client):
        """GET / serves static/index.html without shadowing /api/v1 routes."""
        r = client.get("/")
        assert r.status_code == 200
        assert "Ghag" in r.text
        assert "text/html" in r.headers.get("content-type", "")

    def test_api_routes_not_shadowed(self, client):
        """Ensure /api/v1/health and /openapi.json are accessible."""
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/openapi.json").status_code == 200

    def test_lang_hint_passed_to_stt(self, client):
        """When lang_hint is provided to /ask, it is passed to stt.transcribe."""
        from app.services.stt import STTText

        mock_stt = AsyncMock(return_value=STTText("څنګه درخواست ورکړم؟", lang="ps"))
        mock_llm = AsyncMock(return_value=_mock_answer(lang="ps"))
        mock_tts = AsyncMock(return_value=None)

        fake_wav = b"RIFF" + b"\x00" * 80
        with (
            patch("app.routers.ask.stt.transcribe", mock_stt),
            patch("app.routers.ask.llm.grounded_answer", mock_llm),
            patch("app.routers.ask.tts.synthesize", mock_tts),
        ):
            r = client.post(
                "/api/v1/ask",
                files={"audio": ("voice.wav", fake_wav, "audio/wav")},
                data={"lang_hint": "ps"},
            )

        assert r.status_code == 200
        mock_stt.assert_called_once()
        _, kwargs = mock_stt.call_args
        assert kwargs.get("lang_hint") == "ps"


