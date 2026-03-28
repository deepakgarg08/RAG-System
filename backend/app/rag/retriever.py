"""
retriever.py — Semantic retrieval from the vector store.
Embeds the query, queries ChromaDB for the top-K most similar chunks,
and returns chunks with their metadata and similarity scores for the agent.
"""
import logging

import chromadb

from app.config import settings
from app.rag.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

# ============================================================
# DEMO MODE: ChromaDB — zero config, persists to local disk
# PRODUCTION SWAP → Azure AI Search (AWS: OpenSearch / Kendra):
#   Replace ContractRetriever with AzureSearchRetriever
#   Azure AI Search adds hybrid search (keyword + vector), enterprise RBAC,
#   and horizontal scale — required for multi-tenant production at Riverty
#   See .claude/skills/swap-to-azure.md for step-by-step migration
# ============================================================

_COLLECTION_NAME = "riverty_contracts"
_MIN_SIMILARITY = 0.3


class ContractRetriever:
    """Semantic retriever that queries ChromaDB for relevant contract chunks."""

    def __init__(self) -> None:
        """Initialise ChromaDB client and EmbeddingService."""
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_path)
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = EmbeddingService()
        logger.info(
            "ContractRetriever: connected to collection '%s' (%d docs)",
            _COLLECTION_NAME,
            self._collection.count(),
        )

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """Find the most semantically similar chunks to the query.

        Embeds the query, searches ChromaDB, converts cosine distances to
        similarity scores, and filters out results below MIN_SIMILARITY.

        Args:
            query: Plain-English question or search string.
            top_k: Maximum number of results to return.

        Returns:
            List of result dicts ordered by descending similarity, each with:
            {
                "text": str,
                "source_file": str,
                "chunk_index": int,
                "language": str,
                "similarity_score": float,  # 0.0 (dissimilar) to 1.0 (identical)
            }
        """
        query_vector = self._embedder.get_embedding(query)

        raw = self._collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, max(self._collection.count(), 1)),
            include=["documents", "metadatas", "distances"],
        )

        documents = raw["documents"][0] if raw["documents"] else []
        metadatas = raw["metadatas"][0] if raw["metadatas"] else []
        distances = raw["distances"][0] if raw["distances"] else []

        results: list[dict] = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            # ChromaDB cosine distance ∈ [0, 2]; similarity = 1 - distance
            # (distance 0 = identical, distance 1 = orthogonal, distance 2 = opposite)
            similarity = 1.0 - float(dist)
            if similarity < _MIN_SIMILARITY:
                continue
            results.append(
                {
                    "text": doc,
                    "source_file": meta.get("source_file", "unknown"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "language": meta.get("language", "unknown"),
                    "similarity_score": round(similarity, 4),
                }
            )

        top_score = results[0]["similarity_score"] if results else 0.0
        logger.info(
            "ContractRetriever.retrieve: query=%r → %d results (top score=%.3f)",
            query,
            len(results),
            top_score,
        )
        return results

    def get_collection_stats(self) -> dict:
        """Return basic statistics about the vector collection.

        Returns:
            Dict with total_documents count and collection_name.
        """
        return {
            "total_documents": self._collection.count(),
            "collection_name": _COLLECTION_NAME,
        }
