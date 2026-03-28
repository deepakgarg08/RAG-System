# etl/ — Document Ingestion Pipeline

## What ETL Means Here
**Extract** text from uploaded contract files →
**Transform** (clean + chunk) into semantic units →
**Load** vectors into the vector store for retrieval.

## Decoupled by Design
This pipeline is **completely decoupled from the API layer**. It can be run as a
standalone batch job to process an entire SharePoint folder overnight — no HTTP
server required. The API route simply calls `pipeline.run()`.

## Design Pattern: Strategy Pattern
Every extractor, transformer, and loader is a swappable strategy.
The pipeline orchestrator (`pipeline.py`) never knows which concrete implementation
it is using — it only talks to the base interface. Swapping ChromaDB for Azure AI
Search means changing one line in `pipeline.py`.

## Data Flow (concrete example)

```
Contract PDF uploaded (1 file, ~50KB)
     ↓
[Extractor] pdf_extractor.py
  PyMuPDF reads text → ~3,400 raw characters
  If text < 50 chars → automatically falls back to OCR (scanned PDF detected)
     ↓
[Cleaner] cleaner.py
  Removes OCR artifacts, whitespace, stray symbols → ~3,200 clean characters
  Detects language → "en"
     ↓
[Chunker] chunker.py
  Splits into 4 chunks × 1000 chars with 200-char overlap
  Attaches metadata: {source, chunk_index, total_chunks, language, file_type}
     ↓
[Embedder] embeddings.py (in rag/)
  Each chunk → 1536-dimensional vector via OpenAI text-embedding-3-small
     ↓
[Loader] chroma_loader.py
  4 vectors + metadata stored in ChromaDB local collection
```

## Why Chunk Size 1000 / Overlap 200?

- **1000 chars ≈ one legal clause** — the natural atomic unit of meaning in a contract.
  A clause fits in one chunk; retrieval returns the full clause, not half of it.
- **200-char overlap** prevents a sentence from being split across a chunk boundary.
  The sentence tail from chunk N appears at the head of chunk N+1.
- **Tested alternatives:**
  - 500 chars: loses clause context — a clause split across 2+ chunks hurts precision
  - 2000 chars: too broad — retrieval returns large blocks with mixed topics

## Sub-folders

| Folder | Responsibility |
|---|---|
| `extractors/` | File format → raw text (PDF, JPEG/OCR, future: DOCX) |
| `transformers/` | Raw text → clean, chunked, metadata-enriched documents |
| `loaders/` | Chunked documents → vector store (ChromaDB demo / Azure AI Search prod) |
