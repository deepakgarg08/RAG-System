"""
test_analysis.py — Tests for the document analysis layer.

Covers:
  - compliance_storage.py  — fail-safe external API call
  - document_grouper.py    — chunk aggregation by source document
  - document_analyzer.py   — MODE 1 (single), MODE 2 (compare), compliance check
  - analyze.py route        — POST /api/analyze (single + compare, SSE)
  - compliance.py route     — POST /api/compliance (JSON structured result)

All LLM and HTTP calls are mocked — tests run fully offline.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# ===========================================================================
# compliance_storage.py
# ===========================================================================

class TestComplianceStorage:
    """Tests for store_contract_in_api — fail-safe external archival."""

    def test_returns_false_when_url_not_configured(self, monkeypatch):
        """store_contract_in_api returns False when COMPLIANCE_API_URL is empty."""
        from app.config import settings
        monkeypatch.setattr(settings, "compliance_api_url", "")

        from app.etl.compliance_storage import store_contract_in_api
        result = store_contract_in_api("contract.pdf", b"%PDF-1.4")
        assert result is False

    def test_returns_true_on_successful_post(self, monkeypatch):
        """store_contract_in_api returns True when the API responds 2xx."""
        from app.config import settings
        monkeypatch.setattr(settings, "compliance_api_url", "http://fake-api/store")

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.raise_for_status = MagicMock()

        with patch("app.etl.compliance_storage.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            from app.etl.compliance_storage import store_contract_in_api
            result = store_contract_in_api("contract.pdf", b"%PDF-1.4")

        assert result is True
        mock_client.post.assert_called_once()

    def test_returns_false_on_timeout(self, monkeypatch):
        """store_contract_in_api returns False and logs warning on timeout."""
        import httpx
        from app.config import settings
        monkeypatch.setattr(settings, "compliance_api_url", "http://fake-api/store")

        with patch("app.etl.compliance_storage.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.TimeoutException("timed out")
            mock_client_cls.return_value = mock_client

            from app.etl.compliance_storage import store_contract_in_api
            result = store_contract_in_api("contract.pdf", b"%PDF-1.4")

        assert result is False

    def test_returns_false_on_http_error(self, monkeypatch):
        """store_contract_in_api returns False on HTTP error status."""
        import httpx
        from app.config import settings
        monkeypatch.setattr(settings, "compliance_api_url", "http://fake-api/store")

        mock_response = MagicMock()
        mock_response.status_code = 500
        http_error = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )

        with patch("app.etl.compliance_storage.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = http_error
            mock_client_cls.return_value = mock_client

            from app.etl.compliance_storage import store_contract_in_api
            result = store_contract_in_api("contract.pdf", b"%PDF-1.4")

        assert result is False

    def test_returns_false_on_unexpected_exception(self, monkeypatch):
        """store_contract_in_api returns False on any unexpected exception."""
        from app.config import settings
        monkeypatch.setattr(settings, "compliance_api_url", "http://fake-api/store")

        with patch("app.etl.compliance_storage.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = RuntimeError("network failure")
            mock_client_cls.return_value = mock_client

            from app.etl.compliance_storage import store_contract_in_api
            result = store_contract_in_api("contract.pdf", b"%PDF-1.4")

        assert result is False


# ===========================================================================
# document_grouper.py
# ===========================================================================

class TestDocumentGrouper:
    """Tests for group_by_document and build_grouped_context."""

    def _make_chunks(self) -> list[dict]:
        return [
            {"source_file": "a.pdf", "text": "GDPR clause here.", "page_number": 1, "similarity_score": 0.90},
            {"source_file": "a.pdf", "text": "Termination in 30 days.", "page_number": 2, "similarity_score": 0.75},
            {"source_file": "b.pdf", "text": "No termination clause.", "page_number": 1, "similarity_score": 0.60},
        ]

    def test_groups_chunks_by_source_file(self):
        from app.rag.document_grouper import group_by_document
        grouped = group_by_document(self._make_chunks())
        assert "a.pdf" in grouped
        assert "b.pdf" in grouped
        assert len(grouped["a.pdf"]["chunks"]) == 2
        assert len(grouped["b.pdf"]["chunks"]) == 1

    def test_merges_pages_per_document(self):
        from app.rag.document_grouper import group_by_document
        grouped = group_by_document(self._make_chunks())
        assert grouped["a.pdf"]["pages"] == [1, 2]
        assert grouped["b.pdf"]["pages"] == [1]

    def test_best_score_is_max_chunk_score(self):
        from app.rag.document_grouper import group_by_document
        grouped = group_by_document(self._make_chunks())
        assert grouped["a.pdf"]["best_score"] == pytest.approx(0.90)
        assert grouped["b.pdf"]["best_score"] == pytest.approx(0.60)

    def test_text_concatenates_all_chunks(self):
        from app.rag.document_grouper import group_by_document
        grouped = group_by_document(self._make_chunks())
        assert "GDPR clause here." in grouped["a.pdf"]["text"]
        assert "Termination in 30 days." in grouped["a.pdf"]["text"]

    def test_sorted_by_best_score_descending(self):
        from app.rag.document_grouper import group_by_document
        grouped = group_by_document(self._make_chunks())
        scores = [v["best_score"] for v in grouped.values()]
        assert scores == sorted(scores, reverse=True)

    def test_empty_input_returns_empty_dict(self):
        from app.rag.document_grouper import group_by_document
        assert group_by_document([]) == {}

    def test_build_grouped_context_includes_all_documents(self):
        from app.rag.document_grouper import group_by_document, build_grouped_context
        grouped = group_by_document(self._make_chunks())
        context = build_grouped_context(grouped)
        assert "a.pdf" in context
        assert "b.pdf" in context
        assert "GDPR clause here." in context

    def test_build_grouped_context_labels_pages(self):
        from app.rag.document_grouper import group_by_document, build_grouped_context
        grouped = group_by_document(self._make_chunks())
        context = build_grouped_context(grouped)
        assert "Pages: 1, 2" in context

    def test_build_grouped_context_empty_input(self):
        from app.rag.document_grouper import build_grouped_context
        assert build_grouped_context({}) == ""


# ===========================================================================
# document_analyzer.py — compliance response parser
# ===========================================================================

class TestComplianceParser:
    """Tests for _parse_compliance_response (internal parser)."""

    def test_parses_compliant_response(self):
        from app.rag.document_analyzer import _parse_compliance_response
        raw = (
            "COMPLIANCE STATUS: compliant\n\n"
            "VIOLATIONS:\n- None\n\n"
            "EXPLANATION:\nThe contract meets all requirements."
        )
        result = _parse_compliance_response(raw)
        assert result["compliant"] is True
        assert result["violations"] == []
        assert "meets all requirements" in result["explanation"]

    def test_parses_not_compliant_response(self):
        from app.rag.document_analyzer import _parse_compliance_response
        raw = (
            "COMPLIANCE STATUS: not compliant\n\n"
            "VIOLATIONS:\n- Missing termination clause\n- No GDPR clause\n\n"
            "EXPLANATION:\nThe contract has two critical gaps."
        )
        result = _parse_compliance_response(raw)
        assert result["compliant"] is False
        assert "Missing termination clause" in result["violations"]
        assert "No GDPR clause" in result["violations"]
        assert "critical gaps" in result["explanation"]

    def test_violations_excludes_none_items(self):
        from app.rag.document_analyzer import _parse_compliance_response
        raw = "COMPLIANCE STATUS: compliant\n\nVIOLATIONS:\n- None\n\nEXPLANATION:\nAll good."
        result = _parse_compliance_response(raw)
        assert result["violations"] == []

    def test_preserves_raw_text(self):
        from app.rag.document_analyzer import _parse_compliance_response
        raw = "COMPLIANCE STATUS: compliant\nVIOLATIONS:\n- None\nEXPLANATION:\nOK."
        result = _parse_compliance_response(raw)
        assert result["raw"] == raw


# ===========================================================================
# document_analyzer.py — async functions (LLM mocked)
# ===========================================================================

class TestDocumentAnalyzer:
    """Tests for analyze_single_document, check_compliance, compare_with_database."""

    def _make_mock_stream(self, tokens: list[str]):
        """Build a mock async iterator that yields token chunks."""
        async def _stream(*args, **kwargs):
            for t in tokens:
                chunk = MagicMock()
                chunk.choices = [MagicMock()]
                chunk.choices[0].delta.content = t
                yield chunk

        mock_response = MagicMock()
        mock_response.__aiter__ = lambda self: _stream()
        return mock_response

    @pytest.mark.asyncio
    async def test_analyze_single_streams_tokens_then_done(self):
        """analyze_single_document yields LLM tokens then [DONE]."""
        mock_stream = self._make_mock_stream(["Yes, ", "it contains ", "GDPR."])
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

        with patch("app.rag.document_analyzer._get_llm_client", return_value=mock_client):
            from app.rag.document_analyzer import analyze_single_document
            tokens = []
            async for t in analyze_single_document("Full contract text here.", "GDPR clause?"):
                tokens.append(t)

        assert "[DONE]" in tokens
        assert "Yes, " in tokens

    @pytest.mark.asyncio
    async def test_check_compliance_returns_structured_result(self):
        """check_compliance returns a parsed dict with compliant/violations/explanation."""
        raw_response = (
            "COMPLIANCE STATUS: not compliant\n\n"
            "VIOLATIONS:\n- Missing termination clause\n\n"
            "EXPLANATION:\nThe contract lacks a termination clause."
        )
        mock_message = MagicMock()
        mock_message.choices = [MagicMock()]
        mock_message.choices[0].message.content = raw_response
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_message)

        with patch("app.rag.document_analyzer._get_llm_client", return_value=mock_client):
            from app.rag.document_analyzer import check_compliance
            result = await check_compliance("Full contract text.", "1. Must have termination clause.")

        assert result["compliant"] is False
        assert "Missing termination clause" in result["violations"]
        assert "termination" in result["explanation"]

    @pytest.mark.asyncio
    async def test_compare_yields_no_results_message_on_empty_db(self, temp_chroma_dir, mock_openai_embedding):
        """compare_with_database yields a no-results message when DB is empty."""
        from app.rag.document_analyzer import compare_with_database
        tokens = []
        async for t in compare_with_database("Contract text.", "How does this compare?"):
            tokens.append(t)

        full_text = "".join(tokens)
        assert "No similar contracts found" in full_text
        assert "[DONE]" in tokens


# ===========================================================================
# POST /api/analyze — route tests
# ===========================================================================

class TestAnalyzeRoute:
    """Tests for POST /api/analyze (SSE streaming endpoint)."""

    @pytest.fixture
    def client(self, temp_chroma_dir):
        from app.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_analyze_returns_400_for_unsupported_type(self, client, tmp_path):
        """analyze returns 400 when the file type is not supported."""
        bad_file = tmp_path / "contract.docx"
        bad_file.write_bytes(b"DOCX content")
        with open(bad_file, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={"question": "What is this?", "mode": "single"},
                files={"file": ("contract.docx", f, "application/octet-stream")},
            )
        assert response.status_code == 400

    def test_analyze_returns_400_for_invalid_mode(self, client, sample_pdf_path):
        """analyze returns 400 when mode is not 'single' or 'compare'."""
        with open(sample_pdf_path, "rb") as f:
            response = client.post(
                "/api/analyze",
                data={"question": "What is this?", "mode": "invalid_mode"},
                files={"file": ("contract.pdf", f, "application/pdf")},
            )
        assert response.status_code == 400

    def test_analyze_single_streams_sse(self, client, nda_contract_path, mock_openai_embedding):
        """analyze in single mode returns SSE stream with tokens and [DONE]."""
        async def _fake_stream(document_text, question):
            yield "The contract contains "
            yield "a GDPR clause."
            yield "[DONE]"

        with patch("app.api.routes.analyze.analyze_single_document", side_effect=_fake_stream):
            with open(nda_contract_path, "rb") as f:
                response = client.post(
                    "/api/analyze",
                    data={"question": "Is there a GDPR clause?", "mode": "single"},
                    files={"file": ("contract_nda.pdf", f, "application/pdf")},
                )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        assert "data: [DONE]" in response.text

    def test_analyze_compare_streams_sse(self, client, nda_contract_path, mock_openai_embedding):
        """analyze in compare mode returns SSE stream."""
        async def _fake_stream(document_text, question):
            yield "Compared to stored contracts, "
            yield "this NDA has stricter GDPR terms."
            yield "[DONE]"

        with patch("app.api.routes.analyze.compare_with_database", side_effect=_fake_stream):
            with open(nda_contract_path, "rb") as f:
                response = client.post(
                    "/api/analyze",
                    data={"question": "How does this compare?", "mode": "compare"},
                    files={"file": ("contract_nda.pdf", f, "application/pdf")},
                )

        assert response.status_code == 200
        assert "data: [DONE]" in response.text


# ===========================================================================
# POST /api/compliance — route tests
# ===========================================================================

class TestComplianceRoute:
    """Tests for POST /api/compliance (JSON structured result endpoint)."""

    @pytest.fixture
    def client(self, temp_chroma_dir):
        from app.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_compliance_returns_400_for_unsupported_type(self, client, tmp_path):
        """compliance returns 400 for unsupported file types."""
        bad_file = tmp_path / "contract.txt"
        bad_file.write_bytes(b"plain text")
        with open(bad_file, "rb") as f:
            response = client.post(
                "/api/compliance",
                files={"file": ("contract.txt", f, "text/plain")},
            )
        assert response.status_code == 400

    def test_compliance_returns_structured_json(self, client, nda_contract_path):
        """compliance returns JSON with compliant, violations, explanation keys."""
        mock_result = {
            "compliant": True,
            "violations": [],
            "explanation": "The contract satisfies all requirements.",
            "raw": "COMPLIANCE STATUS: compliant\nVIOLATIONS:\n- None\nEXPLANATION:\nOK.",
        }

        with patch("app.api.routes.compliance.check_compliance", new=AsyncMock(return_value=mock_result)):
            with open(nda_contract_path, "rb") as f:
                response = client.post(
                    "/api/compliance",
                    files={"file": ("contract_nda.pdf", f, "application/pdf")},
                )

        assert response.status_code == 200
        data = response.json()
        assert "compliant" in data
        assert "violations" in data
        assert "explanation" in data
        assert isinstance(data["violations"], list)

    def test_compliance_with_custom_guidelines(self, client, nda_contract_path):
        """compliance accepts custom guidelines as a form field."""
        mock_result = {
            "compliant": False,
            "violations": ["Missing custom clause"],
            "explanation": "Does not satisfy custom guidelines.",
            "raw": "",
        }

        with patch("app.api.routes.compliance.check_compliance", new=AsyncMock(return_value=mock_result)) as mock_fn:
            with open(nda_contract_path, "rb") as f:
                response = client.post(
                    "/api/compliance",
                    data={"guidelines": "1. Must include custom clause."},
                    files={"file": ("contract_nda.pdf", f, "application/pdf")},
                )

        assert response.status_code == 200
        # Confirm the custom guidelines were passed through
        call_args = mock_fn.call_args
        assert "custom clause" in call_args.args[1]

    def test_compliance_uses_default_guidelines_when_none_provided(self, client, nda_contract_path):
        """compliance uses built-in default guidelines when guidelines field is omitted."""
        mock_result = {
            "compliant": True,
            "violations": [],
            "explanation": "All default checks passed.",
            "raw": "",
        }

        with patch("app.api.routes.compliance.check_compliance", new=AsyncMock(return_value=mock_result)) as mock_fn:
            with open(nda_contract_path, "rb") as f:
                response = client.post(
                    "/api/compliance",
                    files={"file": ("contract_nda.pdf", f, "application/pdf")},
                )

        assert response.status_code == 200
        # Default guidelines contain GDPR
        call_args = mock_fn.call_args
        assert "GDPR" in call_args.args[1]
