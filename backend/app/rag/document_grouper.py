"""
document_grouper.py — Aggregates retriever chunks into document-level structures.

The retriever returns a flat list of chunks, each from a specific source file.
This module groups those chunks by document so the LLM can reason at the
document level rather than the chunk level.

Required for:
  MODE 2 — compare an uploaded document against stored contracts
  MODE 3 — cross-database queries ("which contracts are missing clause X?")
"""
import logging

logger = logging.getLogger(__name__)


def group_by_document(chunks: list[dict]) -> dict[str, dict]:
    """Group retriever chunks by their source document.

    Aggregates all chunks from the same source_file into a single entry,
    merging page numbers and tracking the best similarity score.

    Args:
        chunks: Flat list of retriever result dicts. Each dict must have:
                source_file, text, page_number, similarity_score.

    Returns:
        Dict keyed by filename. Each value contains:
        {
            "chunks":     list[dict] — all chunks from that document,
            "text":       str        — all chunk text concatenated (newline-separated),
            "pages":      list[int]  — sorted unique page numbers cited,
            "best_score": float      — highest similarity score across all chunks,
        }
        Ordered by best_score descending so the most relevant doc comes first.
    """
    docs: dict[str, dict] = {}

    for chunk in chunks:
        src = chunk.get("source_file", "unknown")
        if src not in docs:
            docs[src] = {
                "chunks": [],
                "pages": set(),
                "best_score": 0.0,
            }
        docs[src]["chunks"].append(chunk)
        docs[src]["pages"].add(chunk.get("page_number", 1))
        score = chunk.get("similarity_score", 0.0)
        if score > docs[src]["best_score"]:
            docs[src]["best_score"] = score

    # Finalise: convert page sets to sorted lists and build full text
    for data in docs.values():
        data["pages"] = sorted(data["pages"])
        data["text"] = "\n\n".join(c["text"] for c in data["chunks"])

    # Sort by relevance descending
    sorted_docs = dict(
        sorted(docs.items(), key=lambda kv: kv[1]["best_score"], reverse=True)
    )

    logger.info(
        "document_grouper: %d chunks → %d unique documents",
        len(chunks),
        len(sorted_docs),
    )
    return sorted_docs


def build_grouped_context(grouped: dict[str, dict]) -> str:
    """Format grouped document data as a labelled context string for the LLM.

    Each document is clearly separated and labelled with its filename and
    page numbers so the LLM can attribute findings to specific contracts.

    Args:
        grouped: Output of group_by_document().

    Returns:
        Multi-line string with one clearly labelled section per document.
        Example:
            === Document: contract_nda.pdf (Pages: 1, 3) ===
            ...clause text...

            === Document: contract_service.pdf (Pages: 2) ===
            ...clause text...
    """
    parts: list[str] = []
    for filename, data in grouped.items():
        page_label = ", ".join(str(p) for p in data["pages"])
        header = f"=== Document: {filename} (Pages: {page_label}) ==="
        parts.append(f"{header}\n{data['text']}")
    return "\n\n".join(parts)
