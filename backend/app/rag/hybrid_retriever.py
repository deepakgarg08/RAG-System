"""
hybrid_retriever.py — BM25 + dense vector hybrid retrieval with Reciprocal Rank Fusion.

Runs BM25 (keyword) and dense vector (semantic) search in parallel over the same
ChromaDB collection, then merges the two result lists using Reciprocal Rank Fusion (RRF).

Why hybrid:
- Dense vectors handle paraphrased queries ("ending the agreement" ↔ "termination").
- BM25 handles exact legal terms that dense search can miss ("Riverty GmbH", "§12").
- RRF merges without requiring comparable score scales between the two methods.

# ============================================================
# DEMO MODE: BM25 index built in-memory over ChromaDB chunk texts.
# PRODUCTION SWAP → Azure AI Search hybrid mode (AWS: OpenSearch hybrid):
#   Azure AI Search runs BM25 + vector natively in a single API call.
#   No separate BM25 index needed — remove this file and update retriever.py.
# ============================================================
"""
import logging

import chromadb
from rank_bm25 import BM25Okapi

from app.config import settings
from app.rag.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "riverty_contracts"
_MIN_SIMILARITY = 0.40
_RRF_K = 60  # Standard RRF constant — higher K reduces impact of top-ranked items


class HybridRetriever:
    """Combines BM25 keyword search and dense vector search via Reciprocal Rank Fusion."""

    def __init__(self) -> None:
        """Initialise ChromaDB client, embedding service, and an empty BM25 cache."""
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_path)
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = EmbeddingService()
        self._bm25: BM25Okapi | None = None
        self._bm25_docs: list[dict] = []
        self._cached_count: int = -1  # -1 forces a build on first call
        logger.info(
            "HybridRetriever: connected to '%s' (%d chunks)",
            _COLLECTION_NAME,
            self._collection.count(),
        )

    # ── BM25 index management ──────────────────────────────────────────────────

    def _ensure_bm25_index(self) -> None:
        """Build or refresh the BM25 index when the collection has changed."""
        count = self._collection.count()
        if self._bm25 is not None and count == self._cached_count:
            return  # index is current

        if count == 0:
            self._bm25 = None
            self._bm25_docs = []
            self._cached_count = 0
            return

        raw = self._collection.get(include=["documents", "metadatas"])
        self._bm25_docs = [
            {"text": doc, "metadata": meta}
            for doc, meta in zip(raw["documents"], raw["metadatas"])
        ]
        tokenized = [chunk["text"].lower().split() for chunk in self._bm25_docs]
        self._bm25 = BM25Okapi(tokenized)
        self._cached_count = count
        logger.info("HybridRetriever: BM25 index built over %d chunks", count)

    # ── Individual retrievers ──────────────────────────────────────────────────

    def _dense_retrieve(self, query: str, top_k: int) -> list[dict]:
        """Dense vector retrieval from ChromaDB."""
        count = self._collection.count()
        if count == 0:
            return []
        query_vector = self._embedder.get_embedding(query)
        raw = self._collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )
        results: list[dict] = []
        for doc, meta, dist in zip(
            raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
        ):
            similarity = 1.0 - float(dist)
            if similarity < _MIN_SIMILARITY:
                continue
            results.append(
                {
                    "text": doc,
                    "source_file": meta.get("source_file", "unknown"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "total_chunks": meta.get("total_chunks", 0),
                    "page_number": meta.get("page_number", 1),
                    "language": meta.get("language", "unknown"),
                    "similarity_score": round(similarity, 4),
                }
            )
        return results

    def _bm25_retrieve(self, query: str, top_k: int) -> list[dict]:
        """BM25 keyword retrieval over the in-memory index."""
        if self._bm25 is None or not self._bm25_docs:
            return []
        tokenized_query = query.lower().split()
        scores = self._bm25.get_scores(tokenized_query)

        ranked = sorted(
            [(float(score), i) for i, score in enumerate(scores) if score > 0],
            key=lambda x: x[0],
            reverse=True,
        )[:top_k]

        results: list[dict] = []
        for bm25_score, idx in ranked:
            meta = self._bm25_docs[idx]["metadata"]
            results.append(
                {
                    "text": self._bm25_docs[idx]["text"],
                    "source_file": meta.get("source_file", "unknown"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "total_chunks": meta.get("total_chunks", 0),
                    "page_number": meta.get("page_number", 1),
                    "language": meta.get("language", "unknown"),
                    "similarity_score": 0.0,  # filled by RRF merge
                    "bm25_score": round(bm25_score, 4),
                }
            )
        return results

    # ── RRF merge ─────────────────────────────────────────────────────────────

    def _rrf_merge(
        self, dense: list[dict], bm25_results: list[dict], top_k: int
    ) -> list[dict]:
        """Merge two ranked lists with Reciprocal Rank Fusion.

        RRF score = Σ 1 / (k + rank_i) for each list i the chunk appears in.
        A chunk ranked 1st in both lists scores higher than one ranked 1st in just one.

        Args:
            dense:       Dense retrieval results, best-first.
            bm25_results: BM25 retrieval results, best-first.
            top_k:       How many merged results to return.

        Returns:
            Top-k chunks sorted by descending RRF score.
        """
        rrf_scores: dict[str, float] = {}
        best_chunk: dict[str, dict] = {}

        def _key(chunk: dict) -> str:
            return f"{chunk['source_file']}::{chunk['chunk_index']}"

        for rank, chunk in enumerate(dense, start=1):
            k = _key(chunk)
            rrf_scores[k] = rrf_scores.get(k, 0.0) + 1.0 / (_RRF_K + rank)
            best_chunk[k] = chunk

        for rank, chunk in enumerate(bm25_results, start=1):
            k = _key(chunk)
            rrf_scores[k] = rrf_scores.get(k, 0.0) + 1.0 / (_RRF_K + rank)
            if k not in best_chunk:
                best_chunk[k] = chunk

        ranked_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)[:top_k]
        merged = []
        for k in ranked_keys:
            chunk = best_chunk[k].copy()
            chunk["rrf_score"] = round(rrf_scores[k], 6)
            # Use dense similarity_score when available; BM25-only chunks keep 0.0
            if chunk.get("similarity_score", 0.0) == 0.0 and "bm25_score" in chunk:
                chunk["similarity_score"] = min(
                    0.41, round(chunk["bm25_score"] / 10.0, 4)
                )
            merged.append(chunk)

        logger.info(
            "HybridRetriever.rrf_merge: dense=%d bm25=%d → merged=%d",
            len(dense),
            len(bm25_results),
            len(merged),
        )
        return merged

    # ── Public interface ───────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = 8) -> list[dict]:
        """Hybrid BM25 + dense retrieval merged via RRF.

        Retrieves top_k * 2 candidates from each method before merging so the
        final merged list has enough candidates to pick the best top_k from.

        Args:
            query:  Plain-English question or search string.
            top_k:  Number of results to return after merging.

        Returns:
            List of chunk dicts ordered by RRF score, each with all metadata fields.
        """
        self._ensure_bm25_index()
        candidates = top_k * 2

        dense = self._dense_retrieve(query, candidates)
        bm25_results = self._bm25_retrieve(query, candidates)

        if not dense and not bm25_results:
            return []
        if not bm25_results:
            logger.debug("HybridRetriever: BM25 returned nothing — dense only")
            return dense[:top_k]
        if not dense:
            logger.debug("HybridRetriever: dense returned nothing — BM25 only")
            return bm25_results[:top_k]

        return self._rrf_merge(dense, bm25_results, top_k)
