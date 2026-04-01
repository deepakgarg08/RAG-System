"""answer_metrics.py — Answer-level evaluation metrics.

Single responsibility: measure the quality of a generated answer relative to
the question it was asked and the context it was grounded in.

Metrics:
  answer_relevance   (0.0–1.0) — how well the answer addresses the question.
  completeness       (0.0–1.0) — fraction of expected content covered.
  hallucination_rate (0.0–1.0) — fraction of answer not grounded in context;
                                  derived as (1 – faithfulness), no extra LLM call.

# ============================================================
# DEMO MODE: OpenAI GPT-4o-mini — fast, cheap judge for answer relevance
# PRODUCTION SWAP → Azure OpenAI (AWS: Amazon Bedrock Claude):
#   Replace openai_client.chat.completions.create() with the AzureOpenAI client.
#   Model name "gpt-4o-mini" → your Azure deployment name.
#   Embedding fallback uses local bge-m3 — no swap needed for offline path.
# ============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def score_answer_relevance(
    question: str,
    answer: str,
    openai_client: Any | None,
    embed_fn: Callable[[list[str]], list[list[float]]] | None = None,
) -> tuple[float, str]:
    """Score how relevant the answer is to the question (0.0–1.0).

    Primary backend: GPT-4o-mini judge on a 0–10 scale (temperature=0).
    Fallback backend: cosine similarity between question and answer embeddings.

    Args:
        question: The original natural-language question.
        answer: The RAG system's generated answer.
        openai_client: An openai.OpenAI client, or None to force local fallback.
        embed_fn: Callable [[str, ...]] → [[float, ...]] using L2-normalised vectors.
                  Required for the embedding fallback path.

    Returns:
        Tuple of (score, source) where source is "llm" | "embed" | "error".
    """
    if not answer.strip() or not question.strip():
        return -1.0, "error"

    if openai_client is not None:
        score = _relevance_llm(question, answer, openai_client)
        if score >= 0.0:
            return score, "llm"

    if embed_fn is not None:
        score = _relevance_embed(question, answer, embed_fn)
        if score >= 0.0:
            return score, "embed"

    return -1.0, "error"


def _relevance_llm(question: str, answer: str, openai_client: Any) -> float:
    """GPT-4o-mini judge for answer relevance, normalised to 0.0–1.0."""
    prompt = (
        "You are an impartial evaluator assessing whether an AI assistant's answer "
        "directly and fully addresses the question asked.\n\n"
        f'QUESTION:\n"""{question[:500]}"""\n\n'
        f'ANSWER:\n"""{answer[:1500]}"""\n\n'
        "Task: Rate how well the ANSWER addresses the QUESTION on a scale from 0 to 10.\n"
        "- 10 = the answer directly, completely, and specifically addresses the question\n"
        "- 5  = partially relevant but misses key aspects or includes off-topic content\n"
        "- 0  = entirely irrelevant or does not address the question at all\n\n"
        "Reply with ONLY a single integer from 0 to 10. No explanation."
    )
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5,
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        score = int(raw)
        return round(min(max(score, 0), 10) / 10.0, 2)
    except Exception as exc:
        logger.warning("answer_relevance LLM judge failed: %s", exc)
        return -1.0


def _relevance_embed(
    question: str,
    answer: str,
    embed_fn: Callable[[list[str]], list[list[float]]],
) -> float:
    """Cosine similarity between question and answer embeddings (offline fallback)."""
    try:
        vecs = embed_fn([question, answer])
        q_vec, a_vec = vecs[0], vecs[1]
        dot = sum(x * y for x, y in zip(q_vec, a_vec))
        return round(max(0.0, min(1.0, dot)), 3)
    except Exception as exc:
        logger.warning("answer_relevance embedding fallback failed: %s", exc)
        return -1.0


def score_completeness(answer: str, expected_keywords: list[str]) -> float:
    """Score completeness as fraction of expected keyword phrases found in the answer.

    Extends the binary clause_hit check into a continuous 0.0–1.0 score.
    A score of 1.0 means every expected keyword phrase was found; 0.0 means none.
    This is a deterministic, heuristic metric — no LLM call required.

    Args:
        answer: The generated answer text.
        expected_keywords: List of keyword phrases expected to appear.

    Returns:
        Fraction of expected_keywords found (0.0–1.0), or -1.0 if no keywords given.
    """
    if not expected_keywords:
        return -1.0
    answer_lower = answer.lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
    return round(hits / len(expected_keywords), 3)


def score_hallucination_rate(faithfulness_score: float) -> float:
    """Derive hallucination rate as the complement of faithfulness (0.0–1.0).

    A faithfulness score of 0.8 implies 20% of the answer is not grounded in
    the retrieved context — a hallucination rate of 0.2.

    This is a derived metric that reuses the already-computed faithfulness score.
    No additional LLM call is needed.

    Args:
        faithfulness_score: The faithfulness score (0.0–1.0) or -1.0 on error.

    Returns:
        Hallucination rate (0.0–1.0), or -1.0 if faithfulness is unavailable.
    """
    if faithfulness_score < 0.0:
        return -1.0
    return round(1.0 - faithfulness_score, 3)
