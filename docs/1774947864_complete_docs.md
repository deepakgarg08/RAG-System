# Riverty Contract Review — Complete Interview & Presentation Guide

> **Prepared:** 2026-03-31 | **Branch:** `betterment` | **Build:** 93 tests passing

---

## TABLE OF CONTENTS

1. [What is this project?](#1-what-is-this-project)
2. [Problem Statement](#2-problem-statement)
3. [Solution Architecture (Overview)](#3-solution-architecture-overview)
4. [Full File & Folder Structure](#4-full-file--folder-structure)
5. [Tech Stack — Every Tool and WHY](#5-tech-stack--every-tool-and-why)
6. [Data Flow — Step by Step](#6-data-flow--step-by-step)
7. [Three Analysis Modes](#7-three-analysis-modes)
8. [Demo vs Production — The Swap Pattern](#8-demo-vs-production--the-swap-pattern)
9. [ETL Pipeline Deep Dive](#9-etl-pipeline-deep-dive)
10. [RAG Layer Deep Dive](#10-rag-layer-deep-dive)
11. [API Routes Reference](#11-api-routes-reference)
12. [Frontend Architecture](#12-frontend-architecture)
13. [How to Run the Project](#13-how-to-run-the-project)
14. [15-Minute Presentation Script & Slide Plan](#14-15-minute-presentation-script--slide-plan)
15. [Interview Q&A — Every Question They Could Ask](#15-interview-qa--every-question-they-could-ask)

---

## 1. What is this project?

**Riverty Contract Review** is an AI-powered legal contract analysis system.

It allows Riverty's legal team to:
- Upload contracts (PDF, scanned images)
- Ask plain-English questions about them ("Does this contract have a GDPR clause?")
- Compare a new contract against every existing contract in the knowledge base
- Detect missing or risky clauses across all stored contracts
- Get compliance check results in structured form (compliant / violations list / explanation)

The system runs in **demo mode** (on a laptop, no cloud required) and is architected to **swap to Azure production services** with minimal code change.

---

## 2. Problem Statement

Riverty's legal team reviews hundreds of contracts annually. The manual review process has three pain points:

| Pain Point | Impact |
|---|---|
| Time — reading full PDFs clause by clause | Hours per contract, delays business decisions |
| Inconsistency — different reviewers focus on different clauses | Compliance risks slip through |
| No cross-contract search — can't ask "which contracts have unlimited liability?" | Can't audit the full portfolio quickly |

**What the system solves:**

- **Instant answers** — ask a plain-English question, get an answer with source citations in seconds
- **Compliance check** — automated structured check against GDPR, termination, liability, governing law
- **Portfolio analysis** — semantic search across all stored contracts to find patterns and gaps

---

## 3. Solution Architecture (Overview)

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                            │
│                    React + TypeScript SPA                        │
│   ┌──────────────┐  ┌────────────────┐  ┌──────────────────┐   │
│   │ Search KB    │  │ Analyze Doc    │  │ Compare with DB  │   │
│   │ (MODE 3)     │  │ (MODE 1)       │  │ (MODE 2)         │   │
│   └──────┬───────┘  └───────┬────────┘  └────────┬─────────┘   │
└──────────┼──────────────────┼───────────────────-┼─────────────┘
           │ SSE Stream       │ SSE Stream          │ SSE Stream
           ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend  :8000                        │
│  POST /api/query   POST /api/analyze   POST /api/compliance     │
│                    POST /api/ingest                             │
├───────────────┬─────────────────────────────────────────────────┤
│  ETL Pipeline │           RAG Layer                             │
│               │                                                 │
│  PDF/OCR →    │  EmbeddingService  →  ContractRetriever        │
│  Cleaner  →   │  (BAAI/bge-m3)        (ChromaDB cosine)        │
│  Chunker  →   │                                                 │
│  Embedder →   │  LangGraph Agent:                               │
│  ChromaDB     │  query_router → retriever → reasoner → formatter│
└───────────────┴─────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────┐
│  ChromaDB (demo)     │  ← swap → Azure AI Search (prod)
│  Local ./chroma_db/  │
└──────────────────────┘
```

---

## 4. Full File & Folder Structure

```
riverty-contract-review/
│
├── CLAUDE.md                    # AI coding rules and project conventions
├── .gitignore
│
├── backend/
│   ├── README.md                # Tech stack, folder map, quick start
│   ├── SETUP.md                 # Step-by-step setup, Docker, troubleshooting
│   ├── Dockerfile               # Python 3.12 image
│   ├── requirements.txt         # All Python dependencies pinned
│   ├── .env.example             # Template for all env vars
│   ├── run_pipeline.sh          # Ingest documents via API + Q&A
│   ├── run_rag.sh               # Q&A only (no ingest)
│   ├── run_tests.sh             # pytest + coverage
│   ├── ingestion_registry.json  # MD5-based deduplication registry
│   │
│   └── app/
│       ├── __init__.py
│       ├── main.py              # FastAPI app factory; registers all routers
│       ├── config.py            # Pydantic Settings singleton — reads .env
│       ├── models.py            # Shared Pydantic models (ComplianceResult, etc.)
│       ├── state.py             # Shared app-level singletons (embedding model)
│       │
│       ├── api/
│       │   └── routes/
│       │       ├── health.py        # GET /health
│       │       ├── ingest.py        # POST /api/ingest (persistent KB)
│       │       ├── query.py         # POST /api/query  (MODE 3 — SSE)
│       │       ├── analyze.py       # POST /api/analyze (MODE 1 & 2 — SSE)
│       │       ├── compliance.py    # POST /api/compliance (structured JSON)
│       │       ├── files.py         # GET /api/files/{filename}
│       │       └── suggestions.py   # GET /api/suggested-questions
│       │
│       ├── etl/
│       │   ├── base.py              # Abstract BaseExtractor, BaseTransformer
│       │   ├── pipeline.py          # IngestionPipeline orchestrator
│       │   ├── registry.py          # IngestionRegistry (MD5 dedup + model guard)
│       │   ├── compliance_storage.py # Fire-and-forget external API archival
│       │   ├── extractors/
│       │   │   ├── pdf_extractor.py     # PyMuPDF page-by-page extraction
│       │   │   └── ocr_extractor.py     # Tesseract OCR for scanned images
│       │   ├── transformers/
│       │   │   ├── text_cleaner.py      # Whitespace, pipes, umlaut normalisation
│       │   │   ├── language_detector.py # langdetect → "en" / "de"
│       │   │   ├── content_type_detector.py  # qa / legal / narrative classifier
│       │   │   └── document_chunker.py  # Three chunking strategies
│       │   └── loaders/
│       │       ├── base.py              # BaseLoader interface
│       │       ├── chroma_loader.py     # ChromaDB (demo) ↔ AzureSearchLoader swap
│       │       └── azure_search_loader.py  # Azure AI Search (production)
│       │
│       ├── rag/
│       │   ├── embeddings.py        # EmbeddingService (bge-m3 demo / Azure prod)
│       │   ├── retriever.py         # ContractRetriever — cosine similarity, threshold 0.40
│       │   ├── agent.py             # LangGraph agent — 4-node graph
│       │   ├── llm_client.py        # Shared AsyncOpenAI / AsyncAzureOpenAI factory
│       │   ├── document_analyzer.py # MODE 1 & 2 analysis functions
│       │   └── document_grouper.py  # Groups chunks by source_file for MODE 3
│       │
│       └── storage/
│           ├── local_storage.py     # Saves files to ./uploads/ (demo)
│           └── azure_blob_storage.py # Azure Blob Storage (production)
│
├── frontend/
│   ├── package.json             # React 18 + TypeScript + Vite + TailwindCSS
│   ├── vite.config.ts           # Vite dev server proxies /api → localhost:8000
│   └── src/
│       ├── App.tsx              # Root component — three-mode layout
│       ├── types/index.ts       # TypeScript interfaces (AnalysisMode, ComplianceResult)
│       ├── services/
│       │   ├── api.ts           # REST calls (ingest, compliance check, files)
│       │   └── streaming.ts     # SSE helpers — streamQuery, streamAnalyze
│       ├── hooks/
│       │   └── useDocumentAnalysis.ts  # File state + streaming + compliance state
│       └── components/
│           ├── Analysis/
│           │   ├── ModeSelector.tsx      # Three-tab mode switcher
│           │   ├── TemporaryUpload.tsx   # Drop zone with "not stored" label
│           │   ├── CompliancePanel.tsx   # Compliance result display
│           │   └── ExampleQueries.tsx    # Mode-specific query chips
│           ├── QueryInput.tsx            # Question input + submit
│           ├── StreamingResponse.tsx     # Token-by-token display
│           ├── SuggestedQueries.tsx      # Suggested query chips (MODE 3)
│           ├── FileUpload.tsx            # Persistent KB upload dropzone
│           └── IngestedFileList.tsx      # List of files in the knowledge base
│
└── docs/
    ├── decisions.md             # Architecture Decision Records (ADR-001 to ADR-007)
    ├── implementation-status.md # What's built, what's remaining
    ├── env-reference.md         # Annotated .env template
    ├── azure-services.md        # Six Azure services needed for production
    ├── data-flow.md             # Visual data flow diagram
    └── setup.md                 # Mirror of SETUP.md
```

---

## 5. Tech Stack — Every Tool and WHY

### Backend

| Tool | Version | What it does | Why chosen | Azure Production Swap |
|---|---|---|---|---|
| **FastAPI** | 0.111 | HTTP API framework | Async-native; built-in OpenAPI docs; `StreamingResponse` for SSE with one line | Azure API Management in front |
| **LangGraph** | 1.1.3 | AI agent orchestration | State-machine graph; each node (router → retriever → reasoner → formatter) is independently testable and replaceable | Same — works with Azure OpenAI |
| **LangChain** | 1.2.13 | Text splitting utilities | `RecursiveCharacterTextSplitter` handles legal text better than simple split | Same |
| **OpenAI GPT-4o** | openai 2.30 | LLM answer generation | Best legal reasoning; same SDK for Azure OpenAI swap | Azure OpenAI `gpt-4o` deployment |
| **BAAI/bge-m3** | via sentence-transformers | Local embedding model | Free; offline; 1024-dim; multilingual (English + German); no API calls during ingest | Azure OpenAI `text-embedding-3-large` (3072-dim) |
| **ChromaDB** | 1.5.5 | Vector store | Zero-config; runs in-process; persists to disk; good enough for demo | Azure AI Search (hybrid vector + keyword) |
| **PyMuPDF** | 1.27 | PDF text extraction | Fastest Python PDF lib; handles mixed-language PDFs; per-page extraction | Azure Document Intelligence |
| **pytesseract** | 0.3.13 | OCR for scanned images | Industry standard; handles German text; wraps Tesseract 5 | Azure Document Intelligence |
| **langdetect** | 1.0.9 | Language detection | Lightweight; identifies German vs English; used to tag every chunk | Azure Cognitive Services Comprehend |
| **Pydantic** | 2.12 | Request/response validation | Type-safe config + models; `pydantic-settings` reads .env automatically | Same |
| **httpx** | async HTTP client | External compliance API calls | Async; timeout control; used for fire-and-forget compliance archival | Same |

### Frontend

| Tool | What it does | Why chosen |
|---|---|---|
| **React 18** | UI framework | Industry standard; hooks-based; concurrent rendering for SSE |
| **TypeScript** | Type safety | Catches API shape mismatches at compile time |
| **Vite** | Build tool + dev server | 10x faster than Webpack; native ESM; proxy config for API |
| **TailwindCSS** | Styling | Utility-first; no CSS files; consistent design tokens |
| **Lucide React** | Icons | Lightweight; consistent style; tree-shakeable |

### Why these specific choices matter for Riverty

1. **Azure-first architecture**: Every demo component has a documented Azure production swap. Riverty is a Microsoft shop — this alignment was a design constraint from day one.
2. **Offline embeddings**: `BAAI/bge-m3` runs locally so contract text never leaves the machine during the demo. In production, Azure OpenAI keeps data within the Azure tenant.
3. **German + English**: `bge-m3` is multilingual; `langdetect` tags every chunk; Tesseract is installed with German language data. Riverty operates in Germany.
4. **Source citations**: RAG (not fine-tuning) means every answer is traced to a specific document, page, and chunk — a legal requirement.

---

## 6. Data Flow — Step by Step

### Ingestion Flow (upload a contract to the persistent knowledge base)

```
User uploads contract.pdf via browser
         │
         ▼
POST /api/ingest (FastAPI)
         │
         ├─ 1. Save raw file to ./uploads/ (LocalStorage)
         │
         ├─ 2. IngestionRegistry.check(file)
         │      ├─ Compute MD5 checksum of file bytes
         │      ├─ If checksum already in registry.json → return status="skipped"
         │      └─ If new → register checksum + model name + timestamp
         │
         ├─ 3. ETL Pipeline.ingest(file_path)
         │      │
         │      ├─ EXTRACT: PDFExtractor → list of {page_number, text} dicts
         │      │           (OCRExtractor for .jpg/.png)
         │      │
         │      ├─ TRANSFORM:
         │      │   ├─ TextCleaner → normalize whitespace, pipes, umlauts
         │      │   ├─ LanguageDetector → tag "en" or "de"
         │      │   ├─ ContentTypeDetector → classify as qa / legal / narrative
         │      │   └─ DocumentChunker → split using appropriate strategy:
         │      │       ├─ qa: split at Q: markers → one chunk per Q+A pair
         │      │       ├─ legal: split at §, Article, Clause headers
         │      │       └─ narrative: RecursiveCharacterTextSplitter (1500 chars, 200 overlap)
         │      │
         │      └─ LOAD:
         │          ├─ EmbeddingService.get_embeddings_batch(all chunk texts)
         │          │   → BAAI/bge-m3 produces 1024-dim vector per chunk
         │          └─ ChromaLoader.load(chunks + embeddings)
         │              → Upsert into ChromaDB with 14 metadata fields
         │
         ├─ 4. compliance_storage.store_contract_in_api() [fire-and-forget]
         │      → POST file bytes to COMPLIANCE_API_URL (if configured)
         │      → Any error is caught and logged; never blocks ingestion
         │
         └─ Return {"status": "indexed", "chunks_created": N, "language": "en"}
```

### Query Flow (user asks a question — MODE 3 cross-DB search)

```
User types: "Which contracts are missing a GDPR clause?"
         │
         ▼
POST /api/query {"question": "..."}
         │
         ▼
LangGraph Agent — 4-node graph:
         │
         ├─ Node 1: query_router
         │   └─ Classifies query into:
         │       find_clause / compare_contracts / summarise / general_question / find_missing
         │       (LLM call — fast, system prompt only)
         │
         ├─ Node 2: retriever
         │   └─ EmbeddingService.get_embedding(question) → 1024-dim vector
         │   └─ ContractRetriever.retrieve(vector, top_k=8)
         │       → ChromaDB cosine similarity search
         │       → Filter out results below 0.40 threshold
         │       → Return top chunks with metadata
         │
         ├─ Node 3: reasoner
         │   ├─ If query_type == "find_missing":
         │   │   └─ document_grouper.group_by_document(chunks)
         │   │       → Group chunks by source_file
         │   │       → Build per-document context sections
         │   │       → System prompt asks LLM to state verdict per document
         │   └─ Else:
         │       └─ Build flat context string from chunks
         │       └─ System prompt: "Answer only from the provided contract excerpts"
         │   └─ GPT-4o streaming → yields tokens
         │
         └─ Node 4: formatter
             └─ Appends source citations: "● contract.pdf — page 3, chunk 2/5 (0.87)"
             └─ Streams final tokens with citations
         │
         ▼
SSE stream: data: token\n\n ... data: [DONE]\n\n
         │
         ▼
React frontend reads SSE, appends tokens to UI in real time
```

### Temporary Document Analysis Flow (MODE 1 / MODE 2)

```
User uploads temp_contract.pdf + types question
(file is NOT added to knowledge base)
         │
         ▼
POST /api/analyze {file, question, mode: "single"|"compare"}
         │
         ├─ Extract text to tempfile.NamedTemporaryFile
         ├─ PDFExtractor.extract(tmp_path) → pages
         ├─ os.unlink(tmp_path)  ← deleted immediately after extraction
         │
         ├─ If mode == "single":
         │   └─ document_analyzer.analyze_single_document(text, question)
         │       → GPT-4o with just the uploaded document as context
         │       → No ChromaDB query
         │
         └─ If mode == "compare":
             └─ document_analyzer.compare_with_database(text, question)
                 → Use first 500 chars as semantic query
                 → ContractRetriever.retrieve() → get similar stored contracts
                 → GPT-4o sees: uploaded doc + retrieved similar contracts
                 → Compares and contrasts
         │
         ▼
SSE stream of answer tokens
```

---

## 7. Three Analysis Modes

| Mode | Name | Data Source | Backend Route | When to use |
|---|---|---|---|---|
| **MODE 1** | Analyze Document | Uploaded file only — never stored | `POST /api/analyze` (mode=single) | "Review this new contract before signing" |
| **MODE 2** | Compare with DB | Uploaded file + ChromaDB | `POST /api/analyze` (mode=compare) | "How does this draft compare to our existing contracts?" |
| **MODE 3** | Search Contracts | ChromaDB only | `POST /api/query` | "Which of our stored contracts are missing GDPR clauses?" |

### MODE 1 — Single Document Analysis
- User uploads a PDF
- Text extracted to temp file, **immediately deleted** after extraction
- File content is never written to ChromaDB
- GPT-4o answers using only the uploaded document as context
- Also supports **compliance check** (`POST /api/compliance`) → returns structured JSON:
  ```json
  { "compliant": false, "violations": ["No GDPR clause found", "Unlimited liability"], "explanation": "..." }
  ```

### MODE 2 — Compare with Database
- User uploads a PDF (also never stored)
- System embeds the first 500 chars as a semantic query
- Retrieves the most similar stored contracts from ChromaDB
- GPT-4o sees both the uploaded document AND the retrieved contracts
- Produces a comparison: "Your new contract differs from existing ones in these ways..."

### MODE 3 — Cross-DB Query
- No file upload needed
- User asks a question about the stored contract portfolio
- LangGraph's `query_router` classifies the query
- If `find_missing`: uses `document_grouper` to build per-document context → LLM gives per-document verdicts
- If `find_clause` / `compare_contracts` etc.: flat retrieval → standard grounded answer

---

## 8. Demo vs Production — The Swap Pattern

Every file that uses a demo tool has this comment block:

```python
# ============================================================
# DEMO MODE: ChromaDB — zero-config vector store for laptop demo
# PRODUCTION SWAP → Azure AI Search (AWS: OpenSearch):
#   Replace ChromaLoader() with AzureSearchLoader() in pipeline.py
#   Azure AI Search adds hybrid search, RBAC, and enterprise scale
# ============================================================
```

### The Six Swaps

| Layer | Demo | Production | Where to change |
|---|---|---|---|
| Vector store | ChromaDB local disk | Azure AI Search | `etl/loaders/chroma_loader.py` → `AzureSearchLoader` |
| LLM | OpenAI `api.openai.com` | Azure OpenAI endpoint | `rag/llm_client.py` → `AsyncAzureOpenAI` |
| Embeddings | BAAI/bge-m3 local | Azure OpenAI `text-embedding-3-large` | `rag/embeddings.py` |
| File storage | Local `./uploads/` | Azure Blob Storage | `storage/local_storage.py` → `AzureBlobStorage` |
| PDF extraction | PyMuPDF + Tesseract | Azure Document Intelligence | `etl/extractors/` |
| Auth / identity | API key in `.env` | Azure Managed Identity | All Azure SDK clients |

### Why the swap is minimal

All swappable components are hidden behind abstract base classes (`BaseLoader`, `BaseExtractor`).
The calling code (`pipeline.py`, `agent.py`) never imports the concrete class directly.
The `APP_ENV` environment variable triggers the right branch:

```python
# config.py
APP_ENV=development  # → demo stack
APP_ENV=production   # → Azure stack
```

---

## 9. ETL Pipeline Deep Dive

### Extractors (Strategy Pattern)

```
BaseExtractor (abstract)
    └── PDFExtractor   — PyMuPDF: page-by-page text, handles mixed EN/DE
    └── OCRExtractor   — pytesseract: converts rasterized PDFs and images
```

The pipeline selects the extractor based on file extension:
- `.pdf` → `PDFExtractor` (if text is extractable)
- `.jpg`, `.jpeg`, `.png` → `OCRExtractor`
- Scanned PDFs → `OCRExtractor` (detected by empty text extraction)

### Chunking Strategies

Three content types → three chunking strategies:

**QA documents** (FAQ contracts, questionnaires):
- Split at `Q:` markers
- One chunk = one question + answer pair
- Preserves semantic unity of each Q&A

**Legal documents** (contracts, agreements):
- Split at `§`, `Article N`, `Clause N`, `SECTION N` headers
- One chunk = one legal clause/article
- Preserves the atomic unit of legal meaning

**Narrative documents** (everything else):
- `RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)`
- Tries `\n\n` → `\n` → `.` before hard character split
- 200-char overlap prevents sentences being cut at boundaries

### Chunk Metadata (14 fields)

Every stored chunk carries:

```python
{
    "source_file": "contract_2024.pdf",
    "page_number": 3,
    "chunk_index": 2,
    "total_chunks": 8,
    "language": "en",           # or "de"
    "content_type": "legal",    # qa / legal / narrative
    "checksum": "a3f2...",      # MD5 of original file
    "file_size_kb": 142,
    "extraction_method": "pdf", # or "ocr"
    "is_scanned": False,
    "embedding_model": "BAAI/bge-m3",
    "upload_timestamp": "2026-03-30T14:22:00Z",
    "text_preview": "The termination notice period...",
    "chunking_strategy": "legal"
}
```

### Deduplication Registry

`ingestion_registry.json` tracks every ingested file:
- **MD5 checksum** — same file → `status="skipped"`, no re-embedding
- **Embedding model name** — if model changed → `409 Conflict` (different dims, cannot mix)

---

## 10. RAG Layer Deep Dive

### EmbeddingService

```python
# Demo: local, free, offline, 1024-dim, multilingual
model = SentenceTransformer("BAAI/bge-m3")

# Production swap: Azure OpenAI, 3072-dim, within Azure tenant
client = AzureOpenAI(...)
client.embeddings.create(model="text-embedding-3-large", input=texts)
```

Supports:
- `get_embedding(text)` → single 1024-dim vector
- `get_embeddings_batch(texts)` → efficient bulk embedding for ingestion

### ContractRetriever

```python
results = collection.query(
    query_embeddings=[query_vector],
    n_results=top_k,
    include=["documents", "metadatas", "distances"]
)
# Filter: keep only results with similarity_score >= 0.40
```

The 0.40 threshold was calibrated for `BAAI/bge-m3` normalized vectors.
For Azure `text-embedding-3-large`, lower to ~0.30 (OpenAI models produce lower raw cosine scores).

### LangGraph Agent — 4-Node Graph

```
State: {question, query_type, retrieved_chunks, answer}

query_router → retriever → reasoner → formatter
     │              │           │           │
  classifies    ChromaDB    GPT-4o     add source
  query type    cosine      streaming  citations
               similarity   answer
```

**Node 1 — query_router:**
Classifies the question into one of: `find_clause`, `compare_contracts`, `summarise`, `general_question`, `find_missing`. This changes how the context is built in the reasoner.

**Node 2 — retriever:**
Embeds the question, queries ChromaDB, filters by threshold, returns top-K chunks.

**Node 3 — reasoner:**
- If `find_missing`: groups chunks by document, builds per-document context, uses a system prompt that asks GPT-4o to state per-document verdicts
- Otherwise: builds flat context string, uses standard grounded-answer system prompt

**Node 4 — formatter:**
Appends clean source citations with relevance dots:
- `●` = 0.65–1.0 (strongly relevant)
- `◐` = 0.40–0.65 (relevant)
- `○` = below threshold (filtered before reaching formatter)

### Streaming

All three modes use SSE:
```
POST /api/query or /api/analyze
→ StreamingResponse(media_type="text/event-stream")
→ Each token: "data: token\n\n"
→ End: "data: [DONE]\n\n"
```

React reads with `fetch()` + `response.body.getReader()` (not `EventSource` — allows POST with body).

---

## 11. API Routes Reference

| Method | Path | Auth | Request | Response | Mode |
|---|---|---|---|---|---|
| `GET` | `/health` | None | — | `{status, mode, document_count, version}` | — |
| `POST` | `/api/ingest` | None | `multipart: file` | `{status, chunks_created, language, ...}` | — |
| `POST` | `/api/ingest-all` | None | — | `{results: [...]}` | — |
| `POST` | `/api/query` | None | `{"question": str}` | SSE stream | MODE 3 |
| `POST` | `/api/analyze` | None | `multipart: file, question, mode` | SSE stream | MODE 1/2 |
| `POST` | `/api/compliance` | None | `multipart: file, guidelines?` | `ComplianceResult` JSON | MODE 1 |
| `GET` | `/api/files/{filename}` | None | — | PDF bytes | — |
| `GET` | `/api/suggested-questions` | None | — | `[{id, text, category}]` | — |
| `GET` | `/docs` | None | — | Swagger UI | — |

### ComplianceResult model

```python
class ComplianceResult(BaseModel):
    compliant: bool
    violations: list[str]   # empty if compliant
    explanation: str        # human-readable assessment
```

Default compliance guidelines checked:
- GDPR / data protection clause
- Termination rights and notice period
- Governing law and jurisdiction
- Liability cap and limitation clauses
- Clear party identification

---

## 12. Frontend Architecture

### Three-Mode Layout

```
┌─────────────────────────────────────────────────────┐
│  Left Sidebar          │  Right Panel                │
│                        │                             │
│  Knowledge Base        │  [Search] [Analyze] [Compare] ← ModeSelector
│  ─────────────         │                             │
│  FileUpload            │  MODE 3 (Search):           │
│  (persistent,          │    SuggestedQueries         │
│   stored in DB)        │    QueryInput               │
│                        │    StreamingResponse        │
│  IngestedFileList      │                             │
│                        │  MODE 1 (Analyze):          │
│                        │    TemporaryUpload          │
│                        │    ExampleQueries           │
│                        │    QueryInput               │
│                        │    [Check Compliance] btn   │
│                        │    CompliancePanel          │
│                        │    StreamingResponse        │
│                        │                             │
│                        │  MODE 2 (Compare):          │
│                        │    TemporaryUpload          │
│                        │    ExampleQueries           │
│                        │    QueryInput               │
│                        │    StreamingResponse        │
└────────────────────────┴─────────────────────────────┘
```

### Key Design Decisions

**Temporary uploads never reach ChromaDB** — enforced at the route level, not the UI.
The `TemporaryUpload` component shows a blue "Temporary" badge and the text "not stored in knowledge base" to make this explicit to the user.

**useDocumentAnalysis hook** manages:
- `analysisFile: File | null` — the currently selected temp file
- Streaming state: `isStreaming`, `content`, `isDone`, `streamError`
- Compliance state: `complianceResult`, `isCheckingCompliance`, `complianceError`

**Mode switching** clears all response state — prevents stale SSE content from one mode appearing in another.

**SSE reading** uses a shared `readSseStream()` helper in `streaming.ts`:
```typescript
async function* readSseStream(response: Response): AsyncGenerator<string> {
    // reads response.body.getReader(), parses "data: " lines, stops at "[DONE]"
}
```

---

## 13. How to Run the Project

### First-time Setup (5 minutes)

```bash
# 1. Clone
git clone <repo-url>
cd riverty-contract-review

# 2. Backend setup
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env — set OPENAI_API_KEY=sk-...

# 4. (Optional) Pre-download embedding model
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
```

### Start the Backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs  (Swagger UI)
# → http://localhost:8000/health
```

### Start the Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### Add Contracts to the Knowledge Base

```bash
# Option A: via UI — drag PDF to left sidebar dropzone
# Option B: via API
curl -X POST http://localhost:8000/api/ingest -F "file=@contract.pdf"

# Option C: batch ingest all files in uploads/
bash backend/run_pipeline.sh --ingest-only
```

### Run All Tests

```bash
cd backend
source .venv/bin/activate
bash run_tests.sh
# → 93 tests, 0 failed
```

### Run Manual E2E Tests

```bash
# Start backend first, then:
python backend/tests/test-rag-manual.py
# Tests all three modes, measures latency, saves results to rag_test_results.json
```

### Demo Walkthrough (for the presentation)

```bash
# Terminal 1 — Backend
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && npm run dev

# Browser
open http://localhost:5173

# Then:
# 1. Upload 2-3 contracts via left sidebar (they get stored in ChromaDB)
# 2. Switch to "Search Contracts" tab → ask "Which contracts are GDPR compliant?"
# 3. Switch to "Analyze Document" tab → upload a new PDF → run compliance check
# 4. Switch to "Compare Document" tab → same PDF → ask "How does this differ from stored contracts?"
```

### Health Check & Verification

```bash
curl http://localhost:8000/health
# {"status":"ok","mode":"development","document_count":42,"version":"1.0.0"}
```

---

## 14. 15-Minute Presentation Script & Slide Plan

### Slide 1 — Title (30 sec)
**Title:** Riverty Contract Review — AI-Powered Legal Analysis System
**Subtitle:** RAG-based contract intelligence | Python + React | Azure-ready

*Say:* "I built a system that lets Riverty's legal team upload contracts, ask questions about them in plain English, compare them against each other, and get a structured compliance check — all in under 5 seconds per query."

---

### Slide 2 — The Problem (1 min)
**Three pain points:**
- Manual review: hours per contract
- No cross-document search: can't ask "which contracts have unlimited liability?"
- Inconsistency: different reviewers miss different clauses

*Show a simple before/after table. Keep it to 3 bullets.*

---

### Slide 3 — Live Demo (4 min) ← MOST IMPORTANT
Show the running app:
1. Upload a contract → left sidebar → "indexed: 12 chunks" (30 sec)
2. MODE 3: type "Which contracts are missing a GDPR clause?" → watch streaming response (1 min)
3. MODE 1: upload a new PDF → click "Check Compliance" → show structured result (1 min)
4. MODE 2: same PDF → "Compare this with our existing contracts" → streaming comparison (1 min)
5. Show Swagger docs at `/docs` (30 sec)

*This is the centrepiece. Practice it until it takes exactly 4 minutes.*

---

### Slide 4 — Architecture (2 min)
Show the architecture diagram from Section 3.

*Walk through left to right:*
"The user interacts with a React frontend. Requests hit a FastAPI backend. For ingested documents, the ETL pipeline extracts text, chunks it, embeds it with a local model, and stores in ChromaDB. For queries, the LangGraph agent routes the question, retrieves relevant chunks, and streams the GPT-4o answer back via Server-Sent Events."

---

### Slide 5 — Tech Stack & Why (2 min)
**Table with 3 columns: Tool | Demo | Production**

| Layer | Demo | Production (Azure) |
|---|---|---|
| Vector Store | ChromaDB (local) | Azure AI Search |
| LLM | OpenAI GPT-4o | Azure OpenAI (same model) |
| Embeddings | BAAI/bge-m3 (local, free) | Azure text-embedding-3-large |
| File Storage | Local disk | Azure Blob Storage |
| PDF/OCR | PyMuPDF + Tesseract | Azure Document Intelligence |
| Auth | API key | Azure Managed Identity |

*Say:* "Every demo component has a documented production swap. The `APP_ENV` environment variable switches the entire stack. No business logic changes."

---

### Slide 6 — Three Analysis Modes (1.5 min)
**Three boxes:**
- MODE 1: Analyze a single document (never stored, temp file deleted after extraction)
- MODE 2: Compare uploaded doc vs knowledge base
- MODE 3: Query across all stored contracts (LangGraph agent with document grouping for "find missing" queries)

*Say:* "The critical design decision here is that temporary uploaded documents for analysis NEVER touch ChromaDB. This is enforced at the route level, not the UI."

---

### Slide 7 — Data Flow (1 min)
Show a simplified version of the ingestion and query flows from Section 6.

*Say:* "Ingestion: PDF → extract → clean → chunk → embed locally → store in ChromaDB. Query: question → embed → cosine similarity search → top-8 chunks → GPT-4o → stream back via SSE."

---

### Slide 8 — Code Quality (1 min)
- 93 tests, 0 failed (pytest with mocked external services — runs fully offline)
- Strategy Pattern: all swappable components behind abstract base classes
- No hardcoded values: everything in config.py from .env
- Architecture Decision Records: 7 ADRs documenting every major choice
- CLAUDE.md: coding conventions enforced across all contributions

---

### Slide 9 — What's Next (45 sec)
- Re-index ChromaDB with 1500-char chunks (currently 1000 in some docs)
- Add `GET /api/files` endpoint → sidebar survives page refresh
- Azure Active Directory RBAC for multi-team access
- Azure Document Intelligence for higher-accuracy OCR on complex contracts

---

### Slide 10 — Q&A
Leave 2 minutes for questions. Expected questions are in the next section.

---

## 15. Interview Q&A — Every Question They Could Ask

### Architecture & Design

**Q: Why RAG instead of fine-tuning an LLM on contract data?**

A: Three reasons. First, contracts change frequently — a new contract is queryable seconds after upload; fine-tuning requires a full retraining cycle for each update. Second, legal requirement: every answer must cite the source clause — RAG gives this automatically through chunk metadata; fine-tuning cannot. Third, GDPR: storing contract content in model weights is hard to audit and impossible to delete (right to erasure requires deletion from the vector store entry, not retraining the model).

---

**Q: Why LangGraph instead of a simple LLM call?**

A: LangGraph gives us a typed state machine. Each of the four nodes (router, retriever, reasoner, formatter) is independently testable, replaceable, and observable. The query router node means we can handle different query types differently — "find missing clauses" uses document-grouped context; "find a specific clause" uses flat retrieval. With a single LLM call you'd have to put all that logic into one massive prompt. LangGraph also enables conditional branching and future additions (e.g., a reranker node, a hallucination check node) without refactoring the whole pipeline.

---

**Q: Why Server-Sent Events instead of WebSocket?**

A: SSE is strictly server-to-client, which perfectly matches our use case — the client sends one question and only needs to receive a streamed answer. SSE works through all HTTP proxies and corporate firewalls as plain HTTP with no protocol upgrade. WebSocket adds bidirectional complexity (ping/pong, reconnect logic) with zero benefit here. FastAPI's `StreamingResponse` supports SSE natively. For Riverty's production environment behind Azure API Management, the `X-Accel-Buffering: no` header we set handles proxy buffering.

---

**Q: Why ChromaDB for demo and Azure AI Search for production?**

A: ChromaDB requires zero configuration — no cloud account, no API keys beyond OpenAI, no separate service to start. It runs in-process with Python and persists to local disk. A reviewer can clone the repo, set one API key, and have the full system running in 5 minutes. Azure AI Search adds what ChromaDB lacks in production: hybrid vector + keyword search (better recall on short legal terms), enterprise RBAC, horizontal scaling across pods, and SOC 2 / ISO 27001 compliance. The swap is one line: `ChromaLoader()` → `AzureSearchLoader()`.

---

**Q: Why BAAI/bge-m3 instead of OpenAI text-embedding-3-large for the demo?**

A: Three reasons. First, cost: bge-m3 is free — no API calls during ingestion, which is the most expensive phase. For a demo with many documents this matters. Second, privacy: contract text never leaves the machine during embedding — only GPT-4o queries hit an external API. Third, multilingual: bge-m3 handles German and English in one model without switching. In production we switch to Azure `text-embedding-3-large` because Azure OpenAI keeps data within the Microsoft tenant, which is required for Riverty's real contracts.

---

**Q: How does the system prevent hallucination?**

A: The reasoner node's system prompt explicitly instructs GPT-4o: "Answer only from the provided contract excerpts. If the information is not in the excerpts, say so." The formatter node appends source citations with relevance scores — users can verify every claim against the original document. The similarity threshold (0.40) filters out low-relevance chunks before they reach GPT-4o, so the model sees only genuinely relevant context. We do not prevent all hallucination (no system does) but we make it auditable.

---

**Q: How does the deduplication registry work?**

A: When a file is uploaded, we compute its MD5 checksum. If that checksum is already in `ingestion_registry.json`, we return `status="skipped"` without re-processing. We also store the embedding model name — if someone tries to ingest the same corpus with a different model (different vector dimensions), we return `409 Conflict` rather than mixing incompatible vectors in the same ChromaDB collection.

---

**Q: Why do you delete the temp file immediately after extraction?**

A: Data minimisation. The temporary file is only needed for the duration of text extraction — after that, we have the text in memory and the file has no purpose. Keeping it would mean sensitive contract text sits on disk for the duration of the API request. The `finally` block in the route handler guarantees deletion even if extraction raises an exception.

---

**Q: How does the compliance check work technically?**

A: The `/api/compliance` route accepts the file and optional custom guidelines. We extract the text (temp file, immediately deleted), then call GPT-4o with a structured prompt that asks for the assessment in a fixed three-section format: COMPLIANT (yes/no), VIOLATIONS (one per line), EXPLANATION. The `_parse_compliance_response()` function uses a line-by-line state machine to extract these three sections into the `ComplianceResult` Pydantic model. The result is returned as structured JSON (not a stream).

---

**Q: How do you handle scanned PDFs?**

A: `PDFExtractor` attempts text extraction with PyMuPDF first. If the extracted text is empty or below a minimum length threshold, it falls back to `OCRExtractor` which runs Tesseract 5 with both English and German language models. The chunk metadata records `is_scanned: True` and `extraction_method: "ocr"` so you can filter by extraction method in queries or debugging.

---

**Q: Why do you use `APP_ENV` instead of separate .env files?**

A: Single source of truth. All environment variables live in one `.env` file. `APP_ENV=development` activates the demo stack; `APP_ENV=production` activates Azure. In deployment, you set `APP_ENV=production` in the container environment and add the Azure credentials — no file swapping or branch switching required. The `config.py` Pydantic Settings class reads all vars in one place and exposes them as typed attributes throughout the codebase.

---

### Frontend

**Q: Why React with TypeScript instead of a simpler approach?**

A: The UI has three distinct modes with independent state management (file state, streaming state, compliance state per mode). TypeScript's discriminated union type (`AnalysisMode = 'search' | 'analyze' | 'compare'`) makes it impossible to pass the wrong mode to the backend. The `useDocumentAnalysis` hook encapsulates all temporary document state, which would be easy to accidentally share or leak between modes without a typed hook boundary.

---

**Q: Why Vite instead of Create React App or Next.js?**

A: Vite builds in under 500ms versus 5–10 seconds for Webpack. The dev server proxy config (`/api → localhost:8000`) eliminates CORS issues during development. Next.js would add server-side rendering complexity we don't need — this is a single-page app accessed within Riverty's internal network, not a public web app that needs SEO.

---

### Production & Scaling

**Q: How would this scale to 10,000 contracts?**

A: The architecture is designed for this. Swap ChromaDB for Azure AI Search — it handles millions of vectors with sub-second query time. Swap the local embedding model for Azure OpenAI embeddings service — batching is already implemented. Add an Azure Service Bus queue between the upload API and the ETL pipeline so ingestion is asynchronous and doesn't block the HTTP response. The LangGraph agent is stateless — run multiple instances behind Azure API Management.

---

**Q: How do you handle GDPR data subject requests (right to erasure)?**

A: Each chunk's metadata includes the source filename and MD5 checksum. To delete a contract: remove its chunks from ChromaDB by querying for `source_file == "contract.pdf"`, delete the raw file from Azure Blob Storage, and remove the registry entry. The LLM model weights are never updated — the contract text only ever lived in the vector store and blob storage. This is the key GDPR advantage of RAG over fine-tuning.

---

**Q: What monitoring would you add for production?**

A: Azure Monitor + Application Insights. Track: query latency (p50/p95/p99), retrieval hit rate (what fraction of queries get at least one chunk above threshold), LLM token usage (cost control), ingestion failures (by document type), compliance check throughput. Add distributed tracing across the LangGraph nodes so you can see which node is the bottleneck for a specific query.

---

**Q: How do you prevent unauthorized access to contracts?**

A: In production: Azure Active Directory authentication in front of the API, Azure RBAC on the blob storage container and AI Search index. In demo: no auth (single-user, local). The `/api/files/{filename}` route already blocks path traversal attacks (`..` in filename → 400). Adding AAD auth is a matter of adding the `azure-identity` dependency and wrapping routes with `@require_auth` — the business logic is unchanged.

---

**Q: What would you change if you had more time?**

A: Four things in priority order.
1. Re-ingest the ChromaDB with 1500-char chunks consistently (currently mixed 1000/1500 from different development phases)
2. Add `GET /api/files` listing endpoint so the sidebar persists across page refreshes
3. Add a reranker node in LangGraph (e.g., Azure Cognitive Search semantic reranker) to improve retrieval precision
4. Add streaming for the compliance check endpoint — currently it waits for the full response which can take 3–4 seconds for long contracts

---

*End of document. This single file contains everything you need to understand, explain, demo, and defend this project in a technical interview or 15-minute presentation.*
