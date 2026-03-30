# Riverty Contract Review — Implementation Status

> Last updated: 2026-03-30
> Branch: `main` (25 commits)
> Tests: **93 passed, 0 failed**

---

## What Has Been Implemented

### 1. Project Scaffold & Configuration

| Item | Status | Notes |
|---|---|---|
| Folder structure + READMEs | Done | Every subfolder has a README.md |
| `config.py` — Pydantic `Settings` singleton | Done | Reads all vars from `.env`; no hardcoded values |
| `APP_ENV` toggle | Done | `development` → demo stack, `production` → Azure stack |
| Docker image | Done | `python:3.12`, `Dockerfile` at backend root |
| Claude skills | Done | `write-adr`, `add-new-extractor`, `add-new-route`, `swap-to-azure`, `generate-test-contract` |
| `docs/env-reference.md` | Done | Full annotated `.env` template with demo and production sections |

---

### 2. ETL Pipeline (`backend/app/etl/`)

#### Extractors
| Component | Status | Notes |
|---|---|---|
| `BaseExtractor` abstract class | Done | `extract(path) → list[dict]` interface |
| `PDFExtractor` (PyMuPDF) | Done | Returns `[{"page_number": int, "text": str}]` per page |
| `OCRExtractor` (Tesseract) | Done | Converts scanned images/PDFs to text; falls back gracefully |
| Extractor registry in `pipeline.py` | Done | `.pdf` → PDFExtractor; `.jpg/.jpeg/.png` → OCRExtractor |

#### Transformers
| Component | Status | Notes |
|---|---|---|
| `TextCleaner` | Done | Collapses whitespace, strips pipe artifacts, normalises umlauts |
| Language detection (`langdetect`) | Done | Returns `"en"` or `"de"` attached to all chunk metadata |
| `ContentTypeDetector` | Done | Classifies doc as `qa`, `legal`, or `narrative`; supports German signals |
| `DocumentChunker` — Q&A strategy | Done | One chunk per Q+A pair (splits at `Q:` lines) |
| `DocumentChunker` — Legal strategy | Done | One chunk per section/article/clause/`§` header |
| `DocumentChunker` — Narrative strategy | Done | `RecursiveCharacterTextSplitter` (1500 chars / 200 overlap) |
| Rich chunk metadata | Done | 14 metadata fields: source_file, page_number, chunk_index, total_chunks, language, content_type, checksum, file_size_kb, extraction_method, is_scanned, embedding_model, upload_timestamp, text_preview, chunking_strategy |

#### Loaders
| Component | Status | Notes |
|---|---|---|
| `BaseLoader` abstract class | Done | `load()` and `get_document_count()` interface |
| `ChromaLoader` (demo) | Done | ChromaDB PersistentClient; HNSW cosine space |
| `AzureSearchLoader` (production) | Done | Azure AI Search SDK; hybrid search ready |
| `ChromaLoader` production swap | Done | Constructor branches on `APP_ENV`; delegates to `AzureSearchLoader` in production |

#### Pipeline Orchestrator
| Component | Status | Notes |
|---|---|---|
| `IngestionPipeline.ingest()` | Done | Full extract → clean → chunk → embed → load flow |
| `IngestionRegistry` | Done | MD5 checksum deduplication; embedding model version tracking |
| Duplicate detection | Done | Returns `status="skipped"` on second ingest of same file |
| Model mismatch guard | Done | Raises `409 Conflict` if existing data uses different embedding dims |
| `IngestionPipeline.get_document_count()` | Done | Delegates to ChromaLoader |

---

### 3. RAG Layer (`backend/app/rag/`)

| Component | Status | Notes |
|---|---|---|
| `EmbeddingService` | Done | Demo: `BAAI/bge-m3` (1024-dim); Production: Azure `text-embedding-3-large` (3072-dim) |
| Lazy-loaded local model | Done | `SentenceTransformer` local import; not loaded at all in production |
| Batch embedding | Done | `get_embeddings_batch()` for efficient bulk embedding |
| `ContractRetriever` | Done | ChromaDB cosine similarity; filters results below 0.40 similarity |
| LangGraph agent — `query_router` node | Done | Classifies query into `find_clause`, `compare_contracts`, `summarise`, or `general_question` |
| LangGraph agent — `retriever` node | Done | Calls `ContractRetriever`; returns `"No relevant contracts found."` on empty |
| LangGraph agent — `reasoner` node | Done | Builds grounded answer with hallucination-prevention system prompt |
| LangGraph agent — `formatter` node | Done | Adds clean source citations with `●/◐/○` relevance dots |
| `stream_query()` async generator | Done | Yields tokens for SSE; ends with `[DONE]` sentinel |
| Demo/production LLM swap | Done | `_get_llm_client()` returns `AsyncOpenAI` (demo) or `AsyncAzureOpenAI` (production) |
| Demo/production model name swap | Done | `_get_model_name()` returns `"gpt-4o"` (demo) or Azure deployment name (production) |

---

### 4. API Routes (`backend/app/api/routes/`)

| Route | Method | Status | Notes |
|---|---|---|---|
| `/health` | GET | Done | Returns `{status, mode, document_count, version}` |
| `/api/ingest` | POST | Done | Multipart upload; validates extension; runs full ETL pipeline |
| `/api/query` | POST | Done | Accepts `{"question": str}`; returns SSE stream |
| `/api/files/{filename}` | GET | Done | Serves uploaded contracts for in-browser PDF viewing; blocks path traversal |
| `/api/suggested-questions` | GET | Done | Returns static list of suggested questions for the UI |

---

### 5. Storage (`backend/app/storage/`)

| Component | Status | Notes |
|---|---|---|
| `LocalStorage` (demo) | Done | Saves uploaded files to `UPLOAD_DIR` |
| `AzureBlobStorage` (production) | Done | Azure Blob Storage SDK; versioning + legal hold ready |
| `LocalStorage` production swap | Done | Constructor delegates to `AzureBlobStorage` when `APP_ENV=production` |

---

### 6. Frontend (`frontend/src/`)

| Component | Status | Notes |
|---|---|---|
| `App.tsx` — root component | Done | Owns health state, wires all hooks and handlers |
| `AppLayout.tsx` | Done | Fixed navy header, 2-panel body (sidebar + main), footer |
| Header — 3-state connection indicator | Done | `Connecting…` (initial) / `N documents indexed` (green) / `Disconnected` (red) |
| `FileUpload.tsx` | Done | Drag-and-drop + click; shows file name before upload |
| `UploadStatus.tsx` | Done | Per-file status badges (uploading / success / error) |
| `QueryInput.tsx` | Done | Text area + submit button; disabled when no documents indexed |
| `StreamingResponse.tsx` | Done | Renders SSE token stream progressively; shows source citations |
| `SuggestedQueries.tsx` | Done | Clickable suggestion chips; disabled during streaming |
| `StatusDot.tsx` | Done | Amber/green/red dot reflecting connection state |
| `useFileUpload` hook | Done | Manages upload state; calls `/api/ingest` |
| `useStreamingQuery` hook | Done | Manages SSE stream; calls `/api/query` |
| `api.ts` service | Done | `getHealth()`, `uploadFile()`, `streamQuery()` |

> **Note:** Frontend changes are intentionally not committed (per project convention — frontend committed separately).

---

### 7. Testing (`backend/tests/`)

| Test File | Coverage | Tests |
|---|---|---|
| `test_etl.py` | TextCleaner, DocumentChunker, PDFExtractor, ChromaLoader, IngestionPipeline, ContentTypeDetector | ~35 tests |
| `test_rag.py` | EmbeddingService, ContractRetriever, all 4 LangGraph nodes, stream_query | ~25 tests |
| `test_routes.py` | `/health`, `/api/ingest`, `/api/query` routes; error cases; SSE headers | ~15 tests |
| `test_integration.py` | Full ingest → retrieve → answer E2E flow; German/English cross-language | ~8 tests |
| `conftest.py` | Shared fixtures: mock embeddings, temp ChromaDB, synthetic PDF contracts | — |
| `generate_contracts.py` | Generates 4 synthetic bilingual contracts (NDA, service, vendor, German) | — |
| `create_scanned_jpeg.py` | Creates test JPEG for OCR extractor path | — |

**Total: 93 tests — all passing.**

---

### 8. Documentation (`docs/`)

| File | Status | Notes |
|---|---|---|
| `architecture.md` | Done | System components, data flow, component diagram |
| `azure-services.md` | Done | One-line switch table, service mapping, cost estimates, migration checklist |
| `decisions.md` | Done | 7 ADRs: RAG vs fine-tuning, ChromaDB vs Azure, LangGraph, SSE, chunking, test data, OpenAI vs Azure |
| `data-flow.md` | Done | ETL and query flow diagrams |
| `env-reference.md` | Done | Full annotated `.env` with demo and production sections |
| `implementation-guide.md` | Done | Step-by-step developer setup |
| `testing-guide.md` | Done | How to run tests, coverage, test modes |
| `pipeline-commands.md` | Done | Common CLI commands |
| `evaluation_shareable.md` | Done | Project evaluation, metrics, gap analysis |

---

## What Is Remaining / Known Gaps

### High Priority

| Gap | Description | Fix needed |
|---|---|---|
| **Route tests for `/api/files` and `/api/suggested-questions`** | `test_routes.py` has no tests for these two routes added late in the project | Add `test_files_route_serves_pdf` and `test_suggested_questions_returns_list` to `test_routes.py` |
| **Re-ingest existing data** | Existing ChromaDB data was indexed with 1000-char chunks; `MAX_CHUNK_SIZE` is now 1500. Old chunks won't benefit from the improvement until data is cleared and re-ingested | Run `rm -rf backend/chroma_db/` then re-ingest all contracts |
| **ADR-005 outdated** | ADR-005 documents chunk size as 1000 chars / 200 overlap, but it was changed to 1500/200 in commit `de754e7` | Update `docs/decisions.md` ADR-005 to reflect 1500-char chunk size and the reasoning |

### Medium Priority

| Gap | Description | Fix needed |
|---|---|---|
| **Azure production path not E2E tested** | `AzureSearchLoader`, `AzureBlobStorage`, and `AsyncAzureOpenAI` exist and are code-correct, but have never been run against real Azure credentials | Set up Azure resources in a test subscription; run smoke test |
| **No contract listing endpoint** | There is no `GET /api/files` (list all uploaded contracts) — only `GET /api/files/{filename}` (download one) | Add list endpoint to `files.py`; update frontend sidebar to load existing contracts from backend |
| **Frontend sidebar shows only session uploads** | After a page refresh, the uploaded contracts sidebar is empty even though documents are indexed in ChromaDB | Implement `GET /api/files` listing endpoint + fetch on app load |
| **`uploaded_by` is always "anonymous"** | No user identity is passed through the ingest flow; all audit metadata defaults to `"anonymous"` | Add optional `X-Uploaded-By` header to `/api/ingest`; pass through to pipeline |
| **OCR path not in integration tests** | `test_integration.py` covers PDF ingest only; no integration test runs a JPEG through the full OCR → chunk → store → retrieve flow | Add `test_scanned_image_integration` to `test_integration.py` |

### Low Priority / Future Work

| Gap | Description |
|---|---|
| **Contract type classification** | `ContentTypeDetector` classifies document structure (Q&A/legal/narrative) but not contract type (NDA / Service Agreement / Vendor). `contract_type` is noted in `chunker.py` as a planned future field. |
| **Streaming error handling in frontend** | If the SSE stream drops mid-response, the frontend shows partial output with no error indicator. |
| **Multi-file ingest** | `/api/ingest` accepts one file per request. Batch upload (zip of contracts) would improve UX. |
| **Similarity threshold tuning** | `_MIN_SIMILARITY = 0.40` in `retriever.py` is a hardcoded constant — should be configurable via `config.py`. |
| **Azure Document Intelligence (OCR)** | `AzureDocIntelligenceExtractor` is referenced in `docs/azure-services.md` and `config.py` has `AZURE_DOC_INTELLIGENCE_ENDPOINT` but no concrete implementation exists. Production OCR still uses Tesseract. |
| **Production CORS config** | `main.py` has `allow_origins=["http://localhost:3000"]` — must be updated for production domain before deployment. |
| **Chunk size constant in ADR** | ADR-005 says 1000/200 but current setting is 1500/200 — minor doc debt. |

---

## Architecture at a Glance

```
User → React UI
         │
         ├─ POST /api/ingest ──► LocalStorage (saves file)
         │                        └─► IngestionPipeline
         │                              ├─ PDFExtractor / OCRExtractor
         │                              ├─ TextCleaner + DocumentChunker
         │                              ├─ EmbeddingService (bge-m3 / Azure)
         │                              └─ ChromaLoader (ChromaDB / Azure Search)
         │
         └─ POST /api/query ───► stream_query()
                                  └─► LangGraph Agent
                                        ├─ query_router  (classify intent)
                                        ├─ retriever     (semantic search)
                                        ├─ reasoner      (GPT-4o / Azure GPT-4o)
                                        └─ formatter     (source citations)
                                              │
                                              └─► SSE token stream → UI
```

## One-Line Production Switch

Set `APP_ENV=production` in `backend/.env`. No code changes required.

| Component | `development` | `production` |
|---|---|---|
| LLM | `AsyncOpenAI` (gpt-4o) | `AsyncAzureOpenAI` (gpt-4o via Azure) |
| Embeddings | `BAAI/bge-m3` local, 1024-dim | Azure `text-embedding-3-large`, 3072-dim |
| Vector store | ChromaDB local | Azure AI Search |
| File storage | Local filesystem | Azure Blob Storage |

> **Warning:** Switching embedding models requires re-ingesting all contracts (dimension change 1024 → 3072). The `IngestionRegistry` will raise a `409 Conflict` if you try to query with mismatched dims.
