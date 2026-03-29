# transformers/ — Text Cleaners and Chunkers

## Components

### `cleaner.py` — Raw text → clean text
Responsibilities:
- Removes OCR artifacts: stray symbols (`|`, `_`, lone punctuation), excessive whitespace
- Normalises German umlauts if malformed by OCR (e.g. `a¨` → `ä`, `Ue` → `Ü`)
- Collapses multiple blank lines into single line breaks
- Detects document language using `langdetect` — attaches `language` to metadata
- Returns: cleaned text string + detected language code (`"en"` / `"de"`)

### `chunker.py` — Page-tagged pages → list of chunks with metadata
Responsibilities:
- Accepts `list[dict]` of `{"page_number": int, "text": str}` from any extractor
- **Detects content type** (rule-based, no API cost) and selects the best strategy:
  - **`qa`** — 3+ `Q:` lines detected → `QAChunker`: one chunk per Q+A pair
  - **`legal`** — 2+ `Section`/`Article` headers or 3+ legal keywords → `LegalChunker`: one chunk per section
  - **`narrative`** — everything else → `RecursiveCharacterTextSplitter` per page
- Attaches full source attribution metadata to every chunk:

```python
{
    "source_file": "contract_nda_techcorp_2023.pdf",
    "chunk_index": 2,
    "total_chunks": 8,
    "page_number": 3,       # ← which page in the original file
    "language": "en",
    "file_type": ".pdf",
    "char_count": 847
}
```

## Why Content-Aware Chunking Matters
A Q&A document split by 1000-character boundaries mixes 4–5 questions per chunk.
The embedding for that chunk is a blended average — the similarity score for any
single question gets diluted and can fall below the retrieval threshold. The answer
is never found even though it is in the document.

With `QAChunker`, each Q+A pair is its own chunk — the embedding is pure and specific,
similarity scores are high, and retrieval works correctly.

## Why Metadata on Every Chunk Matters
At query time the RAG agent must cite exactly which contract, which page, and which
section an answer comes from. Without per-chunk metadata, source references are lost.
`page_number` in the metadata enables the formatted answer to say:
`contract_nda_techcorp_2023.pdf — page 3, chunk 4/8 (relevance: 0.87)`
