"""
test_integration.py — End-to-end integration tests.
These tests run the FULL pipeline: ingest → store → query → answer.
OpenAI is still mocked (no API costs), but all internal components are real.
ChromaDB runs in a real temp directory (not mocked).

Run these separately from unit tests:
  pytest tests/test_integration.py -v -m integration

Fixtures used (defined in conftest.py):
  mock_openai_embedding — patches OpenAI embeddings to return fake vectors
  mock_openai_chat      — patches AsyncOpenAI chat completions
  temp_chroma_dir       — real ChromaDB + uploads in isolated temp directories
  nda_contract_path     — real PDF built from contract_nda_techcorp_2023.txt
  german_contract_path  — real PDF built from vertrag_dienstleistung_mueller_2024.txt
  sample_contracts_dir  — temp dir containing PDFs for all 4 sample contracts
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# TestFullIngestionFlow
# ---------------------------------------------------------------------------

class TestFullIngestionFlow:
    """Tests that verify the ingest → ChromaDB storage path end-to-end."""

    def test_ingest_then_count_increases(
        self,
        mock_openai_embedding,
        temp_chroma_dir,
        nda_contract_path,
    ):
        """Full flow: ingest one contract → document count increases from 0 to N.

        Verifies: pipeline → ChromaDB → get_document_count all connected correctly.
        """
        from app.etl.pipeline import IngestionPipeline

        pipeline = IngestionPipeline()

        # 1. Confirm count starts at 0 in the fresh temp ChromaDB
        assert pipeline.get_document_count() == 0

        # 2. Run full pipeline on nda_contract_path
        result = pipeline.ingest(str(nda_contract_path))

        # 3. Confirm pipeline reports success
        assert result["status"] == "success", f"Pipeline error: {result.get('error')}"
        assert result["chunks_created"] > 0

        # 4. Confirm ChromaDB count equals chunks_created
        assert pipeline.get_document_count() == result["chunks_created"]

    def test_ingest_all_sample_contracts(
        self,
        mock_openai_embedding,
        temp_chroma_dir,
        sample_contracts_dir,
    ):
        """Full flow: ingest all 4 sample contracts.

        Verifies: pipeline handles different content and languages without error.
        All must return status='success' and total chunk count must be > 0.
        """
        from app.etl.pipeline import IngestionPipeline

        pipeline = IngestionPipeline()
        pdf_files = sorted(sample_contracts_dir.glob("*.pdf"))
        assert len(pdf_files) == 4, f"Expected 4 PDFs, found: {[f.name for f in pdf_files]}"

        results = []
        for pdf_path in pdf_files:
            result = pipeline.ingest(str(pdf_path))
            results.append(result)

        # All must succeed
        failed = [r for r in results if r["status"] != "success"]
        assert not failed, f"Failed contracts: {[(r['filename'], r.get('error')) for r in failed]}"

        # Total chunks across all contracts must be > 0
        total_chunks = sum(r["chunks_created"] for r in results)
        assert total_chunks > 0

    def test_ingest_same_file_twice_is_idempotent(
        self,
        mock_openai_embedding,
        temp_chroma_dir,
        nda_contract_path,
    ):
        """Edge case: ingesting the same file twice must not duplicate chunks.

        Verifies: ChromaDB upsert behaviour — update not insert on duplicate ID.
        """
        from app.etl.pipeline import IngestionPipeline

        pipeline = IngestionPipeline()

        # First ingest
        result1 = pipeline.ingest(str(nda_contract_path))
        assert result1["status"] == "success"
        count_after_first = pipeline.get_document_count()

        # Second ingest of the same file
        result2 = pipeline.ingest(str(nda_contract_path))
        assert result2["status"] == "success"
        count_after_second = pipeline.get_document_count()

        # Count must be identical — upsert, not insert
        assert count_after_first == count_after_second, (
            f"Count grew from {count_after_first} to {count_after_second} — "
            "duplicate chunks were inserted instead of upserted"
        )


# ---------------------------------------------------------------------------
# TestFullQueryFlow
# ---------------------------------------------------------------------------

class TestFullQueryFlow:
    """Tests that verify the ChromaDB retrieval path after a real ingest."""

    def test_query_after_ingest_returns_answer(
        self,
        mock_openai_embedding,
        mock_openai_chat,
        temp_chroma_dir,
        nda_contract_path,
    ):
        """Full flow: ingest contract → query about its content → get answer.

        Verifies: retriever finds relevant chunks → answer built with source attribution.
        """
        from app.etl.pipeline import IngestionPipeline
        from app.rag.retriever import ContractRetriever
        from app.rag.agent import formatter, AgentState

        # 1. Ingest NDA contract (contains GDPR clause)
        pipeline = IngestionPipeline()
        result = pipeline.ingest(str(nda_contract_path))
        assert result["status"] == "success"

        # 2. Retrieve chunks for the query (real ChromaDB, mock embeddings)
        retriever = ContractRetriever()
        chunks = retriever.retrieve("Does this contract have a GDPR clause?")

        # 3. Verify retriever returns results from the NDA file
        assert len(chunks) > 0, "Retriever returned no chunks after ingest"
        sources = [c["source_file"] for c in chunks]
        assert any("nda" in s.lower() or "techcorp" in s.lower() for s in sources), (
            f"Expected NDA source in results, got: {sources}"
        )

        # 4. Build a formatted answer using the formatter node
        state: AgentState = {
            "question": "Does this contract have a GDPR clause?",
            "query_type": "find_clause",
            "retrieved_chunks": chunks,
            "answer": "Yes, the NDA contains a GDPR compliance clause (Article 28).",
            "sources": [],
        }
        formatted = formatter(state)

        assert formatted["answer"]
        assert len(formatted["sources"]) > 0
        assert "**Sources:**" in formatted["answer"]

    def test_query_on_empty_store_returns_not_found(
        self,
        mock_openai_embedding,
        mock_openai_chat,
        temp_chroma_dir,
    ):
        """Edge case: query against empty ChromaDB returns graceful 'not found' message.

        Verifies: system handles zero-result retrieval without crashing.
        """
        from app.rag.agent import retriever_node, AgentState

        state: AgentState = {
            "question": "Does this contract have a GDPR clause?",
            "query_type": "find_clause",
            "retrieved_chunks": [],
            "answer": "",
            "sources": [],
        }

        # Call retriever_node directly against the empty temp ChromaDB
        result = retriever_node(state)

        assert result["answer"] == "No relevant contracts found."
        assert result["retrieved_chunks"] == []

    def test_german_contract_retrievable_in_english_query(
        self,
        mock_openai_embedding,
        mock_openai_chat,
        temp_chroma_dir,
        german_contract_path,
    ):
        """Cross-language test: German contract ingested, queried in English.

        Verifies: retriever does not crash on a cross-language query.
        With mocked (identical) embeddings, semantic similarity is always 1.0,
        so stored German chunks are returned for any English query.

        Note: this is a best-effort structural test — real semantic similarity
        would require real embeddings, tested separately in evaluation (Prompt 4).
        """
        from app.etl.pipeline import IngestionPipeline
        from app.rag.retriever import ContractRetriever

        # 1. Ingest German contract
        pipeline = IngestionPipeline()
        result = pipeline.ingest(str(german_contract_path))
        assert result["status"] == "success", f"Pipeline error: {result.get('error')}"
        assert result["language"] == "de", (
            f"Expected German language detection, got: {result['language']}"
        )

        # 2. Query in English against the German content
        retriever = ContractRetriever()
        chunks = retriever.retrieve("GDPR compliance clause termination notice")

        # 3. With uniform fake embeddings, stored chunks must be returned
        assert isinstance(chunks, list)
        assert len(chunks) > 0, "No chunks returned after ingesting German contract"

        # 4. Verify returned chunks carry correct language metadata
        languages = {c["language"] for c in chunks}
        assert "de" in languages, f"Expected 'de' language in chunks, got: {languages}"


# ---------------------------------------------------------------------------
# TestAPIIntegration
# ---------------------------------------------------------------------------

class TestAPIIntegration:
    """Tests that verify the full HTTP layer wires correctly to pipeline and agent."""

    @pytest.mark.asyncio
    async def test_upload_then_query_via_http(
        self,
        mock_openai_embedding,
        mock_openai_chat,
        temp_chroma_dir,
        nda_contract_path,
    ):
        """Full HTTP flow: POST /api/ingest → POST /api/query → streaming response.

        Verifies: FastAPI routes correctly wire to pipeline and SSE generator.
        The ingest runs the real IngestionPipeline (real ChromaDB, mock embeddings).
        The query uses a mocked stream_query to avoid the LangGraph async/sync
        event-loop conflict in nested async contexts (tested in test_rag.py).
        """
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async def _fake_stream_query(question: str):
            """Simulate the SSE stream the agent would produce."""
            yield "Based on the uploaded contract, "
            yield "the NDA includes a GDPR compliance clause (Article 28)."
            yield "[DONE]"

        # Patch stream_query so the HTTP layer is tested without running LangGraph
        with patch("app.api.routes.query.stream_query", side_effect=_fake_stream_query):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:

                # --- Upload the NDA contract ---
                pdf_bytes = nda_contract_path.read_bytes()
                upload_response = await client.post(
                    "/api/ingest",
                    files={"file": ("contract_nda.pdf", pdf_bytes, "application/pdf")},
                )
                assert upload_response.status_code == 200, (
                    f"Ingest failed: {upload_response.text}"
                )
                ingest_data = upload_response.json()
                assert ingest_data["status"] == "success"
                assert ingest_data["chunks_created"] > 0
                assert ingest_data["filename"] == "contract_nda.pdf"

                # --- Query about the ingested contract ---
                query_response = await client.post(
                    "/api/query",
                    json={"question": "Does this contract have a GDPR clause?"},
                )
                assert query_response.status_code == 200
                assert "text/event-stream" in query_response.headers["content-type"]

                body = query_response.text
                assert "data: Based on the uploaded contract" in body
                assert "data: [DONE]" in body
