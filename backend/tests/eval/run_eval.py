"""
run_eval.py — Evaluation harness for the Riverty RAG contract review system.

Covers all three operational modes without RAGAS:

  Mode 1 — Single-doc analysis  : Upload a temp contract, ask questions about it.
                                   Metrics: contract_hit, clause_hit, faithfulness, latency.

  Mode 2 — Database query        : Ask questions against the persistent vector DB.
                                   Metrics: contract_hit, clause_hit, Precision@K,
                                   Recall@K, MRR, faithfulness, latency.

  Mode 3 — Compare uploaded vs DB: Upload a temp contract, compare it against the DB.
                                   Metrics: keyword_hit, comparison_hit, faithfulness, latency.

Faithfulness has two backends (automatic fallback):
  1. OpenAI GPT-4o-mini LLM judge (0–10 scale) — most accurate; requires OPENAI_API_KEY.
  2. Local embedding cosine similarity (BAAI/bge-m3) — offline fallback; always available.
     Computes mean cosine similarity between context chunk embeddings and the answer
     embedding as a lightweight proxy for how grounded the answer is in the context.

IR metrics (Precision@K, Recall@K, MRR) use the /api/eval/retrieve endpoint which
runs the same HybridRetriever → CrossEncoder reranker → MMR pipeline as the agent.

Usage:
    cd backend
    python tests/eval/run_eval.py [--base-url http://localhost:8000] [--skip-ingest]
                                  [--modes 1,2,3] [--top-k 8] [--output-dir DIR]

Environment variables:
    BASE_URL      — API base URL (default: http://localhost:8000)
    SKIP_INGEST   — set to "1" to skip re-ingestion
    OPENAI_API_KEY — optional; if set, uses GPT-4o-mini judge; otherwise uses local embeddings
"""

# ============================================================
# DEMO MODE: direct HTTP calls to local FastAPI + OpenAI GPT-4o-mini
# PRODUCTION SWAP → Azure API Management + Azure OpenAI (AWS: API Gateway + Bedrock):
#   Replace BASE_URL with the Azure APIM endpoint.
#   Add an Authorization header with the APIM subscription key.
#   Replace openai.OpenAI() with azure_openai client using AZURE_OPENAI_ENDPOINT.
# ============================================================

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

# Load .env so OPENAI_API_KEY and other secrets are available even when
# running this script directly (outside the FastAPI process which loads
# them via pydantic_settings).
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)  # override=False: real env vars win
except ImportError:
    pass  # python-dotenv not installed — env vars must be set manually

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVAL_DIR.parent.parent
GROUND_TRUTH_PATH = EVAL_DIR / "ground_truth.json"
PERSISTENT_CONTRACTS_DIR = BACKEND_DIR / "uploads" / "synthetic_legal_db" / "persistent_contracts"
TEMP_CONTRACTS_DIR = BACKEND_DIR / "data" / "synthetic_legal_db" / "temp_uploads"

# Ensure the co-located metrics package is importable when running as a script
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

# ---------------------------------------------------------------------------
# Extended metrics (new — pluggable metric modules)
# ---------------------------------------------------------------------------
from metrics.answer_metrics import (  # noqa: E402
    score_answer_relevance,
    score_completeness,
    score_hallucination_rate,
)
from metrics.context_metrics import score_context_precision, score_context_recall  # noqa: E402
from metrics.attribution_metrics import score_citation_accuracy, score_citation_coverage  # noqa: E402
from metrics.cost_metrics import aggregate_session_cost, estimate_query_cost  # noqa: E402
from metrics.robustness_metrics import (  # noqa: E402
    generate_paraphrases,
    inject_noise_chunks,
    score_noise_sensitivity,
    score_query_consistency,
)

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def ingest_contract(base_url: str, pdf_path: Path) -> dict[str, Any]:
    """POST a PDF to /api/ingest and return the parsed JSON response.

    Args:
        base_url: API base URL (e.g. http://localhost:8000).
        pdf_path: Local path to the PDF file.

    Returns:
        Parsed JSON dict from the IngestResponse schema.
    """
    import requests

    with open(pdf_path, "rb") as f:
        resp = requests.post(
            f"{base_url}/api/ingest",
            files={"file": (pdf_path.name, f, "application/pdf")},
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


def query_and_collect(base_url: str, question: str) -> tuple[str, float]:
    """POST a question to /api/query, consume the SSE stream, return full answer + latency.

    Args:
        base_url: API base URL.
        question: Plain-English question about the contracts in the DB.

    Returns:
        Tuple of (full_answer_text, latency_seconds).
    """
    import requests

    t0 = time.perf_counter()
    resp = requests.post(
        f"{base_url}/api/query",
        json={"question": question},
        stream=True,
        timeout=120,
    )
    resp.raise_for_status()

    tokens: list[str] = []
    for raw_line in resp.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        if line.startswith("data:"):
            content = line[len("data:"):].strip()
            if content == "[DONE]":
                break
            tokens.append(content)

    latency = time.perf_counter() - t0
    answer = " ".join(tokens).strip()
    return answer, latency


def analyze_and_collect(
    base_url: str,
    pdf_path: Path,
    question: str,
    mode: str,
) -> tuple[str, float]:
    """POST a PDF + question to /api/analyze, collect SSE stream, return answer + latency.

    Args:
        base_url: API base URL.
        pdf_path: Path to the temp contract PDF.
        question: Question about the document.
        mode: "single" (Mode 1) or "compare" (Mode 3).

    Returns:
        Tuple of (full_answer_text, latency_seconds).
    """
    import requests

    t0 = time.perf_counter()
    with open(pdf_path, "rb") as f:
        resp = requests.post(
            f"{base_url}/api/analyze",
            data={"question": question, "mode": mode},
            files={"file": (pdf_path.name, f, "application/pdf")},
            stream=True,
            timeout=180,
        )
    resp.raise_for_status()

    tokens: list[str] = []
    for raw_line in resp.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        if line.startswith("data:"):
            content = line[len("data:"):].strip()
            if content == "[DONE]":
                break
            tokens.append(content)

    latency = time.perf_counter() - t0
    answer = " ".join(tokens).strip()
    return answer, latency


def eval_retrieve(base_url: str, question: str, top_k: int) -> list[dict]:
    """POST to /api/eval/retrieve and return the list of retrieved chunks.

    Args:
        base_url: API base URL.
        question: The retrieval query.
        top_k: Maximum number of chunks to retrieve.

    Returns:
        List of chunk dicts (text, source_file, page_number, …).
    """
    import requests

    resp = requests.post(
        f"{base_url}/api/eval/retrieve",
        json={"question": question, "top_k": top_k},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json().get("chunks", [])


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def check_contract_hit(answer: str, expected_contracts: list[str]) -> bool:
    """Return True if any expected contract stem appears in the answer (case-insensitive).

    Also checks each underscore-separated token longer than 3 characters.
    e.g. "contract_missing_gdpr" → also checks "missing", "gdpr", "contract".

    Args:
        answer: Full response text from the RAG system.
        expected_contracts: List of expected contract filename stems (no .pdf).

    Returns:
        True if any expected contract is referenced in the answer.
    """
    answer_lower = answer.lower()
    for stem in expected_contracts:
        if stem.lower() in answer_lower:
            return True
        for part in stem.split("_"):
            if len(part) > 3 and part.lower() in answer_lower:
                return True
    return False


def check_clause_hit(answer: str, expected_keywords: list[str]) -> bool:
    """Return True if any expected keyword phrase appears in the answer (case-insensitive).

    Args:
        answer: Full response text from the RAG system.
        expected_keywords: List of keyword strings expected in the answer.

    Returns:
        True if at least one keyword is found.
    """
    answer_lower = answer.lower()
    return any(kw.lower() in answer_lower for kw in expected_keywords)


def check_absent_keywords(answer: str, absent_keywords: list[str]) -> bool:
    """Return True if NONE of the absent keywords appear in the answer.

    Args:
        answer: Full response text.
        absent_keywords: Keywords that must NOT appear.

    Returns:
        True if all absent keywords are missing (good — the model didn't hallucinate them).
    """
    answer_lower = answer.lower()
    return not any(kw.lower() in answer_lower for kw in absent_keywords)


def compute_ir_metrics(
    retrieved_chunks: list[dict],
    relevant_chunks: list[dict],
    k: int,
) -> dict[str, float]:
    """Compute Precision@K, Recall@K, and MRR from retrieved chunks vs ground truth.

    Relevance is determined by (source_file, page_number) matching the
    ground-truth relevant_chunks list. Page numbers are stored as integers in
    ground truth (pages: [1, 2]) and as integers in chunk metadata
    (page_number: 1).

    Args:
        retrieved_chunks: Chunks returned by /api/eval/retrieve (ordered by rank).
        relevant_chunks: List of {source_file, pages} from ground_truth.json.
        k: Cut-off rank for Precision@K and Recall@K.

    Returns:
        Dict with keys: precision_at_k, recall_at_k, mrr.
    """
    # Build a set of (source_file, page_number) tuples that are relevant
    relevant_set: set[tuple[str, int]] = set()
    for rc in relevant_chunks:
        src = rc["source_file"]
        for pg in rc.get("pages", []):
            relevant_set.add((src, int(pg)))

    total_relevant = len(relevant_set)
    if total_relevant == 0:
        return {"precision_at_k": 0.0, "recall_at_k": 0.0, "mrr": 0.0}

    top_k_chunks = retrieved_chunks[:k]
    hits_at_k = 0
    first_relevant_rank: int | None = None

    for rank, chunk in enumerate(top_k_chunks, start=1):
        src_file = chunk.get("source_file", "")
        page_num = int(chunk.get("page_number", -1))
        if (src_file, page_num) in relevant_set:
            hits_at_k += 1
            if first_relevant_rank is None:
                first_relevant_rank = rank

    precision_at_k = hits_at_k / k if k > 0 else 0.0
    recall_at_k = hits_at_k / total_relevant if total_relevant > 0 else 0.0
    mrr = (1.0 / first_relevant_rank) if first_relevant_rank is not None else 0.0

    return {
        "precision_at_k": round(precision_at_k, 4),
        "recall_at_k": round(recall_at_k, 4),
        "mrr": round(mrr, 4),
    }


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two pre-normalised vectors.

    Args:
        a: First vector (assumed L2-normalised).
        b: Second vector (assumed L2-normalised).

    Returns:
        Dot product (= cosine similarity for normalised vectors), clipped to [0, 1].
    """
    dot = sum(x * y for x, y in zip(a, b))
    return max(0.0, min(1.0, dot))


# Module-level cache so the model is loaded once per eval run.
_local_embed_model = None


def _get_embed_model():
    """Load BAAI/bge-m3 (from local HuggingFace cache) — called at most once."""
    global _local_embed_model
    if _local_embed_model is None:
        from sentence_transformers import SentenceTransformer
        print("  Loading local embedding model for faithfulness scoring (bge-m3) ...")
        _local_embed_model = SentenceTransformer("BAAI/bge-m3")
    return _local_embed_model


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using the local bge-m3 model.

    Args:
        texts: Texts to embed.

    Returns:
        List of L2-normalised float vectors.
    """
    model = _get_embed_model()
    import numpy as np
    vecs = model.encode(
        [t.replace("\n", " ") for t in texts],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vecs]


def judge_faithfulness_llm(
    context: str,
    answer: str,
    openai_client: Any,
) -> float:
    """Score faithfulness using OpenAI GPT-4o-mini as the judge (0.0–1.0).

    Args:
        context: Retrieved text chunks concatenated (the grounding material).
        answer: The RAG system's generated answer.
        openai_client: An openai.OpenAI (or AzureOpenAI) client instance.

    Returns:
        Faithfulness score 0.0–1.0, or -1.0 on failure.
    """
    prompt = f"""You are an impartial judge evaluating whether an AI assistant's answer is faithful to the provided source context.

CONTEXT (retrieved contract text):
\"\"\"
{context[:3000]}
\"\"\"

ANSWER (generated by the AI assistant):
\"\"\"
{answer[:1500]}
\"\"\"

Task: Rate how faithfully the ANSWER is grounded in the CONTEXT on a scale from 0 to 10.
- 10 = every claim in the answer is directly supported by the context
- 5  = the answer is mostly correct but makes some unsupported extrapolations
- 0  = the answer contains claims that directly contradict or are entirely absent from the context

Reply with ONLY a single integer from 0 to 10. No explanation."""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        score = int(raw)
        return round(min(max(score, 0), 10) / 10.0, 2)
    except Exception as exc:
        logger.warning("faithfulness LLM judging failed: %s", exc)
        return -1.0


def judge_faithfulness_embeddings(context: str, answer: str) -> float:
    """Score faithfulness via mean cosine similarity (local bge-m3 fallback).

    Splits context into chunks of ~500 chars, embeds each chunk and the answer,
    then returns the mean max-similarity — a proxy for how well the answer
    content is represented in the retrieved context.

    Args:
        context: Concatenated retrieved chunk text.
        answer: The RAG system's generated answer.

    Returns:
        Mean max-similarity score 0.0–1.0, or -1.0 on failure.
    """
    if not context.strip() or not answer.strip():
        return -1.0
    try:
        # Split context into ~500-char windows for finer-grained matching
        window = 500
        chunks = [context[i:i + window] for i in range(0, min(len(context), 3000), window)]
        if not chunks:
            return -1.0

        texts = chunks + [answer]
        vecs = _embed_texts(texts)
        chunk_vecs = vecs[:-1]
        answer_vec = vecs[-1]

        # Mean of (max similarity of each answer sentence to any chunk)
        # Simplified: max cosine sim across all context chunks
        sims = [_cosine_similarity(cv, answer_vec) for cv in chunk_vecs]
        return round(sum(sims) / len(sims), 3)
    except Exception as exc:
        logger.warning("faithfulness embedding scoring failed: %s", exc)
        return -1.0


def judge_faithfulness(
    context: str,
    answer: str,
    openai_client: Any | None,
) -> tuple[float, str]:
    """Score faithfulness with automatic backend selection.

    Tries OpenAI GPT-4o-mini first; falls back to local bge-m3 cosine
    similarity when no OpenAI client is available.

    Args:
        context: Retrieved text chunks concatenated (the grounding material).
        answer: The RAG system's generated answer.
        openai_client: openai.OpenAI client, or None to force local fallback.

    Returns:
        Tuple of (score, source) where score is 0.0–1.0 (-1.0 on failure)
        and source is "llm" | "embed" | "error".
    """
    if openai_client is not None:
        score = judge_faithfulness_llm(context, answer, openai_client)
        if score >= 0:
            return score, "llm"
    # Fallback: local embedding cosine similarity
    score = judge_faithfulness_embeddings(context, answer)
    return score, "embed" if score >= 0 else "error"


# ---------------------------------------------------------------------------
# Ingest step
# ---------------------------------------------------------------------------

def run_ingest_step(base_url: str, persistent_contracts: list[dict]) -> list[dict]:
    """Ingest all persistent contracts into the vector DB.

    Args:
        base_url: API base URL.
        persistent_contracts: List of contract dicts from ground_truth.json.

    Returns:
        List of ingest result dicts for the final report.
    """
    ingest_results: list[dict] = []
    print("\n[1/4] Ingesting persistent contracts ...")
    for contract in persistent_contracts:
        pdf_path = BACKEND_DIR / contract["path"]
        if not pdf_path.exists():
            print(f"  WARN  not found: {pdf_path}")
            ingest_results.append({
                "filename": contract["filename"],
                "status": "file_missing",
                "path_checked": str(pdf_path),
            })
            continue

        t0 = time.perf_counter()
        try:
            resp = ingest_contract(base_url, pdf_path)
            latency = time.perf_counter() - t0
            status = resp.get("status", "unknown")
            chunks = resp.get("chunks_created", "?")
            label = "OK" if status in ("success", "skipped") else "FAIL"
            print(f"  {label:4s}  {contract['filename']}  ({latency:.1f}s, {chunks} chunks, status={status})")
            ingest_results.append({
                "filename": contract["filename"],
                "status": status,
                "chunks_created": chunks,
                "latency_s": round(latency, 3),
            })
        except Exception as exc:
            latency = time.perf_counter() - t0
            print(f"  FAIL  {contract['filename']}  ({exc})")
            ingest_results.append({
                "filename": contract["filename"],
                "status": "error",
                "error": str(exc),
                "latency_s": round(latency, 3),
            })
    return ingest_results


# ---------------------------------------------------------------------------
# Mode 2 — Database query evaluation
# ---------------------------------------------------------------------------

def run_mode2_eval(
    base_url: str,
    questions: list[dict],
    top_k: int,
    openai_client: Any | None,
) -> list[dict]:
    """Evaluate Mode 2: question → vector DB → answer.

    For each question:
      - Calls /api/query for the generated answer (contract_hit, clause_hit, faithfulness)
      - Calls /api/eval/retrieve for raw chunks (Precision@K, Recall@K, MRR)

    Args:
        base_url: API base URL.
        questions: Mode 2 question list from ground_truth.json.
        top_k: Retrieval cut-off for IR metrics.
        openai_client: OpenAI client for faithfulness; None to skip.

    Returns:
        List of per-question result dicts.
    """
    results: list[dict] = []
    print(f"\n[2/4] Mode 2 — Database queries ({len(questions)} questions)")
    print(f"{'ID':<7} {'C-Hit':<7} {'Kw-Hit':<8} {'P@K':<7} {'R@K':<7} {'MRR':<7} {'Faith[src]':<14} {'Lat':>7}  Question")
    print("-" * 108)

    for q in questions:
        qid = q["id"]
        question = q["question"]
        expected_contracts = q.get("expected_contracts", [])
        expected_keywords = q.get("expected_keywords", [])
        relevant_chunks_gt = q.get("relevant_chunks", [])

        row: dict[str, Any] = {
            "id": qid,
            "mode": 2,
            "question": question,
            "description": q.get("description", ""),
            "expected_contracts": expected_contracts,
            "expected_keywords": expected_keywords,
        }

        # --- Generate answer ---
        try:
            answer, latency = query_and_collect(base_url, question)
        except Exception as exc:
            print(f"{qid:<7} {'ERROR':<7} {'ERROR':<8} {'-':<7} {'-':<7} {'-':<7} {'-':<7} {'':>7}  {question[:50]}")
            row.update({"error": str(exc), "contract_hit": False, "clause_hit": False})
            results.append(row)
            continue

        contract_hit = check_contract_hit(answer, expected_contracts)
        clause_hit = check_clause_hit(answer, expected_keywords)
        row["answer_preview"] = answer[:300]
        row["contract_hit"] = contract_hit
        row["clause_hit"] = clause_hit
        row["latency_s"] = round(latency, 3)

        # --- IR metrics ---
        ir: dict[str, float] = {"precision_at_k": -1.0, "recall_at_k": -1.0, "mrr": -1.0}
        if relevant_chunks_gt:
            try:
                retrieved = eval_retrieve(base_url, question, top_k)
                ir = compute_ir_metrics(retrieved, relevant_chunks_gt, k=top_k)
            except Exception as exc:
                logger.warning("IR metrics failed for %s: %s", qid, exc)
        row.update(ir)

        # --- Faithfulness (LLM judge if OpenAI available, else local bge-m3 cosine) ---
        faith: float = -1.0
        faith_src: str = "error"
        retrieved_for_faith: list[dict] = []  # captured for reuse by extended metrics
        try:
            retrieved_for_faith = eval_retrieve(base_url, question, top_k)
            context = "\n\n".join(c.get("text", "") for c in retrieved_for_faith)
            faith, faith_src = judge_faithfulness(context, answer, openai_client)
        except Exception as exc:
            logger.warning("Faithfulness failed for %s: %s", qid, exc)
        row["faithfulness"] = faith
        row["faithfulness_source"] = faith_src

        # --- Extended metrics ---
        # Answer Relevance (LLM or embedding fallback)
        ans_rel, ans_rel_src = score_answer_relevance(question, answer, openai_client, _embed_texts)
        row["answer_relevance"] = ans_rel
        row["answer_relevance_source"] = ans_rel_src

        # Completeness — continuous keyword-coverage ratio (deterministic)
        row["completeness"] = score_completeness(answer, expected_keywords)

        # Hallucination Rate — derived from faithfulness, no extra LLM call
        row["hallucination_rate"] = score_hallucination_rate(faith)

        # Context Precision & Recall (GT labels for precision when available)
        if retrieved_for_faith:
            relevant_set_gt: set[tuple[str, int]] = set()
            for rc in relevant_chunks_gt:
                for pg in rc.get("pages", []):
                    relevant_set_gt.add((rc["source_file"], int(pg)))
            ctx_prec, ctx_prec_src = score_context_precision(
                question, retrieved_for_faith, openai_client,
                relevant_set=relevant_set_gt if relevant_set_gt else None,
            )
            ctx_rec, ctx_rec_src = score_context_recall(question, retrieved_for_faith, openai_client)
            row["context_precision"] = ctx_prec
            row["context_precision_source"] = ctx_prec_src
            row["context_recall"] = ctx_rec
            row["context_recall_source"] = ctx_rec_src

            # Attribution metrics (heuristic, deterministic)
            row["citation_accuracy"] = score_citation_accuracy(answer, retrieved_for_faith)
            row["citation_coverage"] = score_citation_coverage(answer, retrieved_for_faith)
        else:
            row.update({
                "context_precision": -1.0, "context_precision_source": "error",
                "context_recall": -1.0, "context_recall_source": "error",
                "citation_accuracy": -1.0, "citation_coverage": -1.0,
            })

        # Cost estimate for this query (question + answer tokens)
        row["cost_estimate"] = estimate_query_cost(question, answer)

        # --- Print row ---
        p_str = f"{ir['precision_at_k']:.2f}" if ir["precision_at_k"] >= 0 else "n/a"
        r_str = f"{ir['recall_at_k']:.2f}" if ir["recall_at_k"] >= 0 else "n/a"
        m_str = f"{ir['mrr']:.2f}" if ir["mrr"] >= 0 else "n/a"
        f_str = f"{faith:.2f}[{faith_src}]" if faith >= 0 else "n/a"
        print(
            f"{qid:<7} {'PASS' if contract_hit else 'FAIL':<7} "
            f"{'PASS' if clause_hit else 'FAIL':<8} "
            f"{p_str:<7} {r_str:<7} {m_str:<7} {f_str:<12} "
            f"{latency:>6.2f}s  {question[:50]}"
        )

        results.append(row)

    return results


# ---------------------------------------------------------------------------
# Mode 1 — Single-doc analysis evaluation
# ---------------------------------------------------------------------------

def run_mode1_eval(
    base_url: str,
    questions: list[dict],
    openai_client: Any | None,
) -> list[dict]:
    """Evaluate Mode 1: upload temp contract + question → single-doc analysis.

    For each question:
      - Calls /api/analyze?mode=single with the temp PDF
      - Checks clause_hit and absent_keyword compliance
      - Judges faithfulness against the full document text

    Args:
        base_url: API base URL.
        questions: Mode 1 question list from ground_truth.json.
        openai_client: OpenAI client for faithfulness; None to skip.

    Returns:
        List of per-question result dicts.
    """
    results: list[dict] = []
    print(f"\n[3/4] Mode 1 — Single-doc analysis ({len(questions)} questions)")
    print(f"{'ID':<7} {'Kw-Hit':<8} {'AbsKw':<8} {'Faith[src]':<14} {'Lat':>7}  Question")
    print("-" * 88)

    for q in questions:
        qid = q["id"]
        question = q["question"]
        upload_file = q.get("upload_file", "")
        expected_keywords = q.get("expected_keywords", [])
        expected_absent = q.get("expected_absent_keywords", [])

        pdf_path = TEMP_CONTRACTS_DIR / upload_file

        row: dict[str, Any] = {
            "id": qid,
            "mode": 1,
            "question": question,
            "upload_file": upload_file,
            "description": q.get("description", ""),
            "expected_keywords": expected_keywords,
            "expected_absent_keywords": expected_absent,
        }

        if not pdf_path.exists():
            print(f"{qid:<7} {'SKIP':<8} {'SKIP':<8} {'n/a':<7} {'':>7}  {question[:50]}  [FILE MISSING: {pdf_path}]")
            row["error"] = f"temp contract not found: {pdf_path}"
            results.append(row)
            continue

        try:
            answer, latency = analyze_and_collect(base_url, pdf_path, question, mode="single")
        except Exception as exc:
            print(f"{qid:<7} {'ERROR':<8} {'ERROR':<8} {'n/a':<7} {'':>7}  {question[:50]}")
            row["error"] = str(exc)
            results.append(row)
            continue

        clause_hit = check_clause_hit(answer, expected_keywords)
        absent_ok = check_absent_keywords(answer, expected_absent) if expected_absent else True

        row["answer_preview"] = answer[:300]
        row["clause_hit"] = clause_hit
        row["absent_keywords_ok"] = absent_ok
        row["latency_s"] = round(latency, 3)

        # --- Faithfulness: judge against raw document text (LLM or local embeddings) ---
        faith: float = -1.0
        faith_src: str = "error"
        try:
            from app.etl.extractors.pdf_extractor import PDFExtractor
            from app.etl.transformers.cleaner import TextCleaner
            pages = PDFExtractor().extract(str(pdf_path))
            cleaner = TextCleaner()
            doc_text = "\n\n".join(cleaner.clean(p["text"]) for p in pages if p.get("text"))
            faith, faith_src = judge_faithfulness(doc_text, answer, openai_client)
        except Exception as exc:
            logger.warning("Faithfulness failed for %s: %s", qid, exc)
        row["faithfulness"] = faith
        row["faithfulness_source"] = faith_src

        # --- Extended metrics ---
        ans_rel, ans_rel_src = score_answer_relevance(question, answer, openai_client, _embed_texts)
        row["answer_relevance"] = ans_rel
        row["answer_relevance_source"] = ans_rel_src
        row["completeness"] = score_completeness(answer, expected_keywords)
        row["hallucination_rate"] = score_hallucination_rate(faith)
        # No DB-retrieved chunks in Mode 1 — context/attribution metrics not applicable
        row.update({
            "context_precision": -1.0, "context_precision_source": "n/a",
            "context_recall": -1.0, "context_recall_source": "n/a",
            "citation_accuracy": -1.0, "citation_coverage": -1.0,
        })
        row["cost_estimate"] = estimate_query_cost(question, answer)

        f_str = f"{faith:.2f}[{faith_src}]" if faith >= 0 else "n/a"
        print(
            f"{qid:<7} {'PASS' if clause_hit else 'FAIL':<8} "
            f"{'PASS' if absent_ok else 'FAIL':<8} "
            f"{f_str:<12} {latency:>6.2f}s  {question[:50]}"
        )

        results.append(row)

    return results


# ---------------------------------------------------------------------------
# Mode 3 — Compare uploaded vs DB evaluation
# ---------------------------------------------------------------------------

def run_mode3_eval(
    base_url: str,
    questions: list[dict],
    openai_client: Any | None,
) -> list[dict]:
    """Evaluate Mode 3: upload temp contract, compare it against the DB.

    For each question:
      - Calls /api/analyze?mode=compare with the temp PDF
      - Checks expected_keywords and expected_comparison_points
      - Judges faithfulness against DB-retrieved context for the same query

    Args:
        base_url: API base URL.
        questions: Mode 3 question list from ground_truth.json.
        openai_client: OpenAI client for faithfulness; None to skip.

    Returns:
        List of per-question result dicts.
    """
    results: list[dict] = []
    print(f"\n[4/4] Mode 3 — Compare uploaded vs DB ({len(questions)} questions)")
    print(f"{'ID':<7} {'Kw-Hit':<8} {'Cmp-Hit':<9} {'Faith[src]':<14} {'Lat':>7}  Question")
    print("-" * 93)

    for q in questions:
        qid = q["id"]
        question = q["question"]
        upload_file = q.get("upload_file", "")
        expected_keywords = q.get("expected_keywords", [])
        comparison_points = q.get("expected_comparison_points", [])

        pdf_path = TEMP_CONTRACTS_DIR / upload_file

        row: dict[str, Any] = {
            "id": qid,
            "mode": 3,
            "question": question,
            "upload_file": upload_file,
            "description": q.get("description", ""),
            "expected_keywords": expected_keywords,
            "expected_comparison_points": comparison_points,
        }

        if not pdf_path.exists():
            print(f"{qid:<7} {'SKIP':<8} {'SKIP':<9} {'n/a':<7} {'':>7}  {question[:50]}  [FILE MISSING]")
            row["error"] = f"temp contract not found: {pdf_path}"
            results.append(row)
            continue

        try:
            answer, latency = analyze_and_collect(base_url, pdf_path, question, mode="compare")
        except Exception as exc:
            print(f"{qid:<7} {'ERROR':<8} {'ERROR':<9} {'n/a':<7} {'':>7}  {question[:50]}")
            row["error"] = str(exc)
            results.append(row)
            continue

        kw_hit = check_clause_hit(answer, expected_keywords)
        # Comparison points: check how many are covered (at least one must be present)
        comparison_hit = any(check_clause_hit(answer, [pt]) for pt in comparison_points) if comparison_points else True

        row["answer_preview"] = answer[:300]
        row["keyword_hit"] = kw_hit
        row["comparison_hit"] = comparison_hit
        row["latency_s"] = round(latency, 3)

        # --- Faithfulness: DB retrieval context (LLM or local embeddings) ---
        faith: float = -1.0
        faith_src: str = "error"
        retrieved_m3: list[dict] = []  # captured for reuse by extended metrics
        try:
            retrieved_m3 = eval_retrieve(base_url, question, top_k=8)
            context = "\n\n".join(c.get("text", "") for c in retrieved_m3)
            faith, faith_src = judge_faithfulness(context, answer, openai_client)
        except Exception as exc:
            logger.warning("Faithfulness failed for %s: %s", qid, exc)
        row["faithfulness"] = faith
        row["faithfulness_source"] = faith_src

        # --- Extended metrics ---
        ans_rel, ans_rel_src = score_answer_relevance(question, answer, openai_client, _embed_texts)
        row["answer_relevance"] = ans_rel
        row["answer_relevance_source"] = ans_rel_src
        row["completeness"] = score_completeness(answer, expected_keywords)
        row["hallucination_rate"] = score_hallucination_rate(faith)

        if retrieved_m3:
            ctx_prec, ctx_prec_src = score_context_precision(
                question, retrieved_m3, openai_client, relevant_set=None
            )
            ctx_rec, ctx_rec_src = score_context_recall(question, retrieved_m3, openai_client)
            row["context_precision"] = ctx_prec
            row["context_precision_source"] = ctx_prec_src
            row["context_recall"] = ctx_rec
            row["context_recall_source"] = ctx_rec_src
            row["citation_accuracy"] = score_citation_accuracy(answer, retrieved_m3)
            row["citation_coverage"] = score_citation_coverage(answer, retrieved_m3)
        else:
            row.update({
                "context_precision": -1.0, "context_precision_source": "error",
                "context_recall": -1.0, "context_recall_source": "error",
                "citation_accuracy": -1.0, "citation_coverage": -1.0,
            })

        row["cost_estimate"] = estimate_query_cost(question, answer)

        f_str = f"{faith:.2f}[{faith_src}]" if faith >= 0 else "n/a"
        print(
            f"{qid:<7} {'PASS' if kw_hit else 'FAIL':<8} "
            f"{'PASS' if comparison_hit else 'FAIL':<9} "
            f"{f_str:<12} {latency:>6.2f}s  {question[:50]}"
        )

        results.append(row)

    return results


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------

def _safe_mean(values: list[float]) -> float:
    """Return the mean of values, excluding -1.0 (skip/error sentinels)."""
    valid = [v for v in values if v >= 0]
    return round(sum(valid) / len(valid), 4) if valid else -1.0


def build_summary(
    mode2_results: list[dict],
    mode1_results: list[dict],
    mode3_results: list[dict],
) -> dict[str, Any]:
    """Build a summary dict across all three evaluation modes.

    Args:
        mode2_results: Per-question results from run_mode2_eval.
        mode1_results: Per-question results from run_mode1_eval.
        mode3_results: Per-question results from run_mode3_eval.

    Returns:
        Summary dict with per-mode and overall metrics.
    """
    def _cost_summary(results: list[dict]) -> dict:
        """Aggregate cost_estimate dicts across all results."""
        costs = [r["cost_estimate"] for r in results if isinstance(r.get("cost_estimate"), dict)]
        return aggregate_session_cost(costs)

    def _mode2_summary(results: list[dict]) -> dict:
        ok = [r for r in results if "error" not in r]
        n = len(ok)
        if n == 0:
            return {"total": 0}
        lats = [r["latency_s"] for r in ok if r.get("latency_s") is not None]
        lats_s = sorted(lats)
        p95_idx = max(0, int(len(lats_s) * 0.95) - 1)
        return {
            "total": n,
            # Existing binary hit metrics
            "contract_hit_rate": round(sum(1 for r in ok if r.get("contract_hit")) / n, 3),
            "clause_hit_rate": round(sum(1 for r in ok if r.get("clause_hit")) / n, 3),
            # Existing IR metrics
            "mean_precision_at_k": _safe_mean([r.get("precision_at_k", -1.0) for r in ok]),
            "mean_recall_at_k": _safe_mean([r.get("recall_at_k", -1.0) for r in ok]),
            "mean_mrr": _safe_mean([r.get("mrr", -1.0) for r in ok]),
            # Existing faithfulness
            "mean_faithfulness": _safe_mean([r.get("faithfulness", -1.0) for r in ok]),
            # New: answer-level metrics
            "mean_answer_relevance": _safe_mean([r.get("answer_relevance", -1.0) for r in ok]),
            "mean_completeness": _safe_mean([r.get("completeness", -1.0) for r in ok]),
            "mean_hallucination_rate": _safe_mean([r.get("hallucination_rate", -1.0) for r in ok]),
            # New: context-level metrics
            "mean_context_precision": _safe_mean([r.get("context_precision", -1.0) for r in ok]),
            "mean_context_recall": _safe_mean([r.get("context_recall", -1.0) for r in ok]),
            # New: attribution metrics
            "mean_citation_accuracy": _safe_mean([r.get("citation_accuracy", -1.0) for r in ok]),
            "mean_citation_coverage": _safe_mean([r.get("citation_coverage", -1.0) for r in ok]),
            # New: robustness (populated by run_robustness_eval if --robustness flag set)
            "mean_query_consistency": _safe_mean([r.get("query_consistency", -1.0) for r in ok]),
            "mean_noise_sensitivity": _safe_mean([r.get("noise_sensitivity", -1.0) for r in ok]),
            # Latency
            "avg_latency_s": round(sum(lats) / len(lats), 3) if lats else 0.0,
            "p95_latency_s": lats_s[p95_idx] if lats_s else 0.0,
            # New: cost
            "cost": _cost_summary(ok),
            "errors": len(results) - n,
        }

    def _mode1_summary(results: list[dict]) -> dict:
        ok = [r for r in results if "error" not in r]
        n = len(ok)
        if n == 0:
            return {"total": 0}
        lats = [r["latency_s"] for r in ok if r.get("latency_s") is not None]
        lats_s = sorted(lats)
        p95_idx = max(0, int(len(lats_s) * 0.95) - 1)
        return {
            "total": n,
            "clause_hit_rate": round(sum(1 for r in ok if r.get("clause_hit")) / n, 3),
            "absent_keyword_pass_rate": round(sum(1 for r in ok if r.get("absent_keywords_ok", True)) / n, 3),
            "mean_faithfulness": _safe_mean([r.get("faithfulness", -1.0) for r in ok]),
            # New: answer-level metrics
            "mean_answer_relevance": _safe_mean([r.get("answer_relevance", -1.0) for r in ok]),
            "mean_completeness": _safe_mean([r.get("completeness", -1.0) for r in ok]),
            "mean_hallucination_rate": _safe_mean([r.get("hallucination_rate", -1.0) for r in ok]),
            "avg_latency_s": round(sum(lats) / len(lats), 3) if lats else 0.0,
            "p95_latency_s": lats_s[p95_idx] if lats_s else 0.0,
            "cost": _cost_summary(ok),
            "errors": len(results) - n,
        }

    def _mode3_summary(results: list[dict]) -> dict:
        ok = [r for r in results if "error" not in r]
        n = len(ok)
        if n == 0:
            return {"total": 0}
        lats = [r["latency_s"] for r in ok if r.get("latency_s") is not None]
        lats_s = sorted(lats)
        p95_idx = max(0, int(len(lats_s) * 0.95) - 1)
        return {
            "total": n,
            "keyword_hit_rate": round(sum(1 for r in ok if r.get("keyword_hit")) / n, 3),
            "comparison_hit_rate": round(sum(1 for r in ok if r.get("comparison_hit")) / n, 3),
            "mean_faithfulness": _safe_mean([r.get("faithfulness", -1.0) for r in ok]),
            # New: answer-level metrics
            "mean_answer_relevance": _safe_mean([r.get("answer_relevance", -1.0) for r in ok]),
            "mean_completeness": _safe_mean([r.get("completeness", -1.0) for r in ok]),
            "mean_hallucination_rate": _safe_mean([r.get("hallucination_rate", -1.0) for r in ok]),
            # New: context-level metrics (Mode 3 uses DB retrieval context)
            "mean_context_precision": _safe_mean([r.get("context_precision", -1.0) for r in ok]),
            "mean_context_recall": _safe_mean([r.get("context_recall", -1.0) for r in ok]),
            "mean_citation_accuracy": _safe_mean([r.get("citation_accuracy", -1.0) for r in ok]),
            "mean_citation_coverage": _safe_mean([r.get("citation_coverage", -1.0) for r in ok]),
            "avg_latency_s": round(sum(lats) / len(lats), 3) if lats else 0.0,
            "p95_latency_s": lats_s[p95_idx] if lats_s else 0.0,
            "cost": _cost_summary(ok),
            "errors": len(results) - n,
        }

    return {
        "mode2_db_query": _mode2_summary(mode2_results),
        "mode1_single_doc": _mode1_summary(mode1_results),
        "mode3_compare": _mode3_summary(mode3_results),
    }


def print_summary(summary: dict[str, Any]) -> None:
    """Print a human-readable summary table to stdout.

    Args:
        summary: Summary dict from build_summary().
    """
    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)

    def _fmt(val: float, fmt: str = ".3f") -> str:
        return format(val, fmt) if val >= 0 else "n/a"

    m2 = summary.get("mode2_db_query", {})
    if m2.get("total", 0) > 0:
        print(f"\nMode 2 — Database Query ({m2['total']} questions)")
        print(f"  Contract Hit Rate     : {m2['contract_hit_rate']:.1%}")
        print(f"  Clause Hit Rate       : {m2['clause_hit_rate']:.1%}")
        if m2.get("mean_precision_at_k", -1) >= 0:
            print(f"  Mean Precision@K      : {m2['mean_precision_at_k']:.3f}")
            print(f"  Mean Recall@K         : {m2['mean_recall_at_k']:.3f}")
            print(f"  Mean MRR              : {m2['mean_mrr']:.3f}")
        print(f"  Mean Faithfulness     : {_fmt(m2.get('mean_faithfulness', -1))}")
        print(f"  Mean Answer Relevance : {_fmt(m2.get('mean_answer_relevance', -1))}")
        print(f"  Mean Completeness     : {_fmt(m2.get('mean_completeness', -1))}")
        print(f"  Mean Hallucination    : {_fmt(m2.get('mean_hallucination_rate', -1))}")
        print(f"  Mean Ctx Precision    : {_fmt(m2.get('mean_context_precision', -1))}")
        print(f"  Mean Ctx Recall       : {_fmt(m2.get('mean_context_recall', -1))}")
        print(f"  Mean Citation Acc.    : {_fmt(m2.get('mean_citation_accuracy', -1))}")
        print(f"  Mean Citation Cov.    : {_fmt(m2.get('mean_citation_coverage', -1))}")
        if m2.get("mean_query_consistency", -1) >= 0:
            print(f"  Mean Query Consist.   : {m2['mean_query_consistency']:.3f}")
        if m2.get("mean_noise_sensitivity", -1) >= 0:
            print(f"  Mean Noise Sensitiv.  : {m2['mean_noise_sensitivity']:.3f}")
        print(f"  Avg Latency           : {m2['avg_latency_s']:.2f}s")
        print(f"  P95 Latency           : {m2['p95_latency_s']:.2f}s")
        cost = m2.get("cost", {})
        if cost.get("total_cost_usd", 0) > 0:
            print(f"  Est. Cost             : ${cost['total_cost_usd']:.6f} "
                  f"({cost['total_tokens']} tokens, {cost['query_count']} queries)")
        print(f"  Errors                : {m2['errors']}")

    m1 = summary.get("mode1_single_doc", {})
    if m1.get("total", 0) > 0:
        print(f"\nMode 1 — Single-Doc Analysis ({m1['total']} questions)")
        print(f"  Clause Hit Rate       : {m1['clause_hit_rate']:.1%}")
        print(f"  Absent KW Pass        : {m1['absent_keyword_pass_rate']:.1%}")
        print(f"  Mean Faithfulness     : {_fmt(m1.get('mean_faithfulness', -1))}")
        print(f"  Mean Answer Relevance : {_fmt(m1.get('mean_answer_relevance', -1))}")
        print(f"  Mean Completeness     : {_fmt(m1.get('mean_completeness', -1))}")
        print(f"  Mean Hallucination    : {_fmt(m1.get('mean_hallucination_rate', -1))}")
        print(f"  Avg Latency           : {m1['avg_latency_s']:.2f}s")
        print(f"  P95 Latency           : {m1['p95_latency_s']:.2f}s")
        cost = m1.get("cost", {})
        if cost.get("total_cost_usd", 0) > 0:
            print(f"  Est. Cost             : ${cost['total_cost_usd']:.6f} "
                  f"({cost['total_tokens']} tokens, {cost['query_count']} queries)")
        print(f"  Errors                : {m1['errors']}")

    m3 = summary.get("mode3_compare", {})
    if m3.get("total", 0) > 0:
        print(f"\nMode 3 — Compare Uploaded vs DB ({m3['total']} questions)")
        print(f"  Keyword Hit Rate      : {m3['keyword_hit_rate']:.1%}")
        print(f"  Comparison Hit Rate   : {m3['comparison_hit_rate']:.1%}")
        print(f"  Mean Faithfulness     : {_fmt(m3.get('mean_faithfulness', -1))}")
        print(f"  Mean Answer Relevance : {_fmt(m3.get('mean_answer_relevance', -1))}")
        print(f"  Mean Completeness     : {_fmt(m3.get('mean_completeness', -1))}")
        print(f"  Mean Hallucination    : {_fmt(m3.get('mean_hallucination_rate', -1))}")
        print(f"  Mean Ctx Precision    : {_fmt(m3.get('mean_context_precision', -1))}")
        print(f"  Mean Ctx Recall       : {_fmt(m3.get('mean_context_recall', -1))}")
        print(f"  Mean Citation Acc.    : {_fmt(m3.get('mean_citation_accuracy', -1))}")
        print(f"  Mean Citation Cov.    : {_fmt(m3.get('mean_citation_coverage', -1))}")
        print(f"  Avg Latency           : {m3['avg_latency_s']:.2f}s")
        print(f"  P95 Latency           : {m3['p95_latency_s']:.2f}s")
        cost = m3.get("cost", {})
        if cost.get("total_cost_usd", 0) > 0:
            print(f"  Est. Cost             : ${cost['total_cost_usd']:.6f} "
                  f"({cost['total_tokens']} tokens, {cost['query_count']} queries)")
        print(f"  Errors                : {m3['errors']}")

    print("=" * 80)


# ---------------------------------------------------------------------------
# Robustness evaluation (opt-in via --robustness flag)
# ---------------------------------------------------------------------------

def run_robustness_eval(
    base_url: str,
    mode2_results: list[dict],
    openai_client: Any | None,
    top_k: int,
    n_paraphrases: int = 2,
) -> None:
    """Run query-consistency and noise-sensitivity checks on Mode 2 questions.

    Results are written back in-place into each ``mode2_results`` row by adding
    ``query_consistency`` and ``noise_sensitivity`` keys.

    Query consistency:
      1. Generate ``n_paraphrases`` paraphrase variants of each question.
      2. Query each paraphrase via /api/query.
      3. Score semantic similarity of each paraphrase answer to the original.

    Noise sensitivity:
      1. Fetch the raw retrieved chunks for the question.
      2. Inject 30% boilerplate noise chunks.
      3. Compute faithfulness on the noisy context.
      4. Score = base_faithfulness – noisy_faithfulness.

    Requires ``openai_client`` for paraphrase generation. Noise sensitivity
    falls back to local bge-m3 embeddings if OpenAI is unavailable.

    Args:
        base_url: API base URL.
        mode2_results: Per-question result dicts from run_mode2_eval (mutated in-place).
        openai_client: OpenAI client for paraphrase generation; None → skip consistency.
        top_k: Retrieval cut-off for fetching chunks.
        n_paraphrases: Number of paraphrases per question (default: 2).
    """
    n_qs = sum(1 for r in mode2_results if "error" not in r)
    print(f"\n[Robustness] Running on {n_qs} Mode 2 questions "
          f"({n_paraphrases} paraphrases + noise injection each) ...")

    for row in mode2_results:
        if "error" in row:
            continue

        qid = row["id"]
        question = row["question"]
        original_answer = row.get("answer_preview", "")  # first 300 chars; sufficient for embedding
        base_faith = row.get("faithfulness", -1.0)

        # --- Query Consistency ---
        qc_score: float = -1.0
        if openai_client is not None and original_answer:
            paraphrases = generate_paraphrases(question, n_paraphrases, openai_client)
            para_answers: list[str] = []
            for para_q in paraphrases:
                try:
                    para_ans, _ = query_and_collect(base_url, para_q)
                    para_answers.append(para_ans)
                except Exception as exc:
                    logger.warning("Paraphrase query failed for %s: %s", qid, exc)
            if para_answers:
                qc_score = score_query_consistency(original_answer, para_answers, _embed_texts)
        row["query_consistency"] = qc_score

        # --- Noise Sensitivity ---
        ns_score: float = -1.0
        try:
            clean_chunks = eval_retrieve(base_url, question, top_k)
            if clean_chunks:
                noisy_chunks = inject_noise_chunks(clean_chunks, noise_ratio=0.3)
                noisy_context = "\n\n".join(c.get("text", "") for c in noisy_chunks)
                noisy_faith, _ = judge_faithfulness(noisy_context, original_answer, openai_client)
                ns_score = score_noise_sensitivity(base_faith, noisy_faith)
        except Exception as exc:
            logger.warning("Noise sensitivity failed for %s: %s", qid, exc)
        row["noise_sensitivity"] = ns_score

        print(f"  {qid:<7} consistency={qc_score:.3f}  noise_sensitivity={ns_score:.3f}")


# ---------------------------------------------------------------------------
# Core evaluation orchestrator
# ---------------------------------------------------------------------------

def run_evaluation(
    base_url: str,
    skip_ingest: bool,
    modes: set[int],
    top_k: int,
    robustness: bool = False,
) -> tuple[dict[str, Any], int]:
    """Run the full evaluation pipeline and return a structured results dict.

    Args:
        base_url: API base URL.
        skip_ingest: If True, skip the ingest step.
        modes: Set of mode numbers to evaluate (1, 2, 3).
        top_k: Retrieval cut-off for IR metrics (Mode 2 only).
        robustness: If True, run query-consistency and noise-sensitivity checks
                    on Mode 2 questions after the main evaluation.

    Returns:
        Tuple of (results_dict, unix_timestamp).
    """
    gt = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    timestamp = int(time.time())

    # --- OpenAI client for faithfulness judging (optional — local fallback always available) ---
    openai_client = None
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        try:
            import openai
            openai_client = openai.OpenAI(api_key=api_key)
            print("  Faithfulness backend : GPT-4o-mini (LLM judge)")
        except ImportError:
            print("  WARN: openai package not installed — using local embedding fallback")
    else:
        print("  Faithfulness backend : local bge-m3 cosine similarity (OPENAI_API_KEY not set)")

    results: dict[str, Any] = {
        "metadata": {
            "timestamp": timestamp,
            "base_url": base_url,
            "ground_truth_version": gt.get("version", "3.0"),
            "modes_evaluated": sorted(modes),
            "top_k": top_k,
            "skip_ingest": skip_ingest,
            "faithfulness_backend": "gpt-4o-mini" if openai_client is not None else "bge-m3-cosine",
            "robustness_eval": robustness,
        },
        "ingest_results": [],
        "mode2_results": [],
        "mode1_results": [],
        "mode3_results": [],
        "summary": {},
    }

    # ------------------------------------------------------------------
    # Step 1 — Ingest persistent contracts
    # ------------------------------------------------------------------
    if not skip_ingest:
        results["ingest_results"] = run_ingest_step(
            base_url, gt.get("persistent_contracts", [])
        )
    else:
        print("\n[1/4] Skipping ingest (--skip-ingest flag set)")

    # ------------------------------------------------------------------
    # Step 2 — Mode 2 evaluation
    # ------------------------------------------------------------------
    if 2 in modes:
        results["mode2_results"] = run_mode2_eval(
            base_url,
            gt.get("mode2_questions", []),
            top_k=top_k,
            openai_client=openai_client,
        )
    else:
        print("\n[2/4] Skipping Mode 2 (not in --modes)")

    # ------------------------------------------------------------------
    # Step 3 — Mode 1 evaluation
    # ------------------------------------------------------------------
    if 1 in modes:
        results["mode1_results"] = run_mode1_eval(
            base_url,
            gt.get("mode1_questions", []),
            openai_client=openai_client,
        )
    else:
        print("\n[3/4] Skipping Mode 1 (not in --modes)")

    # ------------------------------------------------------------------
    # Step 4 — Mode 3 evaluation
    # ------------------------------------------------------------------
    if 3 in modes:
        results["mode3_results"] = run_mode3_eval(
            base_url,
            gt.get("mode3_questions", []),
            openai_client=openai_client,
        )
    else:
        print("\n[4/4] Skipping Mode 3 (not in --modes)")

    # ------------------------------------------------------------------
    # Robustness (opt-in, Mode 2 only)
    # ------------------------------------------------------------------
    if robustness and 2 in modes and results["mode2_results"]:
        run_robustness_eval(
            base_url,
            results["mode2_results"],
            openai_client=openai_client,
            top_k=top_k,
        )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    results["summary"] = build_summary(
        results["mode2_results"],
        results["mode1_results"],
        results["mode3_results"],
    )
    print_summary(results["summary"])

    return results, timestamp


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and run the evaluation."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Evaluation harness for the Riverty RAG contract review system"
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", "http://localhost:8000"),
        help="API base URL (default: http://localhost:8000 or $BASE_URL)",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        default=os.environ.get("SKIP_INGEST", "0") == "1",
        help="Skip contract ingestion (use when contracts are already loaded)",
    )
    parser.add_argument(
        "--modes",
        default="1,2,3",
        help="Comma-separated list of modes to evaluate, e.g. '2' or '1,3' (default: 1,2,3)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
        help="Retrieval cut-off K for IR metrics (default: 8)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(EVAL_DIR),
        help="Directory to write results JSON (default: tests/eval/)",
    )
    parser.add_argument(
        "--robustness",
        action="store_true",
        default=False,
        help="Run query-consistency and noise-sensitivity checks on Mode 2 questions "
             "(adds extra API calls per question; requires --modes to include 2)",
    )
    args = parser.parse_args()

    try:
        modes = {int(m.strip()) for m in args.modes.split(",")}
    except ValueError:
        print(f"ERROR: --modes must be comma-separated integers, got '{args.modes}'")
        sys.exit(1)

    print("=" * 80)
    print("Riverty RAG Evaluation Harness")
    print(f"  Base URL            : {args.base_url}")
    print(f"  Skip Ingest         : {args.skip_ingest}")
    print(f"  Modes               : {sorted(modes)}")
    print(f"  Top-K (IR metrics)  : {args.top_k}")
    print(f"  Ground Truth        : {GROUND_TRUTH_PATH}")
    print(f"  Persistent contracts: {PERSISTENT_CONTRACTS_DIR}")
    print(f"  Temp contracts      : {TEMP_CONTRACTS_DIR}")
    print(f"  Robustness eval     : {'enabled' if args.robustness else 'disabled'}")
    print("=" * 80)

    results, timestamp = run_evaluation(
        base_url=args.base_url,
        skip_ingest=args.skip_ingest,
        modes=modes,
        top_k=args.top_k,
        robustness=args.robustness,
    )

    out_path = Path(args.output_dir) / f"eval_results_{timestamp}.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved → {out_path}")


if __name__ == "__main__":
    main()
