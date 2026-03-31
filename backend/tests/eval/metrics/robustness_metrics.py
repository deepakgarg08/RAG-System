"""robustness_metrics.py — Robustness evaluation metrics.

Single responsibility: measure how stable the RAG system's output quality is
under query variation (paraphrase) and context noise (irrelevant chunk injection).

Metrics:
  query_consistency  (0.0–1.0) — semantic similarity of answers to paraphrased queries.
                                  Near 1.0 = system gives consistent answers regardless
                                  of surface phrasing.
  noise_sensitivity  (float)   — drop in faithfulness when irrelevant chunks are injected.
                                  Positive = degradation (higher = more sensitive).
                                  0.0 = fully robust.

These metrics make additional API calls per question and are therefore opt-in
via the ``--robustness`` flag in the evaluation harness.

# ============================================================
# DEMO MODE: OpenAI GPT-4o-mini for paraphrase generation;
#            bge-m3 cosine similarity for consistency scoring.
# PRODUCTION SWAP → Azure OpenAI (AWS: Bedrock Claude):
#   Replace model="gpt-4o-mini" with your Azure deployment name.
#   Consistency scoring (bge-m3) runs locally — no swap needed.
# ============================================================
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Query Consistency
# ---------------------------------------------------------------------------

_PARAPHRASE_PROMPT = (
    "Generate {n} paraphrased versions of the following question that preserve "
    "its exact meaning but use entirely different wording.\n\n"
    "ORIGINAL QUESTION:\n"
    '"""{question}"""\n\n'
    "Reply with ONLY the paraphrased questions, one per line, no numbering or prefixes."
)


def generate_paraphrases(
    question: str,
    n: int,
    openai_client: Any,
) -> list[str]:
    """Generate ``n`` paraphrase variants of a question using GPT-4o-mini.

    Temperature is set to 0.3 (slightly above 0) to produce lexically diverse
    paraphrases while remaining deterministic enough for reproducible evals.

    Args:
        question: The original question string.
        n: Number of paraphrases to generate.
        openai_client: An openai.OpenAI client instance.

    Returns:
        List of paraphrased question strings (may be shorter than ``n`` on failure).
    """
    prompt = _PARAPHRASE_PROMPT.format(n=n, question=question[:500])
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.3,
        )
        raw = resp.choices[0].message.content.strip()
        paraphrases = [line.strip() for line in raw.splitlines() if line.strip()]
        return paraphrases[:n]
    except Exception as exc:
        logger.warning("paraphrase generation failed: %s", exc)
        return []


def score_query_consistency(
    original_answer: str,
    paraphrase_answers: list[str],
    embed_fn: Callable[[list[str]], list[list[float]]],
) -> float:
    """Score query consistency as mean cosine similarity of paraphrase answers to original.

    Embeds the original answer and each paraphrase answer with the local bge-m3
    model, then returns the mean cosine similarity. A score near 1.0 means the
    system returns semantically equivalent answers regardless of question phrasing.

    Args:
        original_answer: The answer generated for the original question.
        paraphrase_answers: Answers generated for the paraphrased questions.
        embed_fn: Callable that encodes a list of strings into L2-normalised vectors.

    Returns:
        Mean consistency score (0.0–1.0), or -1.0 on failure.
    """
    if not paraphrase_answers or not original_answer.strip():
        return -1.0
    try:
        all_texts = [original_answer] + paraphrase_answers
        vecs = embed_fn(all_texts)
        orig_vec = vecs[0]
        sims = [
            max(0.0, min(1.0, sum(x * y for x, y in zip(orig_vec, v))))
            for v in vecs[1:]
        ]
        return round(sum(sims) / len(sims), 3)
    except Exception as exc:
        logger.warning("query_consistency scoring failed: %s", exc)
        return -1.0


# ---------------------------------------------------------------------------
# Noise Sensitivity
# ---------------------------------------------------------------------------

_NOISE_CHUNK_TEXT = (
    "This general provision applies to all standard commercial agreements and sets out "
    "the default terms for any business relationship between the parties. Either party "
    "may terminate the agreement by providing thirty (30) days written notice. Neither "
    "party shall be liable for indirect or consequential losses arising from the "
    "performance or non-performance of this agreement."
)


def inject_noise_chunks(
    retrieved_chunks: list[dict],
    noise_ratio: float = 0.3,
    seed: int = 42,
) -> list[dict]:
    """Inject synthetic noise by replacing a fraction of chunks with boilerplate.

    Replaces ``noise_ratio`` of the retrieved chunks with a generic, irrelevant
    contract boilerplate chunk. This simulates retrieval noise without requiring
    actual irrelevant documents to be ingested.

    The replacement is deterministic (``seed=42``) so that noise sensitivity
    scores are reproducible across runs.

    Args:
        retrieved_chunks: Original list of retrieved chunks.
        noise_ratio: Fraction (0.0–1.0) of chunks to replace with noise.
        seed: Random seed for deterministic injection.

    Returns:
        New chunk list with noise chunks inserted at random positions.
    """
    if not retrieved_chunks or noise_ratio <= 0.0:
        return list(retrieved_chunks)

    noise_chunk: dict = {
        "text": _NOISE_CHUNK_TEXT,
        "source_file": "noise_injection.pdf",
        "page_number": 0,
        "chunk_index": 0,
        "total_chunks": 1,
        "language": "en",
        "similarity_score": 0.0,
    }

    n_noise = max(1, math.floor(len(retrieved_chunks) * noise_ratio))
    chunks = list(retrieved_chunks)
    rng = random.Random(seed)
    replace_indices = rng.sample(range(len(chunks)), min(n_noise, len(chunks)))
    for idx in replace_indices:
        chunks[idx] = noise_chunk
    return chunks


def score_noise_sensitivity(
    base_faithfulness: float,
    noisy_faithfulness: float,
) -> float:
    """Compute noise sensitivity as the faithfulness drop under injected noise.

    Interpretation:
      0.0  — system is fully robust; noise had no effect.
      > 0  — positive value = degradation; higher = more sensitive.
      < 0  — (rare) noisy context paradoxically improved the score.

    Args:
        base_faithfulness: Faithfulness score on the clean retrieved context.
        noisy_faithfulness: Faithfulness score with noise chunks injected.

    Returns:
        Sensitivity delta (base – noisy), or -1.0 if either score is unavailable.
    """
    if base_faithfulness < 0.0 or noisy_faithfulness < 0.0:
        return -1.0
    return round(base_faithfulness - noisy_faithfulness, 3)
