"""
run_eval.py — Evaluation harness for the Riverty RAG contract review system.

Minimum-viable evaluation without RAGAS:
  1. Ingests the 4 real contracts from uploads/synthetic_legal_db/persistent_contracts/
     via /api/ingest (skipped if already loaded with --skip-ingest).
  2. Runs each ground-truth question through /api/query (SSE stream).
  3. Checks two binary metrics per question:
       - contract_hit  : did the response name the expected source contract?
       - clause_hit    : did the response contain the expected clause keywords?
  4. Measures latency (seconds) for each query.
  5. Saves a timestamped JSON results file and prints a summary table.

Usage:
    cd backend
    python tests/eval/run_eval.py [--base-url http://localhost:8000] [--skip-ingest]

Environment variables:
    BASE_URL    — API base URL (default: http://localhost:8000)
    SKIP_INGEST — set to "1" to skip re-ingestion if contracts are already loaded
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# ============================================================
# DEMO MODE: direct HTTP calls to local FastAPI server
# PRODUCTION SWAP → Azure API Management (AWS: API Gateway):
#   Replace BASE_URL with the Azure APIM endpoint URL.
#   Add an Authorization header with the APIM subscription key.
# ============================================================

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVAL_DIR.parent.parent
GROUND_TRUTH_PATH = EVAL_DIR / "ground_truth.json"


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
        question: Plain-English question about the uploaded contracts.

    Returns:
        Tuple of (full_answer_text, latency_seconds).
        latency_seconds measures time from request start to last SSE token.
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


# ---------------------------------------------------------------------------
# Metric checks
# ---------------------------------------------------------------------------

def check_contract_hit(answer: str, expected_contracts: list[str]) -> bool:
    """Return True if any expected contract stem appears in the answer text.

    Checks the full filename stem AND each underscore-separated token that
    is longer than 3 characters (skips "pdf", "the", etc.).

    e.g. "contract_missing_gdpr" → also checks "missing", "gdpr", "contract"

    Args:
        answer: Full response text from the RAG system.
        expected_contracts: List of expected contract filename stems (no .pdf extension).

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


# ---------------------------------------------------------------------------
# Core evaluation loop
# ---------------------------------------------------------------------------

def run_evaluation(base_url: str, skip_ingest: bool) -> tuple[dict[str, Any], int]:
    """Run the full evaluation pipeline and return a structured results dict.

    Args:
        base_url: API base URL.
        skip_ingest: If True, skip the ingest step (contracts must already be loaded).

    Returns:
        Tuple of (results_dict, unix_timestamp).
    """
    gt = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    contracts = gt["contracts"]
    questions = gt["questions"]
    timestamp = int(time.time())

    results: dict[str, Any] = {
        "metadata": {
            "timestamp": timestamp,
            "base_url": base_url,
            "ground_truth_version": gt.get("version", "2.0"),
            "total_questions": len(questions),
            "skip_ingest": skip_ingest,
        },
        "ingest_results": [],
        "question_results": [],
        "summary": {},
    }

    # ------------------------------------------------------------------
    # Step 1 — Ingest contracts
    # ------------------------------------------------------------------

    if not skip_ingest:
        print("\n[1/3] Ingesting contracts ...")
        for contract in contracts:
            pdf_path = BACKEND_DIR / contract["path"]
            if not pdf_path.exists():
                print(f"  WARN  not found: {pdf_path}")
                results["ingest_results"].append({
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
                print(f"  {'OK' if status in ('success', 'skipped') else 'FAIL':4s}  {contract['filename']}  ({latency:.1f}s, {chunks} chunks, status={status})")
                results["ingest_results"].append({
                    "filename": contract["filename"],
                    "status": status,
                    "chunks_created": chunks,
                    "latency_s": round(latency, 3),
                })
            except Exception as exc:
                latency = time.perf_counter() - t0
                print(f"  FAIL  {contract['filename']}  ({exc})")
                results["ingest_results"].append({
                    "filename": contract["filename"],
                    "status": "error",
                    "error": str(exc),
                    "latency_s": round(latency, 3),
                })
    else:
        print("\n[1/3] Skipping ingest (--skip-ingest flag set)")

    # ------------------------------------------------------------------
    # Step 2 — Run questions
    # ------------------------------------------------------------------

    print(f"\n[2/3] Running {len(questions)} evaluation questions ...")
    print(f"{'ID':<6} {'Contract Hit':<15} {'Clause Hit':<12} {'Latency':>9}  Question")
    print("-" * 80)

    for q in questions:
        qid = q["id"]
        question = q["question"]
        expected_contracts = q["expected_contracts"]
        expected_keywords = q["expected_keywords"]

        try:
            answer, latency = query_and_collect(base_url, question)
        except Exception as exc:
            print(f"{qid:<6} {'ERROR':<15} {'ERROR':<12} {'':>9}  {question[:50]}")
            results["question_results"].append({
                "id": qid,
                "question": question,
                "answer": "",
                "contract_hit": False,
                "clause_hit": False,
                "latency_s": None,
                "error": str(exc),
            })
            continue

        contract_hit = check_contract_hit(answer, expected_contracts)
        clause_hit = check_clause_hit(answer, expected_keywords)

        print(
            f"{qid:<6} {'PASS' if contract_hit else 'FAIL':<15} "
            f"{'PASS' if clause_hit else 'FAIL':<12} "
            f"{latency:>8.2f}s  {question[:50]}"
        )

        results["question_results"].append({
            "id": qid,
            "question": question,
            "description": q.get("description", ""),
            "expected_contracts": expected_contracts,
            "expected_keywords": expected_keywords,
            "answer_preview": answer[:300],
            "contract_hit": contract_hit,
            "clause_hit": clause_hit,
            "latency_s": round(latency, 3),
        })

    # ------------------------------------------------------------------
    # Step 3 — Summarise
    # ------------------------------------------------------------------

    evaluated = [r for r in results["question_results"] if r.get("error") is None]
    total = len(evaluated)
    contract_hits = sum(1 for r in evaluated if r["contract_hit"])
    clause_hits = sum(1 for r in evaluated if r["clause_hit"])
    latencies = [r["latency_s"] for r in evaluated if r["latency_s"] is not None]

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    latencies_sorted = sorted(latencies)
    p95_idx = max(0, int(len(latencies_sorted) * 0.95) - 1)
    p95_latency = latencies_sorted[p95_idx] if latencies_sorted else 0.0

    results["summary"] = {
        "total_questions": total,
        "contract_hit_count": contract_hits,
        "contract_hit_rate": round(contract_hits / total, 3) if total else 0.0,
        "clause_hit_count": clause_hits,
        "clause_accuracy": round(clause_hits / total, 3) if total else 0.0,
        "avg_latency_s": round(avg_latency, 3),
        "p95_latency_s": round(p95_latency, 3),
        "errors": len(results["question_results"]) - total,
    }

    print("\n" + "=" * 80)
    print("[3/3] Summary")
    print("=" * 80)
    print(f"  Contract Hit Rate : {results['summary']['contract_hit_rate']:.1%}  ({contract_hits}/{total})")
    print(f"  Clause Accuracy   : {results['summary']['clause_accuracy']:.1%}  ({clause_hits}/{total})")
    print(f"  Avg Latency       : {avg_latency:.2f}s")
    print(f"  P95 Latency       : {p95_latency:.2f}s")
    print(f"  Errors            : {results['summary']['errors']}")
    print("=" * 80)

    return results, timestamp


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and run the evaluation."""
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
        "--output-dir",
        default=str(EVAL_DIR),
        help="Directory to write results JSON (default: tests/eval/)",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("Riverty RAG Evaluation Harness")
    print(f"  Base URL      : {args.base_url}")
    print(f"  Skip Ingest   : {args.skip_ingest}")
    print(f"  Ground Truth  : {GROUND_TRUTH_PATH}")
    print(f"  Contracts dir : {BACKEND_DIR}/uploads/synthetic_legal_db/persistent_contracts/")
    print("=" * 80)

    results, timestamp = run_evaluation(args.base_url, args.skip_ingest)

    out_path = Path(args.output_dir) / f"eval_results_{timestamp}.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved → {out_path}")


if __name__ == "__main__":
    main()
