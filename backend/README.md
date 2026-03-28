# Backend — Riverty Contract Review

## What this system does
This backend lets the Riverty legal team upload contracts and ask plain-English questions
about them — the AI reads the documents and gives grounded answers with contract references.

## Tech Stack

| Tool | Version | Purpose | AWS Equivalent |
|---|---|---|---|
| FastAPI | 0.111.0 | HTTP API framework | API Gateway + Lambda |
| LangGraph | 0.1.5 | AI agent orchestration | Bedrock Agents |
| OpenAI GPT-4o | latest | Answer generation | Bedrock Claude/Titan |
| OpenAI text-embedding-3-small | latest | Vector embeddings | Bedrock Titan Embeddings |
| ChromaDB | 0.5.3 | Vector store (demo) | OpenSearch / Kendra |
| PyMuPDF | 1.24.5 | PDF text extraction | Textract |
| Tesseract | 0.3.10 | OCR for scanned images | Textract |
| LangDetect | 1.0.9 | Language detection | Comprehend |
| Pydantic | 2.7.4 | Request/response validation | — |

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
