"""
eval_retrieve.py — POST /api/eval/retrieve

Returns raw retrieved chunks for a query without generating an answer.
Used exclusively by the evaluation harness (tests/eval/run_eval.py) to
compute IR metrics: Precision@K, Recall@K, MRR.

Runs the same retrieval pipeline as the query agent:
  HybridRetriever (BM25 + dense, RRF merged) → CrossEncoder reranker → MMR filter

NOT a production endpoint — exposed only to support offline evaluation.
No business logic lives here; delegation only.
"""
import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import rerank, mmr_filter

logger = logging.getLogger(__name__)

router = APIRouter()


class EvalRetrieveRequest(BaseModel):
    """Request body for the eval retrieve endpoint."""

    question: str = Field(..., min_length=3, max_length=500)
    top_k: int = Field(default=8, ge=1, le=20)


class EvalRetrieveResponse(BaseModel):
    """Response containing raw retrieved chunks for IR metric computation."""

    question: str
    chunks: list[dict]
    total_retrieved: int


@router.post("/eval/retrieve")
def eval_retrieve(request: EvalRetrieveRequest) -> EvalRetrieveResponse:
    """Return raw retrieved chunks for a question (evaluation use only).

    Runs HybridRetriever → CrossEncoder reranker → MMR filter — the same
    pipeline used inside the LangGraph agent — and returns the chunks
    directly instead of generating an LLM answer.

    Args:
        request: EvalRetrieveRequest with question and optional top_k.

    Returns:
        EvalRetrieveResponse with chunks list and total count.
        Each chunk contains: text, source_file, page_number, chunk_index,
        total_chunks, language, similarity_score.
    """
    retriever = HybridRetriever()
    candidates = retriever.retrieve(
        query=request.question,
        top_k=request.top_k * 2,
    )

    if not candidates:
        logger.info("eval_retrieve: no candidates for question=%r", request.question)
        return EvalRetrieveResponse(
            question=request.question,
            chunks=[],
            total_retrieved=0,
        )

    reranked = rerank(request.question, candidates, top_k=request.top_k)
    final = mmr_filter(reranked, top_k=request.top_k)

    logger.info(
        "eval_retrieve: question=%r → %d candidates → %d final chunks",
        request.question,
        len(candidates),
        len(final),
    )

    return EvalRetrieveResponse(
        question=request.question,
        chunks=final,
        total_retrieved=len(final),
    )
