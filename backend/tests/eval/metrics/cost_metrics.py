"""cost_metrics.py — Per-query token and USD cost estimation.

Single responsibility: estimate the token cost of one RAG query using OpenAI
pricing for the models used in this evaluation system.

Token counting uses a fixed characters-per-token ratio (4 chars ≈ 1 token for
English/German legal text). For production billing accuracy, replace
``estimate_tokens`` with tiktoken:
    import tiktoken
    enc = tiktoken.encoding_for_model("gpt-4o-mini")
    tokens = len(enc.encode(text))

Pricing reference (as of 2025-Q1 — subject to change):
  gpt-4o-mini: $0.15 / 1M input tokens, $0.60 / 1M output tokens
  gpt-4o:      $5.00 / 1M input tokens, $15.00 / 1M output tokens
  bge-m3 (local embedding): $0.00 — runs on-device, no API cost

# ============================================================
# DEMO MODE: OpenAI GPT-4o-mini pricing for cost estimation
# PRODUCTION SWAP → Azure OpenAI (AWS: Amazon Bedrock):
#   Update MODEL_PRICING with Azure billing rates from your cost management portal.
#   Azure OpenAI charges per 1K tokens with deployment-specific pricing.
#   The estimate_query_cost() signature is unchanged — only pricing dict needs updating.
# ============================================================
"""

from __future__ import annotations

# Pricing table: USD per 1 million tokens (update when provider pricing changes)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {
        "input_per_million": 0.15,
        "output_per_million": 0.60,
    },
    "gpt-4o": {
        "input_per_million": 5.00,
        "output_per_million": 15.00,
    },
    "gpt-4o-mini-azure": {  # placeholder for Azure deployment
        "input_per_million": 0.165,
        "output_per_million": 0.66,
    },
}

# Characters-per-token approximation for English/German legal text
_CHARS_PER_TOKEN: int = 4


def estimate_tokens(text: str) -> int:
    """Estimate token count via the chars-per-token ratio heuristic.

    Args:
        text: Input text string.

    Returns:
        Estimated token count (minimum 1).
    """
    return max(1, len(text) // _CHARS_PER_TOKEN)


def estimate_query_cost(
    prompt_text: str,
    completion_text: str,
    model: str = "gpt-4o-mini",
) -> dict[str, float | int | str]:
    """Estimate the USD cost for a single LLM call.

    The cost covers both prompt (input) tokens and completion (output) tokens.
    Use the return dict's ``total_cost_usd`` field for per-query aggregation.

    Args:
        prompt_text: Full prompt sent to the model (concatenate system + user messages).
        completion_text: Full completion text received from the model.
        model: Model name — must be a key in ``MODEL_PRICING``; falls back to
               ``gpt-4o-mini`` pricing if not found.

    Returns:
        Dict with keys: model, prompt_tokens, completion_tokens, total_tokens,
        prompt_cost_usd, completion_cost_usd, total_cost_usd.
    """
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-4o-mini"])
    prompt_tokens = estimate_tokens(prompt_text)
    completion_tokens = estimate_tokens(completion_text)
    total_tokens = prompt_tokens + completion_tokens

    prompt_cost = (prompt_tokens / 1_000_000) * pricing["input_per_million"]
    completion_cost = (completion_tokens / 1_000_000) * pricing["output_per_million"]

    return {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "prompt_cost_usd": round(prompt_cost, 8),
        "completion_cost_usd": round(completion_cost, 8),
        "total_cost_usd": round(prompt_cost + completion_cost, 8),
    }


def aggregate_session_cost(per_query_costs: list[dict]) -> dict[str, float | int]:
    """Aggregate per-query cost dicts into a session-level cost summary.

    Args:
        per_query_costs: List of dicts returned by ``estimate_query_cost``.

    Returns:
        Dict with total tokens, total USD cost, and average cost per query.
    """
    if not per_query_costs:
        return {"query_count": 0, "total_tokens": 0, "total_cost_usd": 0.0, "avg_cost_per_query_usd": 0.0}

    total_tokens = sum(c.get("total_tokens", 0) for c in per_query_costs)
    total_cost = sum(c.get("total_cost_usd", 0.0) for c in per_query_costs)

    return {
        "query_count": len(per_query_costs),
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "avg_cost_per_query_usd": round(total_cost / len(per_query_costs), 8),
    }
