"""context_metrics.py — Context-level evaluation metrics.

Single responsibility: measure the quality of the retrieved context relative
to the question, using LLM-based semantic judgement or ground-truth labels.

Metrics:
  context_precision (0.0–1.0) — fraction of retrieved chunks judged relevant.
  context_recall    (0.0–1.0) — whether the context is sufficient to answer fully.

When ground-truth relevance labels are available (Mode 2), context_precision
uses them directly (deterministic, no LLM cost). In all other cases both
metrics fall back to GPT-4o-mini judging (temperature=0).

# ============================================================
# DEMO MODE: OpenAI GPT-4o-mini — batched chunk relevance judge
# PRODUCTION SWAP → Azure OpenAI (AWS: Amazon Bedrock Claude):
#   Replace model="gpt-4o-mini" with your Azure deployment name.
#   Use AzureOpenAI client instead of openai.OpenAI.
# ============================================================
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def score_context_precision(
    question: str,
    retrieved_chunks: list[dict],
    openai_client: Any | None,
    relevant_set: set[tuple[str, int]] | None = None,
) -> tuple[float, str]:
    """Score context precision: fraction of retrieved chunks that are useful.

    When ``relevant_set`` is provided (ground-truth labels), matching is exact
    and deterministic — no LLM call is made. Otherwise, GPT-4o-mini judges
    each chunk's relevance in a single batched prompt.

    Args:
        question: The retrieval question.
        retrieved_chunks: Chunk dicts with text, source_file, page_number keys.
        openai_client: OpenAI client for LLM judging; ignored when relevant_set given.
        relevant_set: Optional set of (source_file, page_number) ground-truth pairs.

    Returns:
        Tuple of (score, source) where source is "gt" | "llm" | "error".
    """
    if not retrieved_chunks:
        return 0.0, "gt"

    # Deterministic path: use ground-truth labels (Mode 2 with relevant_chunks)
    if relevant_set is not None:
        hits = sum(
            1
            for c in retrieved_chunks
            if (c.get("source_file", ""), int(c.get("page_number", -1))) in relevant_set
        )
        return round(hits / len(retrieved_chunks), 4), "gt"

    # LLM path: judge each chunk's relevance in one batched call
    if openai_client is None:
        return -1.0, "error"

    return _context_precision_llm(question, retrieved_chunks, openai_client)


def _context_precision_llm(
    question: str,
    chunks: list[dict],
    openai_client: Any,
) -> tuple[float, str]:
    """Batch-judge chunk relevance with GPT-4o-mini in a single API call."""
    n = len(chunks)
    chunk_texts = "\n\n".join(
        f"[Chunk {i + 1}] ({c.get('source_file', 'unknown')}, p{c.get('page_number', '?')}):\n"
        f"{c.get('text', '')[:400]}"
        for i, c in enumerate(chunks)
    )
    prompt = (
        "You are an impartial evaluator. For each context chunk below, decide whether "
        "it contains information useful for answering the given question.\n\n"
        f'QUESTION:\n"""{question[:500]}"""\n\n'
        f"CONTEXT CHUNKS:\n{chunk_texts}\n\n"
        f"Task: Reply with EXACTLY {n} characters — one Y (relevant) or N (not relevant) "
        f"per chunk, in order, no spaces or other characters.\n"
        f"Example for {n} chunks: {'Y' * n}"
    )
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=n + 10,
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip().upper()
        judgements = [ch for ch in raw if ch in ("Y", "N")][:n]
        if not judgements:
            return -1.0, "error"
        score = round(sum(1 for j in judgements if j == "Y") / n, 4)
        return score, "llm"
    except Exception as exc:
        logger.warning("context_precision LLM judge failed: %s", exc)
        return -1.0, "error"


def score_context_recall(
    question: str,
    retrieved_chunks: list[dict],
    openai_client: Any | None,
) -> tuple[float, str]:
    """Score context recall: does the retrieved context contain enough to answer?

    Uses GPT-4o-mini to assess whether the provided context contains sufficient
    information to fully answer the question, on a 0–10 scale (temperature=0).

    Args:
        question: The original question.
        retrieved_chunks: Retrieved context chunks (text, source_file, page_number).
        openai_client: OpenAI client; required — metric returns -1.0 without it.

    Returns:
        Tuple of (recall_score, source) where source is "llm" | "error".
    """
    if openai_client is None or not retrieved_chunks:
        return -1.0, "error"

    context = "\n\n".join(
        f"[{c.get('source_file', 'unknown')} p{c.get('page_number', '?')}]:\n"
        f"{c.get('text', '')[:400]}"
        for c in retrieved_chunks[:8]
    )
    prompt = (
        "You are an impartial evaluator assessing whether the provided context "
        "contains sufficient information to answer the question completely.\n\n"
        f'QUESTION:\n"""{question[:500]}"""\n\n'
        f'CONTEXT:\n"""{context[:3000]}"""\n\n'
        "Task: Rate whether the CONTEXT contains all the information needed to answer "
        "the QUESTION on a scale from 0 to 10.\n"
        "- 10 = the context fully covers everything needed to answer the question\n"
        "- 5  = the context partially covers the question; some information is missing\n"
        "- 0  = the context is entirely insufficient to answer the question\n\n"
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
        return round(min(max(score, 0), 10) / 10.0, 2), "llm"
    except Exception as exc:
        logger.warning("context_recall LLM judge failed: %s", exc)
        return -1.0, "error"
