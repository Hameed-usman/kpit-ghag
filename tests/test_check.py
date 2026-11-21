"""
Tests for POST /api/v1/check — Chunk 3.

Covers:
- check unavailable when KB is unverified/TODO
- check ready (all required matched)
- check missing (set difference in code)
- check ambiguous (unsure verdict)
- unknown IDs dropped by code validation
- set difference invariant (never marks ready if required items missing)
- missing labels validated in output template
- audio upload processing
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from app.services.check_service import (
    ChecklistItem,
    LLMCheckMap,
    process_document_check,
)


@pytest.fixture
def mock_checklist():
    """Return a mock verified checklist with stable IDs D1..D6."""
    return [
        ChecklistItem(id="D1", label_en="Applicant CNIC", label_ur="شناختی کارڈ", required=True),
        ChecklistItem(id="D2", label_en="Parent CNIC", label_ur="والد کا شناختی کارڈ", required=True),
        ChecklistItem(id="D3", label_en="Passport Photographs", label_ur="تصاویر", required=True),
        ChecklistItem(id="D4", label_en="Proof of Residence", label_ur="رہائشی بل", required=True),
        ChecklistItem(id="D5", label_en="Affidavit", label_ur="بیان حلفی", required=True),
        ChecklistItem(id="D6", label_en="Previous Domicile Surrender", label_ur="این او سی", required=False),
    ]


class TestDocumentCheckLogic:
    """Unit tests for check_service pure logic and invariants."""

    @pytest.mark.asyncio
    async def test_check_unavailable_when_kb_unverified(self):
        """Constitution P-1: When checklist has TODO(verified-source), returns verdict='unavailable'."""
        resp = await process_document_check(
            heard="I have all my documents",
            lang_hint="en",
            is_verified_override=False,
            checklist_override=[],
        )
        assert resp.verdict == "unavailable"
        assert resp.matched == []
        assert resp.missing == []
        assert "I'm sorry" in resp.spoken

    @pytest.mark.asyncio
    async def test_check_ready_all_present(self, mock_checklist):
        """When all required documents are matched, verdict is 'ready' and missing is empty."""
        mock_map = LLMCheckMap(
            matched_ids=["D1", "D2", "D3", "D4", "D5"],
            ambiguous_ids=[],
            detected_lang="en",
        )
        with patch("app.services.check_service.map_caller_text_to_checklist", AsyncMock(return_value=mock_map)):
            resp = await process_document_check(
                heard="I have CNIC, parent CNIC, photos, residence proof and affidavit",
                lang_hint="en",
                checklist_override=mock_checklist,
            )
        assert resp.verdict == "ready"
        assert resp.missing == []
        assert "ready to apply" in resp.spoken

    @pytest.mark.asyncio
    async def test_check_missing_computed_in_code(self, mock_checklist):
        """Missing items are computed strictly in code: required - matched."""
        # User only has D1 and D3. Missing should be D2, D4, D5 (D6 is optional).
        mock_map = LLMCheckMap(
            matched_ids=["D1", "D3"],
            ambiguous_ids=[],
            detected_lang="en",
        )
        with patch("app.services.check_service.map_caller_text_to_checklist", AsyncMock(return_value=mock_map)):
            resp = await process_document_check(
                heard="I only have my CNIC and photos",
                lang_hint="en",
                checklist_override=mock_checklist,
            )
        assert resp.verdict == "missing"
        missing_ids = [m.id for m in resp.missing]
        assert missing_ids == ["D2", "D4", "D5"]
        # Ensure every missing label appears in the output
        for item in resp.missing:
            assert item.label in resp.spoken

    @pytest.mark.asyncio
    async def test_check_ambiguous_returns_unsure(self, mock_checklist):
        """If user statement is ambiguous, verdict is 'unsure'."""
        mock_map = LLMCheckMap(
            matched_ids=["D1"],
            ambiguous_ids=["D4"],
            detected_lang="en",
        )
        with patch("app.services.check_service.map_caller_text_to_checklist", AsyncMock(return_value=mock_map)):
            resp = await process_document_check(
                heard="I have CNIC and maybe some paper for home",
                lang_hint="en",
                checklist_override=mock_checklist,
            )
        assert resp.verdict == "unsure"
        assert "unclear" in resp.spoken.lower()

    @pytest.mark.asyncio
    async def test_unknown_id_dropped_by_validation(self, mock_checklist):
        """LLM hallucinating unknown IDs (e.g. D99, PASSPORT) must be dropped and ignored."""
        mock_map = LLMCheckMap(
            matched_ids=["D1", "D99", "INVALID_DOC"],
            ambiguous_ids=[],
            detected_lang="en",
        )
        with patch("app.services.check_service.map_caller_text_to_checklist", AsyncMock(return_value=mock_map)):
            resp = await process_document_check(
                heard="I have CNIC and a golden stamp",
                lang_hint="en",
                checklist_override=mock_checklist,
            )
        assert "D99" not in resp.matched
        assert "INVALID_DOC" not in resp.matched
        assert resp.matched == ["D1"]
        assert resp.verdict == "missing"

    @pytest.mark.asyncio
    async def test_set_difference_never_marks_ready_with_missing_item(self, mock_checklist):
        """Invariant: If ANY required item is missing, verdict can NEVER be 'ready'."""
        # Provide only subset of required items
        for subset in [["D1"], ["D1", "D2"], ["D1", "D2", "D3", "D4"]]:
            mock_map = LLMCheckMap(matched_ids=subset, ambiguous_ids=[], detected_lang="en")
            with patch("app.services.check_service.map_caller_text_to_checklist", AsyncMock(return_value=mock_map)):
                resp = await process_document_check(
                    heard="subset test",
                    lang_hint="en",
                    checklist_override=mock_checklist,
                )
            assert resp.verdict == "missing", f"Subset {subset} incorrectly marked as {resp.verdict}"
            assert len(resp.missing) > 0


class TestCheckRouter:
    """Integration tests for POST /api/v1/check."""

    def test_check_empty_input_returns_400(self, client):
        r = client.post("/api/v1/check", json={})
        assert r.status_code == 400

    def test_check_json_input_returns_200(self, client, mock_checklist):
        mock_map = LLMCheckMap(
            matched_ids=["D1", "D2", "D3", "D4", "D5"],
            ambiguous_ids=[],
            detected_lang="en",
        )
        with (
            patch("app.services.check_service.load_checklist", return_value=(mock_checklist, True)),
            patch("app.services.check_service.map_caller_text_to_checklist", AsyncMock(return_value=mock_map)),
            patch("app.routers.check.tts.synthesize", AsyncMock(return_value=b"\xff\xfb" * 10)),
        ):
            r = client.post(
                "/api/v1/check",
                json={"text": "I have all documents ready", "service": "domicile", "lang": "en"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["verdict"] == "ready"
        assert body["matched"] == ["D1", "D2", "D3", "D4", "D5"]
        assert body["audio_b64"] is not None

    def test_check_audio_input_returns_200(self, client, mock_checklist):
        from app.services.stt import STTText
        mock_map = LLMCheckMap(
            matched_ids=["D1"],
            ambiguous_ids=[],
            detected_lang="en",
        )
        fake_wav = b"RIFF" + b"\x00" * 80
        with (
            patch("app.routers.check.stt.transcribe", AsyncMock(return_value=STTText("I have my CNIC", "en"))),
            patch("app.services.check_service.load_checklist", return_value=(mock_checklist, True)),
            patch("app.services.check_service.map_caller_text_to_checklist", AsyncMock(return_value=mock_map)),
            patch("app.routers.check.tts.synthesize", AsyncMock(return_value=None)),
        ):
            r = client.post(
                "/api/v1/check",
                files={"audio": ("voice.wav", fake_wav, "audio/wav")},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["heard"] == "I have my CNIC"
        assert body["verdict"] == "missing"


class TestChecklistEndpoint:
    """Tests for GET /api/v1/checklist metadata endpoint."""

    def test_checklist_endpoint_unverified(self, client):
        """When KB checklist is unverified: returns available=False and empty items."""
        with patch("app.services.check_service.load_checklist", return_value=([], False)):
            r = client.get("/api/v1/checklist")
            assert r.status_code == 200
            data = r.json()
            assert data["available"] is False
            assert data["items"] == []

    def test_checklist_endpoint_verified_mock(self, client, mock_checklist):
        """When KB checklist is verified, returns available=True with items."""
        r = client.get("/api/v1/checklist")
        assert r.status_code == 200
        data = r.json()
        assert data["available"] is True
        assert len(data["items"]) >= 5

    def test_check_lang_hint_passed_to_stt(self, client, mock_checklist):
        """When lang_hint is provided to /check audio, it is passed to stt.transcribe."""
        from app.services.stt import STTText
        mock_map = LLMCheckMap(matched_ids=["D1"], ambiguous_ids=[], detected_lang="ur")
        mock_stt = AsyncMock(return_value=STTText("میرے پاس شناختی کارڈ ہے", "ur"))

        fake_wav = b"RIFF" + b"\x00" * 80
        with (
            patch("app.routers.check.stt.transcribe", mock_stt),
            patch("app.services.check_service.load_checklist", return_value=(mock_checklist, True)),
            patch("app.services.check_service.map_caller_text_to_checklist", AsyncMock(return_value=mock_map)),
            patch("app.routers.check.tts.synthesize", AsyncMock(return_value=None)),
        ):
            r = client.post(
                "/api/v1/check",
                files={"audio": ("voice.wav", fake_wav, "audio/wav")},
                data={"lang_hint": "ur"},
            )
        assert r.status_code == 200
        mock_stt.assert_called_once()
        _, kwargs = mock_stt.call_args
        assert kwargs.get("lang_hint") == "ur"

