# Evaluation Metrics — Riverty RAG Contract Review

**Created:** 2026-03-31  
**Feature branch:** `betterment`  
**Ground-truth version:** 3.0  
**Scope:** Minimum-viable offline evaluation harness (no RAGAS dependency)

---

## What Was Built

A lightweight evaluation harness at `backend/tests/eval/` covering all three operational
modes of the RAG system.

### Three operational modes

| Mode | API endpoint | Scenario |
|------|-------------|---------|
| Mode 1 — Single-doc | `POST /api/analyze?mode=single` | Upload a temp contract, ask questions directly about it |
| Mode 2 — DB query | `POST /api/query` | Ask questions against the persistent vector DB |
| Mode 3 — Compare | `POST /api/analyze?mode=compare` | Upload a temp contract, compare it against the DB |

### Metrics per mode

| Metric | Mode 1 | Mode 2 | Mode 3 |
|--------|:------:|:------:|:------:|
| `clause_hit` — answer contains expected keywords | ✓ | ✓ | ✓ |
| `contract_hit` — answer names the correct source contract | — | ✓ | — |
| `absent_keywords_ok` — forbidden phrases absent from answer | ✓ | — | — |
| `comparison_hit` — comparison point mentioned | — | — | ✓ |
| `Precision@K` — fraction of retrieved chunks that are relevant | — | ✓ | — |
| `Recall@K` — fraction of relevant chunks that were retrieved | — | ✓ | — |
| `MRR` — Mean Reciprocal Rank of first relevant chunk | — | ✓ | — |
| `faithfulness` — LLM-as-judge, 0.0–1.0 | ✓ | ✓ | ✓ |
| `latency_s` — wall-clock seconds per query | ✓ | ✓ | ✓ |

---

## Files

| File | Purpose |
|------|---------|
| `backend/tests/eval/ground_truth.json` | v3.0 dataset — 4 persistent contracts, 2 temp contracts, 10 Mode-2 Qs, 5 Mode-1 Qs, 4 Mode-3 Qs |
| `backend/tests/eval/run_eval.py` | Evaluation harness — ingest → eval all modes → report |
| `backend/app/api/routes/eval_retrieve.py` | `POST /api/eval/retrieve` — returns raw retrieved chunks for IR metric computation |
| `backend/tests/eval/eval_results_*.json` | Output — one timestamped file per run (gitignored) |

---

## Ground-Truth Dataset (v3.0)

### Persistent contracts (DB)

| Filename | GDPR | Termination | Liability |
|----------|:----:|:-----------:|:---------:|
| `contract_gdpr_strict.pdf` | Full (EU 2016/679) | Either party, 15 days notice | Capped at 12 months fees |
| `contract_missing_gdpr.pdf` | **Absent** (DATA USAGE only) | Weak — provider discretion only | Capped at 12 months fees |
| `contract_unlimited_liability.pdf` | Full (EU 2016/679) | Either party, 15 days notice | **Unlimited** (direct + indirect + consequential) |
| `contract_weak_termination.pdf` | Full (EU 2016/679) | **Weak** — provider discretion only | Capped at 12 months fees |

All four contracts have Germany as governing law.

### Temp contracts (uploaded for Mode 1 / Mode 3)

| Filename | Profile | Most similar DB contract |
|----------|---------|------------------------|
| `temp_contract_1.pdf` | no GDPR + weak termination + unlimited liability | `contract_missing_gdpr` (pages 1+2) + `contract_unlimited_liability` (page 3) |
| `temp_contract_2.pdf` | full GDPR + fair termination + capped liability | `contract_gdpr_strict` (all pages) |

---

## Metrics Explained

### Binary hit metrics

| Metric | Pass condition |
|--------|---------------|
| `contract_hit` | Response contains the expected contract filename stem (or any token > 3 chars from it) |
| `clause_hit` | Response contains at least one expected keyword phrase (case-insensitive) |
| `absent_keywords_ok` | None of the forbidden phrases appear in the response |
| `comparison_hit` | At least one expected comparison point is present in the response |

### IR metrics (Mode 2 only)

Computed from `/api/eval/retrieve` — the same retrieval pipeline (HybridRetriever → CrossEncoder reranker → MMR) as the query agent, but returning raw chunks instead of an LLM answer.

Relevance labels are defined at `(source_file, page_number)` granularity. Each contract page contains exactly one clause, so page = chunk in this dataset.

| Metric | Formula |
|--------|---------|
| **Precision@K** | `(relevant chunks in top-K) / K` |
| **Recall@K** | `(relevant chunks in top-K) / (total relevant chunks)` |
| **MRR** | `1 / rank_of_first_relevant_chunk` (0 if none in top-K) |

### Faithfulness (LLM-as-judge)

Implemented without RAGAS. Uses a direct OpenAI GPT-4o-mini call with a 0–10 scale prompt:

- **Mode 2**: context = retrieved chunks from `/api/eval/retrieve`
- **Mode 1**: context = full extracted document text (PDF parsed locally)
- **Mode 3**: context = DB chunks retrieved for the same question

Score is normalised to 0.0–1.0. Requires `OPENAI_API_KEY` to be set; if absent, faithfulness is skipped and reported as `n/a`.

### Latency

Wall-clock seconds from `requests.post()` call to last SSE `[DONE]` token, measured with `time.perf_counter()`. Includes network round-trip + LLM generation time.

---

## How to Run

### Prerequisites

1. Start the backend server:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. Set environment variables:
   ```bash
   export OPENAI_API_KEY=sk-...   # required for faithfulness judging
   ```

3. Ingest persistent contracts (first run only) — or use `--skip-ingest` if already loaded.

### Run all three modes

```bash
cd backend
python tests/eval/run_eval.py
```

### Skip ingest (contracts already in the DB)

```bash
python tests/eval/run_eval.py --skip-ingest
```

### Run specific modes only

```bash
# Mode 2 only (DB query)
python tests/eval/run_eval.py --skip-ingest --modes 2

# Modes 1 and 3 (needs no persistent DB state, but server must be running)
python tests/eval/run_eval.py --skip-ingest --modes 1,3
```

### Custom API URL or top-K

```bash
python tests/eval/run_eval.py --base-url http://staging:8000 --top-k 10
# or via env var
BASE_URL=http://staging:8000 python tests/eval/run_eval.py
```

### Sample output

```
Mode 2 — Database queries (10 questions)
ID      C-Hit   Kw-Hit   P@K     R@K     MRR     Faith   Lat      Question
----------------------------------------------------------------------------------------------------
M2Q01   PASS    PASS     0.13    1.00    1.00    0.90    3.41s    Which contract is missing a GDPR...
M2Q02   PASS    PASS     0.13    1.00    1.00    0.88    2.87s    Which contract has unlimited liab...
...

================================================================================
EVALUATION SUMMARY
================================================================================

Mode 2 — Database Query (10 questions)
  Contract Hit Rate  : 90.0%
  Clause Hit Rate    : 80.0%
  Mean Precision@K   : 0.131
  Mean Recall@K      : 0.900
  Mean MRR           : 0.875
  Mean Faithfulness  : 0.87
  Avg Latency        : 3.52s
  P95 Latency        : 5.10s
  Errors             : 0

Mode 1 — Single-Doc Analysis (5 questions)
  Clause Hit Rate    : 100.0%
  Absent KW Pass     : 100.0%
  Mean Faithfulness  : 0.91
  Avg Latency        : 4.20s

Mode 3 — Compare Uploaded vs DB (4 questions)
  Keyword Hit Rate   : 75.0%
  Comparison Hit Rate: 100.0%
  Mean Faithfulness  : 0.85
  Avg Latency        : 5.80s
================================================================================

Results saved → tests/eval/eval_results_1774915200.json
```

---

## Architecture

### Eval retrieve endpoint

`POST /api/eval/retrieve` is a non-production endpoint registered in `main.py`. It runs the identical retrieval pipeline as the LangGraph agent — HybridRetriever (BM25 + dense, RRF merge) → CrossEncoder reranker → MMR filter — and returns the raw chunks. This lets IR metrics be computed against the real retrieval logic, not a simplified version.

### Why not RAGAS?

RAGAS requires its own LLM pipeline and external dependencies. For this demo:
- Binary hit metrics are deterministic, cheap, and easy to inspect
- Faithfulness is covered by a direct 8-line GPT-4o-mini call with a controlled prompt
- IR metrics give retrieval signal independent of LLM generation quality

### Why SSE consumption end-to-end?

The evaluation reuses the exact same code path as the frontend — SSE streaming from `/api/query` and `/api/analyze`. This means the eval tests the production path, not a synthetic shortcut.

---

## Extending the Dataset

### Add a Mode 2 question

```json
{
  "id": "M2Q11",
  "question": "Your question about the DB contracts?",
  "expected_contracts": ["contract_gdpr_strict"],
  "expected_keywords": ["keyword1", "keyword2"],
  "relevant_chunks": [
    {"source_file": "contract_gdpr_strict.pdf", "pages": [1]}
  ],
  "description": "What this tests"
}
```

### Add a Mode 1 question

```json
{
  "id": "M1Q06",
  "upload_file": "temp_contract_1.pdf",
  "question": "Does this contract specify a governing law?",
  "expected_keywords": ["germany", "german"],
  "expected_absent_keywords": ["france", "uk"],
  "description": "Governing law check on temp_contract_1"
}
```

### Add a Mode 3 question

```json
{
  "id": "M3Q05",
  "upload_file": "temp_contract_2.pdf",
  "question": "How does the governing law clause compare to the database?",
  "expected_keywords": ["germany", "similar", "all"],
  "expected_comparison_points": ["same governing law as all DB contracts"],
  "description": "All contracts share Germany governing law"
}
```
