# tests/eval — RAG Evaluation Harness

Minimum-viable evaluation for the Riverty contract review RAG system.
No RAGAS, no LLM-as-judge — fast deterministic string-matching oracles.

## Files

| File | Purpose |
|------|---------|
| `ground_truth.json` | 4 sample contracts + 10 questions with expected answers |
| `run_eval.py` | Ingest → query → score → report |
| `eval_results_*.json` | Output files (gitignored) |

## Quick Start

```bash
# 1. Start the backend
cd backend && uvicorn app.main:app --reload

# 2. Run the evaluation (ingest + all 10 questions)
python tests/eval/run_eval.py

# 3. Skip ingest if contracts are already loaded
python tests/eval/run_eval.py --skip-ingest
```

## Metrics

- **contract_hit_rate** — % of answers that named the expected source contract
- **clause_accuracy** — % of answers that contained the expected clause keywords  
- **avg_latency_s / p95_latency_s** — query latency statistics

Full documentation: [docs/1774915200_eval_metrics.md](../../docs/1774915200_eval_metrics.md)
