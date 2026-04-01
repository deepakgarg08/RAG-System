"""attribution_metrics.py — Source attribution (citation) metrics.

Single responsibility: measure how accurately the generated answer attributes
its claims to the retrieved source documents.

Metrics:
  citation_accuracy (0.0–1.0) — fraction of contract references in the answer
                                 that correspond to an actually retrieved chunk.
  citation_coverage (0.0–1.0) — fraction of retrieved source files that are
                                 explicitly mentioned in the answer.

Both metrics are deterministic heuristics — no LLM call required.

Design note:
  This system does not produce formal footnote citations. Instead, these
  metrics detect *implicit* source references by matching contract filename
  stems (e.g. "gdpr_strict", "missing_gdpr") found in the answer text against
  the set of retrieved chunk source files. Pattern: ``contract_<stem>.pdf``.
"""

from __future__ import annotations

import re


# Regex to find explicit PDF filename references in the answer text
_PDF_REF_PATTERN = re.compile(r"\b([a-z][a-z0-9_]{2,})(?:\.pdf)?\b", re.IGNORECASE)


def _stem_from(source_file: str) -> str:
    """Strip the .pdf extension and return the lowercase stem."""
    return re.sub(r"\.pdf$", "", source_file, flags=re.IGNORECASE).lower()


def _find_mentioned_sources(answer: str, candidate_sources: list[str]) -> set[str]:
    """Return the subset of ``candidate_sources`` whose stems appear in ``answer``.

    Matches both the full stem (e.g. "contract_gdpr_strict") and each
    underscore-separated token longer than 3 characters (e.g. "gdpr", "strict").

    Args:
        answer: Generated answer text.
        candidate_sources: Source file names to search for (e.g. "contract_gdpr_strict.pdf").

    Returns:
        Set of source file names from ``candidate_sources`` mentioned in the answer.
    """
    answer_lower = answer.lower()
    mentioned: set[str] = set()
    for src in candidate_sources:
        stem = _stem_from(src)
        if stem in answer_lower:
            mentioned.add(src)
            continue
        # Also check individual underscore-separated tokens (> 3 chars)
        for token in stem.split("_"):
            if len(token) > 3 and token in answer_lower:
                mentioned.add(src)
                break
    return mentioned


def score_citation_accuracy(answer: str, retrieved_chunks: list[dict]) -> float:
    """Score citation accuracy: are contract references in the answer actually retrieved?

    Extracts contract names mentioned in the answer and checks each one against
    the set of actually retrieved source files. A reference is accurate when the
    model cites a contract that was indeed retrieved. A reference to a contract
    NOT in the retrieved set indicates a hallucinated or fabricated source.

    Args:
        answer: Generated answer text.
        retrieved_chunks: Chunks returned by the retriever (with source_file metadata).

    Returns:
        Accuracy score (0.0–1.0), or -1.0 if no contract names are found in the answer.
    """
    if not retrieved_chunks:
        return -1.0

    retrieved_sources = list({c.get("source_file", "") for c in retrieved_chunks if c.get("source_file")})
    if not retrieved_sources:
        return -1.0

    # Find which retrieved sources are mentioned in the answer
    mentioned_from_retrieved = _find_mentioned_sources(answer, retrieved_sources)

    # Also scan for any contract-like patterns in the answer that might NOT match
    # any retrieved source (i.e. hallucinated references)
    answer_lower = answer.lower()
    retrieved_stems = {_stem_from(s) for s in retrieved_sources}
    hallucinated_refs = 0
    for match in _PDF_REF_PATTERN.finditer(answer_lower):
        token = match.group(1)
        # Only flag tokens that look like contract names (contain "_" or start with "contract")
        if "_" not in token and not token.startswith("contract"):
            continue
        if len(token) < 6:
            continue
        # Check if this token matches any retrieved stem or their sub-tokens
        matched_any = any(
            token in stem or stem in token or any(t == token for t in stem.split("_") if len(t) > 3)
            for stem in retrieved_stems
        )
        if not matched_any:
            hallucinated_refs += 1

    total_refs = len(mentioned_from_retrieved) + hallucinated_refs
    if total_refs == 0:
        return -1.0  # No contract references found — metric not applicable

    return round(len(mentioned_from_retrieved) / total_refs, 3)


def score_citation_coverage(answer: str, retrieved_chunks: list[dict]) -> float:
    """Score citation coverage: what fraction of retrieved sources appear in the answer?

    A score of 1.0 means every contract that contributed retrieved chunks is
    explicitly acknowledged in the answer. A score of 0.0 means no retrieved
    contracts are named.

    Note: low coverage is not necessarily bad — a concise answer may correctly
    summarise multiple contracts without naming each one. Use this metric to
    track transparency trends rather than as a hard quality gate.

    Args:
        answer: Generated answer text.
        retrieved_chunks: Chunks returned by the retriever (with source_file metadata).

    Returns:
        Coverage score (0.0–1.0), or -1.0 if no chunks were retrieved.
    """
    if not retrieved_chunks:
        return -1.0

    retrieved_sources = list({c.get("source_file", "") for c in retrieved_chunks if c.get("source_file")})
    if not retrieved_sources:
        return -1.0

    mentioned = _find_mentioned_sources(answer, retrieved_sources)
    return round(len(mentioned) / len(retrieved_sources), 3)
