"""
reranker.py — Cross-encoder reranking and MMR diversity filtering.

Two post-retrieval techniques that improve chunk quality before the LLM sees them:

1. rerank(): uses a cross-encoder model that reads the query and each chunk *together*
   (not as separate embeddings), producing a more accurate relevance score than
   cosine similarity from a bi-encoder. Model: cross-encoder/ms-marco-MiniLM-L-6-v2.

2. mmr_filter(): Maximal Marginal Relevance — selects a diverse set of chunks by
   penalising candidates that are too similar to already-selected ones.
   Prevents GPT-4o seeing 8 chunks that all repeat the same clause.

Both have safe fallbacks if the cross-encoder model is unavailable.
"""
import logging
import re

logger = logging.getLogger(__name__)

_CE_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_cross_encoder = None  # lazy-loaded on first use


def _get_cross_encoder():
    """Lazy-load the cross-encoder (downloads ~80 MB on first call, cached afterwards)."""
    global _cross_encoder
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder

            _cross_encoder = CrossEncoder(_CE_MODEL)
            logger.info("reranker: loaded cross-encoder model '%s'", _CE_MODEL)
        except Exception as exc:
            logger.warning(
                "reranker: could not load cross-encoder '%s' — %s. "
                "Falling back to similarity_score ordering.",
                _CE_MODEL,
                exc,
            )
    return _cross_encoder


def rerank(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    """Rerank retrieved chunks using a cross-encoder for higher accuracy.

    The cross-encoder model reads (query, chunk_text) pairs jointly, unlike
    a bi-encoder which encodes them independently. This gives it better
    precision on short legal clauses that share surface form with many queries.

    Falls back silently to descending similarity_score order if the model
    cannot be loaded (e.g. no internet connection during first download).

    Args:
        query:  The user's question.
        chunks: Retrieved chunk dicts (must contain "text" and "similarity_score").
        top_k:  Maximum number of chunks to return.

    Returns:
        Top-k chunks sorted by cross-encoder relevance score (descending).
        Each chunk gains a "ce_score" key with the raw cross-encoder score.
    """
    if not chunks:
        return []

    ce = _get_cross_encoder()
    if ce is None:
        return sorted(chunks, key=lambda c: c.get("similarity_score", 0.0), reverse=True)[
            :top_k
        ]

    pairs = [(query, chunk["text"]) for chunk in chunks]
    scores = ce.predict(pairs)

    for chunk, score in zip(chunks, scores):
        chunk["ce_score"] = round(float(score), 4)

    reranked = sorted(chunks, key=lambda c: c["ce_score"], reverse=True)
    logger.info(
        "rerank: %d candidates → top-%d (best ce_score=%.3f)",
        len(chunks),
        min(top_k, len(reranked)),
        reranked[0]["ce_score"] if reranked else 0.0,
    )
    return reranked[:top_k]


def _jaccard(text_a: str, text_b: str) -> float:
    """Token-level Jaccard similarity between two text strings.

    Args:
        text_a: First text.
        text_b: Second text.

    Returns:
        Jaccard similarity in [0, 1]. 0 = no overlap, 1 = identical token sets.
    """
    words_a = set(re.findall(r"\w+", text_a.lower()))
    words_b = set(re.findall(r"\w+", text_b.lower()))
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def mmr_filter(
    chunks: list[dict], top_k: int, lambda_param: float = 0.6
) -> list[dict]:
    """Select a diverse, relevant subset of chunks via Maximal Marginal Relevance.

    Iteratively picks the chunk that maximises:
        score = lambda * relevance_to_query - (1 - lambda) * max_similarity_to_selected

    Uses cross-encoder score (ce_score) if available, otherwise falls back to
    cosine similarity_score.  Inter-chunk similarity is measured by Jaccard
    overlap of token sets — no extra model needed.

    Args:
        chunks:       Candidate chunks (from rerank() or raw retrieval).
        top_k:        Maximum number of chunks to select.
        lambda_param: 0 = pure diversity, 1 = pure relevance. Default 0.6
                      keeps most-relevant chunks while removing near-duplicates.

    Returns:
        Up to top_k chunks, ordered by MMR selection priority.
    """
    if len(chunks) <= top_k:
        return chunks

    selected: list[dict] = []
    remaining = list(chunks)

    while len(selected) < top_k and remaining:
        best_score = -float("inf")
        best_idx = 0

        for i, candidate in enumerate(remaining):
            relevance = candidate.get("ce_score", candidate.get("similarity_score", 0.0))
            redundancy = (
                max(_jaccard(candidate["text"], s["text"]) for s in selected)
                if selected
                else 0.0
            )
            mmr_score = lambda_param * relevance - (1 - lambda_param) * redundancy

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i

        selected.append(remaining.pop(best_idx))

    logger.info("mmr_filter: %d → %d chunks (lambda=%.1f)", len(chunks), len(selected), lambda_param)
    return selected
