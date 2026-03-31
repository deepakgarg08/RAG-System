"""metrics — pluggable evaluation metric functions for the Riverty RAG eval harness.

Each submodule covers one category:
  answer_metrics     — answer relevance, completeness, hallucination rate
  context_metrics    — context precision, context recall (LLM-judged)
  attribution_metrics— citation accuracy, citation coverage
  robustness_metrics — query consistency, noise sensitivity
  cost_metrics       — per-query token and USD cost estimation
"""

from metrics.answer_metrics import (
    score_answer_relevance,
    score_completeness,
    score_hallucination_rate,
)
from metrics.context_metrics import score_context_precision, score_context_recall
from metrics.attribution_metrics import score_citation_accuracy, score_citation_coverage
from metrics.robustness_metrics import (
    generate_paraphrases,
    inject_noise_chunks,
    score_noise_sensitivity,
    score_query_consistency,
)
from metrics.cost_metrics import aggregate_session_cost, estimate_query_cost

__all__ = [
    "score_answer_relevance",
    "score_completeness",
    "score_hallucination_rate",
    "score_context_precision",
    "score_context_recall",
    "score_citation_accuracy",
    "score_citation_coverage",
    "generate_paraphrases",
    "inject_noise_chunks",
    "score_noise_sensitivity",
    "score_query_consistency",
    "estimate_query_cost",
    "aggregate_session_cost",
]
