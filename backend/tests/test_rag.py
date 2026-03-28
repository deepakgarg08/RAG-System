"""
test_rag.py — Tests for the RAG query layer.
Covers: embedding generation, retriever top-K results, LangGraph agent node
routing, reasoner output, and formatter source attribution.
All OpenAI and ChromaDB calls are mocked.
"""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# embeddings.py
# ---------------------------------------------------------------------------

class TestEmbeddingService:
    """Tests for EmbeddingService class."""

    def test_get_embedding_returns_1536_floats(self, mock_openai_embeddings):
        """get_embedding must return exactly 1536 floats."""
        from app.rag.embeddings import EmbeddingService

        svc = EmbeddingService()
        result = svc.get_embedding("Sample contract text.")

        assert isinstance(result, list)
        assert len(result) == 1536
        assert all(isinstance(v, float) for v in result)

    def test_get_embedding_replaces_newlines(self, mock_openai_embeddings):
        """Newlines in input text are replaced before the API call."""
        from app.rag.embeddings import EmbeddingService

        svc = EmbeddingService()
        svc.get_embedding("line one\nline two\n")

        call_kwargs = mock_openai_embeddings.embeddings.create.call_args
        sent_input = call_kwargs.kwargs.get("input") or call_kwargs.args[0]
        assert "\n" not in sent_input

    def test_get_embedding_raises_on_api_error(self, mock_openai_embeddings):
        """get_embedding re-raises API errors for the caller to handle."""
        from app.rag.embeddings import EmbeddingService

        mock_openai_embeddings.embeddings.create.side_effect = RuntimeError("API down")
        svc = EmbeddingService()

        with pytest.raises(RuntimeError, match="API down"):
            svc.get_embedding("text")

    def test_get_embeddings_batch_processes_in_batches(self, mock_openai_embeddings):
        """get_embeddings_batch calls the API in chunks of ≤ 20."""
        from app.rag.embeddings import EmbeddingService, _BATCH_SIZE

        # Build 45 fake texts to force 3 batches
        texts = [f"text {i}" for i in range(45)]

        # Each batch call must return the right number of items
        def _make_response(texts_sent):
            items = []
            for idx, _ in enumerate(texts_sent):
                item = MagicMock()
                item.embedding = [0.1] * 1536
                item.index = idx
                items.append(item)
            resp = MagicMock()
            resp.data = items
            return resp

        mock_openai_embeddings.embeddings.create.side_effect = (
            lambda input, model: _make_response(input)
        )

        svc = EmbeddingService()
        results = svc.get_embeddings_batch(texts)

        assert len(results) == 45
        expected_calls = -(-len(texts) // _BATCH_SIZE)  # ceiling division
        assert mock_openai_embeddings.embeddings.create.call_count == expected_calls


# ---------------------------------------------------------------------------
# retriever.py
# ---------------------------------------------------------------------------

class TestContractRetriever:
    """Tests for ContractRetriever class."""

    def _make_retriever(self, temp_chroma_db, mock_openai_embeddings):
        """Construct a retriever pointing at the temp ChromaDB."""
        from app.rag.retriever import ContractRetriever
        return ContractRetriever()

    def _seed_collection(self, temp_chroma_db, mock_openai_embeddings, sample_chunks):
        """Load sample chunks into the temp ChromaDB via ChromaLoader."""
        from app.etl.loaders.chroma_loader import ChromaLoader
        loader = ChromaLoader()
        loader.load(sample_chunks)

    def test_get_collection_stats_returns_dict(self, temp_chroma_db, mock_openai_embeddings):
        """get_collection_stats returns total_documents and collection_name."""
        from app.rag.retriever import ContractRetriever

        retriever = ContractRetriever()
        stats = retriever.get_collection_stats()

        assert "total_documents" in stats
        assert "collection_name" in stats
        assert isinstance(stats["total_documents"], int)

    def test_retrieve_returns_empty_on_empty_collection(
        self, temp_chroma_db, mock_openai_embeddings
    ):
        """retrieve returns an empty list when no documents are stored."""
        from app.rag.retriever import ContractRetriever

        retriever = ContractRetriever()
        results = retriever.retrieve("any question")
        assert results == []

    def test_retrieve_result_schema(
        self, temp_chroma_db, mock_openai_embeddings, sample_chunks
    ):
        """Each result dict must have the required keys."""
        self._seed_collection(temp_chroma_db, mock_openai_embeddings, sample_chunks)
        from app.rag.retriever import ContractRetriever

        retriever = ContractRetriever()
        results = retriever.retrieve("German law")

        assert len(results) > 0
        required_keys = {"text", "source_file", "chunk_index", "language", "similarity_score"}
        for r in results:
            assert required_keys.issubset(r.keys()), f"Missing keys in result: {r}"

    def test_retrieve_respects_top_k(
        self, temp_chroma_db, mock_openai_embeddings, sample_chunks
    ):
        """retrieve must not return more results than top_k."""
        self._seed_collection(temp_chroma_db, mock_openai_embeddings, sample_chunks)
        from app.rag.retriever import ContractRetriever

        retriever = ContractRetriever()
        results = retriever.retrieve("termination", top_k=1)
        assert len(results) <= 1

    def test_retrieve_filters_low_similarity(
        self, temp_chroma_db, mock_openai_embeddings, sample_chunks
    ):
        """All returned results must have similarity_score >= 0.3."""
        self._seed_collection(temp_chroma_db, mock_openai_embeddings, sample_chunks)
        from app.rag.retriever import ContractRetriever

        retriever = ContractRetriever()
        results = retriever.retrieve("anything", top_k=10)
        for r in results:
            assert r["similarity_score"] >= 0.3, (
                f"Low-similarity result slipped through: {r}"
            )


# ---------------------------------------------------------------------------
# agent.py — node unit tests (no LangGraph graph invocation)
# ---------------------------------------------------------------------------

class TestAgentNodes:
    """Unit tests for individual agent node functions."""

    def test_formatter_appends_sources(self):
        """formatter must append a Sources line and populate state['sources']."""
        from app.rag.agent import formatter, AgentState

        state: AgentState = {
            "question": "Is there a GDPR clause?",
            "query_type": "find_clause",
            "retrieved_chunks": [
                {"source_file": "contract_a.pdf", "text": "...", "chunk_index": 0,
                 "language": "en", "similarity_score": 0.9},
                {"source_file": "contract_b.pdf", "text": "...", "chunk_index": 0,
                 "language": "de", "similarity_score": 0.8},
            ],
            "answer": "Yes, GDPR clause found.",
            "sources": [],
        }

        result = formatter(state)

        assert "contract_a.pdf" in result["answer"]
        assert "contract_b.pdf" in result["answer"]
        assert "**Sources:**" in result["answer"]
        assert set(result["sources"]) == {"contract_a.pdf", "contract_b.pdf"}

    def test_formatter_deduplicates_sources(self):
        """formatter must not repeat the same source filename twice."""
        from app.rag.agent import formatter, AgentState

        state: AgentState = {
            "question": "Any clause?",
            "query_type": "find_clause",
            "retrieved_chunks": [
                {"source_file": "contract_a.pdf", "text": "chunk 1",
                 "chunk_index": 0, "language": "en", "similarity_score": 0.9},
                {"source_file": "contract_a.pdf", "text": "chunk 2",
                 "chunk_index": 1, "language": "en", "similarity_score": 0.8},
            ],
            "answer": "Found something.",
            "sources": [],
        }

        result = formatter(state)
        assert result["sources"].count("contract_a.pdf") == 1

    def test_formatter_no_sources_on_empty_chunks(self):
        """formatter does not append Sources line when no chunks are present."""
        from app.rag.agent import formatter, AgentState

        state: AgentState = {
            "question": "Any?",
            "query_type": "find_clause",
            "retrieved_chunks": [],
            "answer": "No relevant contracts found.",
            "sources": [],
        }

        result = formatter(state)
        assert "**Sources:**" not in result["answer"]

    def test_retriever_node_sets_empty_answer_when_no_results(
        self, temp_chroma_db, mock_openai_embeddings
    ):
        """retriever_node sets answer='No relevant contracts found.' when nothing matches."""
        from app.rag.agent import retriever_node, AgentState

        state: AgentState = {
            "question": "Completely unrelated question",
            "query_type": "find_clause",
            "retrieved_chunks": [],
            "answer": "",
            "sources": [],
        }

        result = retriever_node(state)
        assert result["answer"] == "No relevant contracts found."
        assert result["retrieved_chunks"] == []


# ---------------------------------------------------------------------------
# agent.py — build_agent smoke test
# ---------------------------------------------------------------------------

def test_build_agent_compiles():
    """build_agent must return a compiled graph without errors."""
    from app.rag.agent import build_agent

    agent = build_agent()
    assert agent is not None
