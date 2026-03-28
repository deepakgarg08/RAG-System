# transformers/ — Text Cleaners and Chunkers

## Components

### `cleaner.py` — Raw text → clean text
Responsibilities:
- Removes OCR artifacts: stray symbols (`|`, `_`, lone punctuation), excessive whitespace
- Normalises German umlauts if malformed by OCR (e.g. `a¨` → `ä`, `Ue` → `Ü`)
- Collapses multiple blank lines into single line breaks
- Detects document language using `langdetect` — attaches `language` to metadata
- Returns: cleaned text string + detected language code (`"en"` / `"de"`)

### `chunker.py` — Clean text → list of chunks with metadata
Responsibilities:
- Splits text using LangChain `RecursiveCharacterTextSplitter`
  - `chunk_size=1000` (configurable via `MAX_CHUNK_SIZE` in config)
  - `chunk_overlap=200` (configurable via `CHUNK_OVERLAP` in config)
- Attaches a metadata dict to every chunk:

```python
{
    "source_file": "contract_nda_techcorp_2023.pdf",
    "chunk_index": 2,
    "total_chunks": 4,
    "language": "en",
    "file_type": ".pdf"
}
```

## Why Metadata on Every Chunk Matters
At query time, the RAG agent must cite which contract and which section an answer
comes from. Without per-chunk metadata, the source reference is lost when the chunk
is retrieved from the vector store. The metadata travels with the vector from
ingestion through retrieval to the final formatted answer.
