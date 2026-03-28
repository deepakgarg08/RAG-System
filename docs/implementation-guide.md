# Implementation Guide — How Everything Actually Works

> **Who is this for?** Anyone running this system for the first time, or anyone who wants
> to understand exactly what happens when you upload a contract and ask a question.
> No prior knowledge of RAG or LangGraph needed.

---

## The Simple Mental Model

Think of this system as a **very smart librarian** who has read every contract you gave them.

1. **You hand over a contract (PDF/JPG)** → the librarian reads it, cuts it into meaningful
   sections, and memorises each section by its "meaning fingerprint" (a 1536-number vector)
2. **You ask a question** → the librarian finds the sections whose meaning most closely
   matches your question, then writes a careful answer using only those sections —
   and tells you exactly which contract and section each piece of information came from
3. **You get a sourced answer** — not a guess, not internet knowledge, only what is in the
   contracts you uploaded

---

## Part 1 — Where to Put Your Contract Files

### Supported File Types

| Extension | How it's processed | Use case |
|---|---|---|
| `.pdf` | PyMuPDF reads text layers; auto-falls back to OCR if scanned | Standard typed contracts |
| `.jpg` / `.jpeg` | Tesseract OCR with grayscale + contrast pre-processing | Scanned/photographed contracts |
| `.png` | Same as JPEG | Screenshots, scanned pages |

> **Not supported:** `.txt`, `.docx`, `.xlsx` — the pipeline will raise a `ValueError`
> if you try to ingest these. The ingest route returns HTTP 400 for unsupported types.

### Where files land after upload

When you call `POST /api/ingest`, the raw file is saved here first:

```
backend/
└── uploads/                 ← controlled by UPLOAD_DIR in .env (default: ./uploads)
    ├── contract_nda_2023.pdf
    ├── service_agreement.pdf
    └── scanned_contract.jpg
```

The `uploads/` directory is created automatically on startup by the `lifespan` function
in [backend/app/main.py](../backend/app/main.py).

### For testing — sample contracts

Pre-written synthetic contracts live here:
```
backend/tests/sample_contracts/
├── contract_nda_techcorp_2023.txt           ← English NDA (has GDPR clause)
├── contract_service_datasystems_2022.txt    ← English service agreement (NO GDPR — intentional)
├── contract_vendor_2023_no_termination.txt  ← English vendor agreement (NO termination clause)
└── vertrag_dienstleistung_mueller_2024.txt  ← German contract (DSGVO Art. 28)
```

These are `.txt` reference files — the pipeline doesn't process `.txt` directly.
To test with them, convert to PDF or use the `sample_pdf_path` fixture in tests.

---

## Part 2 — How to Fire the ETL Pipeline

You have three ways to run the pipeline. All three do exactly the same thing.

### Way 1 — Via the HTTP API (normal usage)

```bash
# Start the server first
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# In another terminal — upload a contract
curl -X POST http://localhost:8000/api/ingest \
  -F "file=@/path/to/contract.pdf"
```

Response:
```json
{
  "filename": "contract.pdf",
  "file_type": ".pdf",
  "language": "en",
  "chunks_created": 4,
  "status": "success",
  "error": null
}
```

### Way 2 — Direct Python script (batch mode, no server needed)

```python
# Run from backend/ with venv activated
# python ingest_batch.py

from app.etl.pipeline import IngestionPipeline
import os

pipeline = IngestionPipeline()

# Ingest a single file
result = pipeline.ingest("uploads/contract.pdf")
print(result)

# Ingest a whole folder
for filename in os.listdir("uploads/"):
    if filename.endswith((".pdf", ".jpg", ".jpeg", ".png")):
        result = pipeline.ingest(f"uploads/{filename}")
        print(f"{result['filename']}: {result['status']} — {result['chunks_created']} chunks")
```

This is useful for bulk-loading an existing contract archive overnight with no HTTP server running.

### Way 3 — Interactive Python (for debugging one file)

```python
# cd backend && source venv/bin/activate && python
from app.etl.pipeline import IngestionPipeline

pipeline = IngestionPipeline()
result = pipeline.ingest("uploads/my_contract.pdf")

# See exactly what happened
print("Status:   ", result["status"])
print("Language: ", result["language"])
print("Chunks:   ", result["chunks_created"])
print("Error:    ", result.get("error"))
```

---

## Part 3 — What the Pipeline Does Step by Step

Here is the exact journey of a file called `contract_nda.pdf` through the system.
Each step names the **function** and the **file** that handles it.

```
You upload contract_nda.pdf
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: HTTP Validation                                        │
│  File:     backend/app/api/routes/ingest.py                     │
│  Function: ingest_document()                                    │
│  Does:     Checks extension is .pdf/.jpg/.jpeg/.png             │
│            Returns HTTP 400 immediately if not                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: Save Raw File                                          │
│  File:     backend/app/storage/local_storage.py                 │
│  Function: LocalStorage.save()                                  │
│  Does:     Writes bytes to ./uploads/contract_nda.pdf           │
│  Result:   File is now at: backend/uploads/contract_nda.pdf     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: Select Extractor                                       │
│  File:     backend/app/etl/pipeline.py                          │
│  Function: IngestionPipeline.ingest()                           │
│  Does:     Looks up ".pdf" in EXTRACTOR_REGISTRY dict           │
│            → selects PDFExtractor                               │
│            (would select OCRExtractor for .jpg/.png)            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: Extract Raw Text                                       │
│  File:     backend/app/etl/extractors/pdf_extractor.py          │
│  Function: PDFExtractor.extract()                               │
│  Does:     PyMuPDF opens each page, reads text layer            │
│            If total chars < 50 → auto-switches to OCR fallback  │
│  Result:   raw_text = "This Non-Disclosure Agreement..."        │
│            (a plain Python string, ~3000 chars)                 │
│                                                                 │
│  For JPG/PNG files:                                             │
│  File:     backend/app/etl/extractors/ocr_extractor.py          │
│  Function: OCRExtractor.extract()                               │
│  Does:     Pillow opens image → grayscale → boost contrast      │
│            Tesseract runs OCR with lang='eng+deu'               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: Clean the Text                                         │
│  File:     backend/app/etl/transformers/cleaner.py              │
│  Function: TextCleaner.clean()  +  TextCleaner.detect_language()│
│  Does:     Removes pipe characters (|), long underscores (____) │
│            Fixes OCR German umlaut mistakes (a¨ → ä)            │
│            Collapses extra whitespace and blank lines           │
│            Detects language → "en" or "de"                      │
│  Result:   clean_text (trimmed string), language = "en"         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 6: Split into Chunks                                      │
│  File:     backend/app/etl/transformers/chunker.py              │
│  Function: DocumentChunker.chunk()                              │
│  Does:     LangChain RecursiveCharacterTextSplitter              │
│            chunk_size=1000 chars, overlap=200 chars             │
│            Tries to split at \n\n, then \n, then ". ", then " " │
│            Attaches metadata to every chunk:                    │
│              {                                                  │
│                "source_file": "contract_nda.pdf",              │
│                "chunk_index": 0,                               │
│                "total_chunks": 4,                              │
│                "language": "en",                               │
│                "file_type": ".pdf",                            │
│                "char_count": 982                               │
│              }                                                  │
│  Result:   list of 4 dicts, each with "text" + "metadata"       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 7: Embed + Store                                          │
│  File:     backend/app/etl/loaders/chroma_loader.py             │
│  Function: ChromaLoader.load()                                  │
│  Also:     backend/app/rag/embeddings.py → get_embedding()      │
│  Does:     For each chunk:                                      │
│            1. Calls OpenAI text-embedding-3-small API           │
│               chunk text → 1536-dimensional float vector        │
│            2. Calls ChromaDB collection.upsert() with:          │
│               - id:        "contract_nda.pdf_chunk_0"           │
│               - embedding: [0.023, -0.011, ...]  (1536 floats)  │
│               - document:  "This Non-Disclosure..."  (text)     │
│               - metadata:  {source_file, chunk_index, ...}      │
│  Result:   4 vectors stored in ChromaDB                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
        Pipeline returns result dict to the HTTP route
        Route wraps it in IngestResponse and returns JSON
```

---

## Part 4 — Where Is the Transformed Data Stored?

After ingestion you will find data in two places:

### 1. Raw files → `backend/uploads/`

```
backend/uploads/
├── contract_nda.pdf          ← original binary, exactly as uploaded
└── scanned_contract.jpg      ← original binary, exactly as uploaded
```

These are never modified. They exist for audit/download purposes.

### 2. Vectors + text → `backend/chroma_db/`

```
backend/chroma_db/             ← controlled by CHROMA_PERSIST_PATH in .env
└── (ChromaDB internal files)
```

ChromaDB stores everything in this directory (SQLite + binary index files).
You don't read these directly — you query them via Python. To inspect what's stored:

```python
# cd backend && source venv/bin/activate && python
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("riverty_contracts")

# How many chunks are stored?
print("Total chunks:", collection.count())

# Peek at the first 5 stored documents
results = collection.peek(5)
for i in range(len(results["ids"])):
    print("─" * 60)
    print("ID:      ", results["ids"][i])
    print("Source:  ", results["metadatas"][i]["source_file"])
    print("Chunk:   ", results["metadatas"][i]["chunk_index"])
    print("Language:", results["metadatas"][i]["language"])
    print("Preview: ", results["documents"][i][:120], "...")
```

Example output:
```
Total chunks: 12
────────────────────────────────────────────────────────────
ID:       contract_nda.pdf_chunk_0
Source:   contract_nda.pdf
Chunk:    0
Language: en
Preview:  This Non-Disclosure Agreement is entered into between TechCorp GmbH and...
```

---

## Part 5 — Source Attribution in Retrieved Results

**Yes — every answer is fully sourced.** This is a core design requirement.

### How source data travels through the system

At ingestion, every chunk gets `source_file` in its metadata. That metadata is stored
in ChromaDB alongside the vector. At query time it comes back with every result.

Here is the full chain:

```
Ingestion:
  chunk["metadata"]["source_file"] = "contract_nda.pdf"
  chunk["metadata"]["chunk_index"] = 2
           ↓ stored in ChromaDB upsert
           ↓
Query time:
  ContractRetriever.retrieve() returns:
  [
    {
      "text":             "Section 7: All personal data shall be...",
      "source_file":      "contract_nda.pdf",     ← WHERE it came from
      "chunk_index":      2,                       ← which section
      "language":         "en",
      "similarity_score": 0.87                     ← how relevant (0-1)
    },
    ...
  ]
           ↓ passed to reasoner node as context
           ↓
Agent formatter appends:
  "**Sources:** contract_nda.pdf, service_agreement.pdf"
```

### Inspect retrieved sources directly

```python
# cd backend && source venv/bin/activate && python
from app.rag.retriever import ContractRetriever

retriever = ContractRetriever()
results = retriever.retrieve("Does this contract have a GDPR clause?", top_k=5)

for r in results:
    print(f"Score: {r['similarity_score']:.2f} | File: {r['source_file']} "
          f"| Chunk: {r['chunk_index']} | Lang: {r['language']}")
    print(f"  → {r['text'][:100]}...")
    print()
```

Example output:
```
Score: 0.87 | File: contract_nda.pdf | Chunk: 2 | Lang: en
  → Section 7: All personal data processed under this agreement shall comply with GDPR...

Score: 0.71 | File: service_datasystems.pdf | Chunk: 1 | Lang: en
  → 4. Data handling: The service provider acknowledges its obligations regarding...

Score: 0.34 | File: mueller_vertrag.pdf | Chunk: 0 | Lang: de
  → DSGVO Artikel 28: Der Auftragsverarbeiter verarbeitet personenbezogene Daten...
```

The similarity score goes from 0.0 (unrelated) to 1.0 (identical). Chunks below 0.30
are filtered out automatically in `retriever.py` (`_MIN_SIMILARITY = 0.3`).

---

## Part 6 — The Query Path (After Ingestion)

Once contracts are ingested, this is what happens when you ask a question:

```
POST /api/query  {"question": "Which contracts are missing a GDPR clause?"}
         │
         ▼
┌───────────────────────────────────────────────────────────┐
│  query.py → stream_query(question)                        │
│  Opens SSE stream immediately                             │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────┐
│  LangGraph Node 1: query_router                           │
│  File: backend/app/rag/agent.py → query_router()          │
│  Does: Sends question to GPT-4o with a classification     │
│        prompt, gets back one of:                          │
│        "find_clause" / "find_missing" /                   │
│        "compare" / "update_name"                          │
│  Result: state["query_type"] = "find_missing"             │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────┐
│  LangGraph Node 2: retriever_node                         │
│  File: backend/app/rag/agent.py → retriever_node()        │
│  Also: backend/app/rag/retriever.py → retrieve()          │
│  Does: Embeds the question (1536-dim vector)              │
│        Queries ChromaDB for top-5 closest chunks          │
│        Filters out chunks with score < 0.30               │
│  Result: state["retrieved_chunks"] = [list of 5 dicts]    │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────┐
│  LangGraph Node 3: reasoner                               │
│  File: backend/app/rag/agent.py → reasoner()              │
│  Does: Formats the 5 chunks as context string             │
│        Calls GPT-4o with system prompt:                   │
│        "Answer ONLY using the provided contract excerpts. │
│         Always cite which contract your answer comes from.│
│         If the information is not in the excerpts, say:   │
│         'Not found in the uploaded contracts.'"            │
│        Streams response token by token                    │
│  Result: state["answer"] = "Based on the contracts..."    │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────┐
│  LangGraph Node 4: formatter                              │
│  File: backend/app/rag/agent.py → formatter()             │
│  Does: Collects unique source filenames from chunks       │
│        Appends "**Sources:** contract_a.pdf, ..."         │
│  Result: state["sources"] = ["contract_a.pdf", ...]       │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
Tokens streamed as SSE:
  data: Based\n\n
  data:  on\n\n
  data:  the\n\n
  ...
  data: **Sources:** contract_nda.pdf\n\n
  data: [DONE]\n\n
```

---

## Part 7 — How to Test This (Simple Sense)

### Step 0 — Check the system is up

```bash
curl http://localhost:8000/health
```
```json
{"status": "ok", "document_count": 0, "mode": "demo", "app_env": "development"}
```
`document_count: 0` means nothing is ingested yet. That's expected.

### Step 1 — Ingest a contract

Put a real PDF in `backend/uploads/` and ingest it:

```bash
curl -X POST http://localhost:8000/api/ingest \
  -F "file=@backend/uploads/my_contract.pdf"
```
```json
{"filename": "my_contract.pdf", "file_type": ".pdf", "language": "en",
 "chunks_created": 4, "status": "success", "error": null}
```

Check health again — document count should now be 4:
```bash
curl http://localhost:8000/health
# {"status": "ok", "document_count": 4, ...}
```

### Step 2 — Ask a question and see SSE streaming

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Does this contract have a GDPR clause?"}' \
  --no-buffer
```

You will see tokens arriving one by one:
```
data: Based

data:  on

data:  the

data:  uploaded

data:  contracts

data: ,

data:  the

data:  NDA

...

data: **Sources:** my_contract.pdf

data: [DONE]
```

### Step 3 — Try a question with no answer in the contracts

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the weather in Berlin today?"}' \
  --no-buffer
```

Expected: the model will respond with:
`"This information was not found in the uploaded contracts."`

This confirms the grounding is working — GPT-4o is NOT using its internet knowledge.

### Step 4 — Test the 400 error for unsupported file type

```bash
curl -X POST http://localhost:8000/api/ingest \
  -F "file=@somefile.docx"
```
```json
{"detail": "Unsupported file type '.docx'. Accepted types: .jpeg, .jpg, .pdf, .png"}
```

### Step 5 — Run the automated test suite

```bash
cd backend
bash run_tests.sh
```

Expected: `55 passed` with 81%+ coverage, all tests run offline with no API calls.

### Step 6 — Inspect the vector store directly

```python
# cd backend && source venv/bin/activate && python
import chromadb
client = chromadb.PersistentClient(path="./chroma_db")
col = client.get_collection("riverty_contracts")
print("Stored chunks:", col.count())
peek = col.peek(3)
for i, doc_id in enumerate(peek["ids"]):
    print(doc_id, "→", peek["documents"][i][:80])
```

---

## Part 8 — Configuration Reference

All settings live in `backend/.env`. The defaults work for demo mode:

```bash
# Required for demo
OPENAI_API_KEY=sk-...your-key...

# Optional — change storage locations
UPLOAD_DIR=./uploads          # where raw files are saved
CHROMA_PERSIST_PATH=./chroma_db  # where vectors are persisted

# Optional — tune chunking
MAX_CHUNK_SIZE=1000           # characters per chunk
CHUNK_OVERLAP=200             # overlap between consecutive chunks
TOP_K_RESULTS=5               # how many chunks to retrieve per query

# Environment
APP_ENV=development
LOG_LEVEL=INFO
```

Change `MAX_CHUNK_SIZE` if your contracts are unusually short (try 500) or long (try 1500).
Change `TOP_K_RESULTS` if you want more context (try 8) or faster responses (try 3).

---

## Part 9 — File Map (Every Relevant File)

```
backend/
├── app/
│   ├── main.py                    ← FastAPI app, CORS, startup/shutdown
│   ├── config.py                  ← All settings, reads from .env
│   ├── models.py                  ← Pydantic schemas (IngestResponse, QueryRequest, etc.)
│   │
│   ├── api/routes/
│   │   ├── health.py              ← GET /health
│   │   ├── ingest.py              ← POST /api/ingest (validates, saves, calls pipeline)
│   │   └── query.py               ← POST /api/query (SSE streaming)
│   │
│   ├── etl/
│   │   ├── pipeline.py            ← Orchestrator: ties extract→clean→chunk→load together
│   │   ├── extractors/
│   │   │   ├── pdf_extractor.py   ← PyMuPDF + OCR fallback
│   │   │   └── ocr_extractor.py   ← Tesseract for JPG/PNG
│   │   ├── transformers/
│   │   │   ├── cleaner.py         ← Removes artifacts, detects language
│   │   │   └── chunker.py         ← Splits text, attaches metadata
│   │   └── loaders/
│   │       ├── chroma_loader.py   ← DEMO: stores vectors in ChromaDB
│   │       └── azure_loader.py    ← PRODUCTION STUB: Azure AI Search
│   │
│   ├── rag/
│   │   ├── embeddings.py          ← text → 1536-dim vector (OpenAI)
│   │   ├── retriever.py           ← queries ChromaDB, returns ranked chunks with sources
│   │   └── agent.py               ← LangGraph 4-node state machine
│   │
│   └── storage/
│       ├── local_storage.py       ← DEMO: saves to ./uploads/
│       └── azure_blob.py          ← PRODUCTION STUB: Azure Blob Storage
│
├── uploads/                       ← Raw contract files land here
├── chroma_db/                     ← Vectors + metadata land here (auto-created)
├── tests/
│   ├── conftest.py                ← Shared fixtures (mocks, temp db, sample pdf)
│   ├── test_etl.py                ← ETL unit tests (27 tests)
│   ├── test_rag.py                ← RAG unit tests (14 tests)
│   └── test_routes.py             ← HTTP route tests (14 tests)
└── run_tests.sh                   ← Single-command test runner
```
