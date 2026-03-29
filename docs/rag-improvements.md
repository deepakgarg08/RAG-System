# RAG Improvements — What Changed and Why

## Overview

This document describes all changes made to improve RAG retrieval accuracy,
source attribution precision, and chunking quality.

**Important:** Because the embedding model changed from `text-embedding-3-small`
(1536 dims) to `text-embedding-3-large` (3072 dims), **you must clear ChromaDB
and re-ingest all documents** before running the pipeline:

```bash
rm -rf backend/chroma_db/
bash backend/run_pipeline.sh
```

---

## 1. Content-Aware Chunking

**Problem:** The pipeline used a single `RecursiveCharacterTextSplitter` (1000 chars)
for every document type. A Q&A document with 4–5 question/answer pairs per chunk
produces a blended embedding — the similarity score for any single question gets
diluted and falls below the retrieval threshold. The answer is present in the document
but never returned.

**What was changed:** [backend/app/etl/transformers/chunker.py](../backend/app/etl/transformers/chunker.py)

The chunker now auto-detects document type and applies the right strategy:

| Detected Type | Signal | Strategy | Result |
|---|---|---|---|
| `qa` | 3+ lines starting with `Q:` | One chunk per Q+A pair | Each question has a focused, pure embedding |
| `legal` | 2+ Section/Article headers or 3+ legal keywords | One chunk per section | GDPR clause = one chunk, not split mid-sentence |
| `narrative` | No strong signals | `RecursiveCharacterTextSplitter` per page | Character-based with page boundaries respected |

Detection is rule-based (no API calls, no cost).

**Before:**
```
Chunk 3: Q: Can I return a product? A: Yes, within 30 days...
         Q: What payment methods? A: We accept Visa...
         Q: Can I request in my preferred color? A: ...
         Q: How long does shipping take? A: 3-5 days...
```
→ Similarity for color question: ~0.28 → filtered out → "Not found"

**After:**
```
Chunk 7: Q: Can I request a product if not available in my preferred color?
         A: If a product is not available in your preferred color, it may be
            temporarily out of stock. Please check back later or sign up...
```
→ Similarity for color question: ~0.82 → retrieved → correct answer

---

## 2. Page Numbers Stored Per Chunk

**Problem:** Extractors previously returned a single concatenated string, discarding
page boundaries. The Sources line only showed a filename with no location information —
unhelpful for large documents where the lawyer needs to find the exact passage.

**What was changed:**

- [backend/app/etl/extractors/base.py](../backend/app/etl/extractors/base.py) — `extract()` now returns `list[dict]` instead of `str`
- [backend/app/etl/extractors/pdf_extractor.py](../backend/app/etl/extractors/pdf_extractor.py) — reads each page separately, returns `[{"page_number": 1, "text": "..."}, ...]`
- [backend/app/etl/extractors/ocr_extractor.py](../backend/app/etl/extractors/ocr_extractor.py) — images are single-page, returns `[{"page_number": 1, "text": "..."}]`
- [backend/app/etl/transformers/chunker.py](../backend/app/etl/transformers/chunker.py) — accepts page dicts, attaches `page_number` to every chunk's metadata
- [backend/app/etl/pipeline.py](../backend/app/etl/pipeline.py) — passes page dicts through the whole ETL chain

Every chunk stored in ChromaDB now carries `page_number` in its metadata.

---

## 3. Rich Source Attribution in Answers

**Problem:** The formatted answer showed only filename in the Sources line:
```
**Sources:** ecomdata_converted.pdf
```
For a 50-page contract this is useless — the lawyer cannot locate the passage.

**What was changed:** [backend/app/rag/agent.py](../backend/app/rag/agent.py) — `formatter()` node

**Before:**
```
**Sources:** contract_nda_techcorp_2023.pdf
```

**After:**
```
**Sources:**
  • contract_nda_techcorp_2023.pdf — page 3, chunk 4/21 (relevance: 0.87)
  • vertrag_dienstleistung_mueller_2024.pdf — page 5, chunk 7/18 (relevance: 0.74)
```

Each source line gives:
- **File name** — which document
- **Page number** — which page in the original file to open
- **Chunk position** (e.g. `4/21`) — which section within the document
- **Relevance score** — how confident the retrieval was (0.0–1.0)

---

## 4. Upgraded Embedding Model

**Problem:** `text-embedding-3-small` (1536 dims) sometimes fails to match paraphrased
queries to document text. A user asking "favourite color" against text saying
"preferred color" gets a lower similarity score than needed.

**What was changed:** [backend/app/rag/embeddings.py](../backend/app/rag/embeddings.py)

| | Before | After |
|---|---|---|
| Model | `text-embedding-3-small` | `text-embedding-3-large` |
| Dimensions | 1536 | 3072 |
| Paraphrase matching | Moderate | Strong |
| Cost per 1M tokens | ~$0.02 | ~$0.13 |

The larger model handles synonym and paraphrase matching significantly better —
important for legal language where the same concept is expressed many ways.

**Re-indexing required:** Vectors from different embedding models cannot be mixed in
the same ChromaDB collection. Clear `backend/chroma_db/` and re-ingest after this change.

---

## 5. Lower Similarity Threshold + Higher top_k

**Problem:** `_MIN_SIMILARITY = 0.3` silently filtered out chunks that scored 0.28–0.29.
These were often the correct answer, just paraphrased. `top_k=5` also limited how many
candidates GPT-4o could reason over.

**What was changed:**

- [backend/app/rag/retriever.py](../backend/app/rag/retriever.py) — `_MIN_SIMILARITY` lowered from `0.30` → `0.15`
- [backend/app/config.py](../backend/app/config.py) — `TOP_K_RESULTS` default raised from `5` → `8`

The threshold change means marginally relevant chunks are still passed to GPT-4o.
GPT-4o is good at ignoring irrelevant context — it is better to give it more candidates
than to silently drop the right answer before it ever sees the question.

---

## Files Changed

| File | What changed |
|---|---|
| `app/etl/extractors/base.py` | `extract()` return type: `str` → `list[dict]` |
| `app/etl/extractors/pdf_extractor.py` | Per-page extraction, returns page dicts |
| `app/etl/extractors/ocr_extractor.py` | Returns `[{"page_number": 1, "text": ...}]` |
| `app/etl/transformers/chunker.py` | ContentTypeDetector + QAChunker + LegalChunker + page_number in metadata |
| `app/etl/pipeline.py` | Threads page dicts through full ETL chain |
| `app/rag/embeddings.py` | `text-embedding-3-small` → `text-embedding-3-large` (3072 dims) |
| `app/rag/retriever.py` | `_MIN_SIMILARITY` 0.30→0.15, `top_k` default 5→8, `page_number` in results |
| `app/rag/agent.py` | `formatter()` now outputs page + chunk position + score per source |
| `app/config.py` | `TOP_K_RESULTS` default 5→8 |
| `tests/conftest.py` | Embedding dim 1536→3072, sample_chunks include page_number + total_chunks |
| `tests/test_etl.py` | Chunker tests use page dicts, new QA/legal/page_number tests |
| `tests/test_rag.py` | Embedding dim, result schema, formatter assertions updated |
| `app/etl/extractors/README.md` | Updated interface description |
| `app/etl/transformers/README.md` | Updated chunking strategy docs |
| `app/rag/README.md` | Updated model, top_k, threshold docs |

---

## After These Changes — Re-index Required

```bash
# 1. Clear old vectors (different embedding model — cannot mix)
rm -rf backend/chroma_db/

# 2. Re-ingest your documents
bash backend/run_pipeline.sh

# 3. Run tests to verify everything passes
bash backend/run_tests.sh
```
