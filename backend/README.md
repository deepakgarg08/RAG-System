# Backend — Riverty Contract Review

## What this system does
This backend lets the Riverty legal team upload contracts and ask plain-English questions
about them — the AI reads the documents and gives grounded answers with contract references.

## Tech Stack

| Tool | Version | Purpose | AWS Equivalent |
|---|---|---|---|
| FastAPI | 0.111.0 | HTTP API framework | API Gateway + Lambda |
| LangGraph | 1.1.3 | AI agent orchestration | Bedrock Agents / Step Functions |
| LangChain | 1.2.13 | Text splitting, LLM utilities | — |
| OpenAI GPT-4o | via openai 2.30.0 | Answer generation | Bedrock Claude/Titan |
| OpenAI text-embedding-3-small | via openai 2.30.0 | Vector embeddings | Bedrock Titan Embeddings |
| ChromaDB | 1.5.5 | Vector store (demo) | OpenSearch / Kendra |
| PyMuPDF | 1.27.2.2 | PDF text extraction | Textract |
| pytesseract | 0.3.13 | OCR for scanned images | Textract |
| LangDetect | 1.0.9 | Language detection | Comprehend |
| rank-bm25 | 0.2.2 | BM25 keyword index for hybrid retrieval | — |
| pyspellchecker | 0.8.2 | OCR spell correction (EN + DE) | — |
| Pydantic | 2.12.5 | Request/response validation | — |
| pydantic-settings | 2.13.1 | Config from .env | SSM Parameter Store |

## Folder Map

| Folder | Responsibility |
|---|---|
| `app/` | Main Python package — entry point, config, models |
| `app/api/` | HTTP boundary — routes only, zero business logic |
| `app/etl/` | Document ingestion pipeline — extract, transform, load |
| `app/rag/` | AI query layer — embeddings, retrieval, LangGraph agent |
| `app/storage/` | File persistence — raw uploaded contract storage |
| `tests/` | Pytest test suite with offline mocking |

## Two Modes

### DEMO (runs on a laptop, no cloud required)
- Vector store: ChromaDB (local disk, zero config)
- Embeddings + LLM: OpenAI API (requires `OPENAI_API_KEY`)
- File storage: local `./uploads` directory
- PDF/OCR: PyMuPDF + Tesseract (local binaries)

### PRODUCTION (Azure services)
- Vector store: Azure AI Search
- Embeddings + LLM: Azure OpenAI
- File storage: Azure Blob Storage
- PDF/OCR: Azure Document Intelligence

See `.claude/skills/swap-to-azure.md` for the migration steps.

## Quick Start
See [docs/setup.md](../docs/setup.md) for full instructions.

## Evaluation

A minimum-viable evaluation harness lives in `tests/eval/`.  
It does **not** use RAGAS — metrics are fast, deterministic, and free:

| Metric | What it checks |
|--------|---------------|
| Contract Hit Rate | Did the answer cite the right source contract? |
| Clause Accuracy | Did the answer contain the expected clause keywords? |
| Latency (avg / P95) | Wall-clock seconds per query |

```bash
# Start the server first, then:
cd backend
python tests/eval/run_eval.py
```

See [docs/1774915200_eval_metrics.md](../docs/1774915200_eval_metrics.md) for full documentation.
