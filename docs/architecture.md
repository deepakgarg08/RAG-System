# System Architecture — Riverty Contract Review

## Executive Summary

Riverty's legal team reviews dozens of supplier and service contracts every month — checking
for GDPR clauses, comparing termination terms, and flagging missing provisions. Until now
this work required manually opening each PDF, reading through dense legal language, and
keeping notes in a spreadsheet. A single review could take several hours; a cross-contract
comparison across ten documents could take a full working day.

This system changes that entirely. Legal staff upload contracts through a web interface and
then ask plain-English questions — "Which of our supplier contracts are missing a GDPR data
processing clause?" or "Show me the termination notice period across all contracts signed
in 2023." The system reads every contract it holds, finds the relevant passages, and returns
a sourced answer in seconds. Every answer cites exactly which contract and which section it
came from, so the legal team can verify the source with one click. No AI expertise is
required; if you can type a question, you can use this tool.

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Legal Team (Browser)                  │
│              React + TypeScript Frontend                 │
└──────────────────────┬──────────────────────────────────┘
                       │ REST / SSE
┌──────────────────────▼──────────────────────────────────┐
│                  FastAPI Backend                         │
│         POST /api/ingest  │  POST /api/query             │
│         GET  /health      │                              │
└──────┬───────────────────┼─────────────────────┬────────┘
       │                   │                     │
┌──────▼──────┐   ┌────────▼────────┐   ┌───────▼────────┐
│ ETL Pipeline│   │  LangGraph Agent│   │  File Storage  │
│  Extract    │   │  query_router   │   │  Local / Blob  │
│  Clean      │   │  retriever      │   └────────────────┘
│  Chunk      │   │  reasoner       │
│  Embed      │   │  formatter      │
│  Load       │   └────────┬────────┘
└──────┬──────┘            │
       │          ┌────────▼────────┐
       └─────────►│  Vector Store   │
                  │ ChromaDB (demo) │
                  │ Azure AI Search │
                  │   (production)  │
                  └─────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|---|---|
| **React Frontend** | File upload via drag-drop, SSE-streamed query display, source citation links |
| **FastAPI Backend** | HTTP routing, file type validation, CORS, lifespan management |
| **ETL Pipeline** | Extract text → clean → chunk → embed → load into vector store |
| **LangGraph Agent** | Classify query intent → retrieve chunks → reason → format with citations |
| **File Storage** | Persist uploaded files (local filesystem in demo, Azure Blob in production) |
| **Vector Store** | Store and search 1536-dim embeddings (ChromaDB in demo, Azure AI Search in prod) |

### API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | System status, document count, active mode (demo/production) |
| `POST` | `/api/ingest` | Upload a contract file and run the full ETL pipeline |
| `POST` | `/api/query` | Submit a question; returns SSE token stream |

### Key Architectural Principles

- **No business logic in routes** — API layer is purely HTTP translation; all logic lives in `etl/` or `rag/`
- **Strategy Pattern throughout ETL** — every extractor, loader, and transformer is swappable with one line
- **Single config source** — only `config.py` reads from `.env`; all other modules import from it
- **Grounded answers only** — the LLM system prompt restricts answers to retrieved chunks; hallucination is prevented by design
- **Demo / production parity** — every demo tool has a clearly marked swap comment pointing to its Azure equivalent

---

## Technology Stack

| Tool | Version | Purpose | AWS Equivalent | Why chosen |
|---|---|---|---|---|
| **FastAPI** | 0.111.0 | Web framework — async HTTP, auto-generated OpenAPI docs | API Gateway + Lambda | Native async, automatic request validation via Pydantic, SSE-friendly |
| **Uvicorn** | 0.30.1 | ASGI server — runs the FastAPI app | — | Standard ASGI runner; supports `--reload` for development |
| **OpenAI** | 2.30.0 | LLM calls (GPT-4o) and text embeddings | Bedrock | Same SDK works with Azure OpenAI — swap is 2 lines of code |
| **LangChain** | 1.2.13 | Document text splitting utilities | — | Mature text-splitter library with configurable chunk size and overlap |
| **LangChain OpenAI** | 1.1.12 | LangChain ↔ OpenAI integration layer | — | Required for LangGraph node compatibility |
| **LangChain Community** | 0.4.1 | Community integrations (loaders, tools) | — | Standard LangChain extension package |
| **LangChain Text Splitters** | 1.1.1 | `RecursiveCharacterTextSplitter` for chunking | — | Best-practice chunker for legal text; respects sentence boundaries |
| **LangGraph** | 1.1.3 | Multi-node AI agent state machine | Step Functions | Explicit graph = debuggable; each node independently testable |
| **ChromaDB** | 1.5.5 | Local vector store for demo | OpenSearch | Zero config, persists to disk, no credentials required |
| **PyMuPDF** | 1.27.2.2 | PDF text extraction | Textract | Fast, reliable, handles complex PDF layouts and multi-column text |
| **Pillow** | 12.1.1 | Image pre-processing before OCR | — | Standard Python image library; required by pytesseract |
| **pytesseract** | 0.3.13 | OCR for scanned JPEG/PNG contracts | Textract | Open-source Tesseract wrapper; works fully offline |
| **langdetect** | 1.0.9 | Detect contract language (EN/DE/etc.) | Comprehend | Lightweight, offline; sufficient for EN/DE bilingual contracts |
| **python-dotenv** | 1.2.2 | Load `.env` into environment at startup | SSM Parameter Store | Standard dev-time config loading |
| **python-multipart** | 0.0.9 | Multipart file upload parsing for FastAPI | — | Required by FastAPI for `UploadFile` support |
| **Pydantic** | 2.12.5 | Request/response validation and settings | — | FastAPI's native validator; strict typing enforced throughout |
| **pydantic-settings** | 2.13.1 | `Settings` class that reads from `.env` | — | Single config source of truth with environment variable aliasing |
| **httpx** | 0.27.0 | Async HTTP client (used in tests via TestClient) | — | Required by FastAPI `TestClient` for integration tests |
| **pytest** | 8.2.2 | Test runner | — | Industry standard; integrates with pytest-cov and pytest-asyncio |
| **pytest-asyncio** | 0.23.7 | Async test support | — | Required for testing `async def` route handlers |
| **pytest-cov** | 5.0.0 | Code coverage reporting | — | Generates HTML coverage reports |

### Production Azure Stack (not yet activated — swap instructions in each file)

| Azure Service | Replaces | SDK Package |
|---|---|---|
| Azure OpenAI | OpenAI API | `openai` (same SDK, different client init) |
| Azure AI Search | ChromaDB | `azure-search-documents==11.6.0b4` |
| Azure Blob Storage | Local filesystem | `azure-storage-blob==12.20.0` |
| Azure Document Intelligence | PyMuPDF + Tesseract | `azure-ai-formrecognizer==3.3.3` |
| Azure Container Apps | Local uvicorn | Docker image — no application code changes |
| Azure Key Vault | `.env` file | `azure-keyvault-secrets` |

---

## RAG vs Fine-tuning Decision

### Why RAG was chosen

Retrieval-Augmented Generation (RAG) retrieves relevant document chunks at query time and
feeds them into the LLM as context. Fine-tuning bakes document content into model weights
through additional supervised training.

For a legal contract review system, RAG is the only viable approach:

| Dimension | RAG | Fine-tuning |
|---|---|---|
| **New contracts** | Available instantly after ingestion (~10 seconds) | Requires full retraining cycle (hours, significant cost) |
| **Answer traceability** | Every answer cites exact source chunks with filenames | No mechanism to trace which training document influenced the output |
| **GDPR compliance** | Contract text stays in your vector store, not in model weights | Contract content baked into model weights — violates data minimisation principle |
| **Cost to update** | Near-zero — re-embed the changed document | Thousands of euros in GPU compute per retraining run |
| **Hallucination control** | System prompt strictly limits answers to retrieved chunks | No mechanism to prevent model drawing on baked-in knowledge |
| **Multi-language** | Works immediately for any language the base model supports | Would need balanced multilingual training data |
| **Model upgrades** | Swap base model, keep same vector store and all document data | Must retrain from scratch on the new base model |
| **Auditability** | Retrieved chunks are logged — auditors can see exactly what the model read | Black-box — no audit trail of which documents influenced an answer |

### Why fine-tuning is the wrong tool here

Fine-tuning is valuable when you need a model to adopt a new *style*, *format*, or
*domain vocabulary* consistently (e.g., always respond in a specific JSON schema or
adopt medical terminology). It is the wrong tool when you need the model to recall
*specific facts from specific documents* — that is exactly what a vector store is for.

The legal requirement that every answer must be attributable to a named contract section
makes RAG mandatory. A fine-tuned model cannot provide that attribution; a RAG system
does it automatically through chunk metadata returned alongside each result.
