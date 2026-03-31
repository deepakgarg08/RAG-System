# Evaluation Metrics — Riverty RAG Contract Review

**Created:** 2026-03-31  
**Feature branch:** `betterment`  
**Scope:** Minimum-viable offline evaluation harness (no RAGAS dependency)

---

## What Was Built

A lightweight evaluation harness at `backend/tests/eval/` that:

1. **Builds a ground-truth dataset** (`ground_truth.json`) — 4 synthetic contracts × 10 questions with known-correct answers.
2. **Ingests contracts via the live API** — converts `.txt` samples to PDFs (same `fitz` pattern as `conftest.py`) and POSTs to `/api/ingest`.
3. **Runs each question through `/api/query`** — consumes the SSE stream and collects the full answer.
4. **Checks three metrics per question:**
   - `contract_hit` — did the answer name the expected source contract?
   - `clause_hit` — did the answer contain the expected clause keywords?
   - `latency_s` — wall-clock seconds from request to last token.
5. **Saves a timestamped results file** — `eval_results_{unix_timestamp}.json` in `tests/eval/`.

---

## Files

| File | Purpose |
|------|---------|
| `backend/tests/eval/ground_truth.json` | Dataset — 4 contracts + 10 Q&A pairs with expected contract names and keyword oracles |
| `backend/tests/eval/run_eval.py` | Evaluation script — ingest → query → score → report |
| `backend/tests/eval/eval_results_*.json` | Output — one file per run (gitignored) |

---

## Ground-Truth Dataset

### Contracts

| Filename | Type | Language | Has GDPR | Has Termination |
|----------|------|----------|----------|----------------|
| `contract_nda_techcorp_2023.pdf` | NDA | EN | Yes | Yes (30 days) |
| `contract_service_datasystems_2022.pdf` | Service Agreement | EN | No | Yes (Net 30) |
| `contract_vendor_2023_no_termination.pdf` | Vendor Agreement | EN | Yes | **No** |
| `vertrag_dienstleistung_mueller_2024.pdf` | Dienstleistungsvertrag | DE | Yes | Yes (3 months) |

### Questions

| ID | Question | Tests |
|----|----------|-------|
| Q01 | Governing law in TechCorp NDA? | Clause extraction |
| Q02 | Monthly fee in DataSystems agreement? | Numeric fact extraction |
| Q03 | Which contracts lack a termination clause? | `find_missing` query type |
| Q04 | Days notice to terminate TechCorp NDA? | Specific numeric value |
| Q05 | Which contract is in German? | Language-aware retrieval |
| Q06 | Does TechCorp NDA have GDPR clause? | Clause existence detection |
| Q07 | Invoice payment period in DataSystems agreement? | Payment term extraction |
| Q08 | Does CloudVendor agreement include GDPR obligations? | Clause presence |
| Q09 | What services does Müller Consulting provide? | German-language extraction |
| Q10 | Max annual price increase in CloudVendor agreement? | Pricing cap extraction |

---

## Metrics Explained

### Per-Question Metrics

| Metric | Type | Pass condition |
|--------|------|---------------|
| `contract_hit` | bool | Response text contains the expected contract filename stem (case-insensitive, partial-match on meaningful tokens) |
| `clause_hit` | bool | Response text contains at least one expected keyword phrase |
| `latency_s` | float | Wall-clock seconds — measured from `requests.post()` to last SSE token |

### Aggregate Summary

| Metric | Formula |
|--------|---------|
| `contract_hit_rate` | `contract_hit_count / total_questions` |
| `clause_accuracy` | `clause_hit_count / total_questions` |
| `avg_latency_s` | Mean across all successful queries |
| `p95_latency_s` | 95th-percentile latency |

---

## How to Run

### Prerequisites

1. Start the backend server:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. Ensure your `.env` has a valid `OPENAI_API_KEY`.

### Run Full Evaluation (ingest + query)

```bash
cd backend
python tests/eval/run_eval.py
```

### Skip Ingest (contracts already loaded)

```bash
python tests/eval/run_eval.py --skip-ingest
```

### Custom API URL

```bash
python tests/eval/run_eval.py --base-url http://my-staging-server:8000
```

Or via environment variable:
```bash
BASE_URL=http://staging:8000 python tests/eval/run_eval.py
```

### Output

The script prints a live table during execution:

```
ID     Contract Hit    Clause Hit   Latency  Question
----------------------------------------------------------------------
Q01    PASS            PASS            3.41s  What is the governing law in the NDA...
Q02    PASS            PASS            2.87s  What is the monthly service fee in th...
Q03    PASS            FAIL            4.12s  Which contracts are missing a terminat...
...

================================================================================
[3/3] Summary
================================================================================
  Contract Hit Rate : 90.0%  (9/10)
  Clause Accuracy   : 80.0%  (8/10)
  Avg Latency       : 3.52s
  P95 Latency       : 5.10s
  Errors            : 0
================================================================================

Results saved → tests/eval/eval_results_1774915200.json
```

---

## Design Decisions

### Why not RAGAS?

RAGAS requires LLM calls for faithfulness/answer-relevance scoring — it costs money, adds latency, and introduces non-determinism. For a demo/interview context, deterministic string-matching oracles (contract names + clause keywords) are faster, cheaper, and easier to inspect.

### Why binary hits instead of fuzzy scores?

The ground-truth questions have unambiguous answers (specific contract names, numeric values, clause titles). Binary pass/fail makes it easy to see regressions at a glance. Fuzzy semantic similarity can be added later via embedding cosine distance if needed.

### Why SSE consumption instead of a separate non-streaming endpoint?

The evaluation reuses the real production code path end-to-end. Adding a batch endpoint just for eval would mean testing different code. The SSE parser in `run_eval.py` is 8 lines and mirrors the frontend pattern exactly.

---

## Adding More Questions

Edit `ground_truth.json`:

```json
{
  "id": "Q11",
  "question": "Your question here?",
  "expected_contracts": ["contract_filename_stem"],
  "expected_keywords": ["keyword1", "keyword2"],
  "description": "What this question tests"
}
```

No code changes needed — `run_eval.py` reads the JSON dynamically.

---

## Adding More Sample Contracts

1. Add `.txt` file to `backend/tests/sample_contracts/`
2. Add an entry to `ground_truth.json` under `"contracts"`
3. Add question entries that reference the new contract filename stem
4. Update `backend/tests/sample_contracts/README.md`
