# Pipeline Commands — Complete Reference

## Is the response from the LLM?

**Yes.** Here is exactly what generates the answer:

```
Your question
     ↓
Embedding model (text-embedding-3-small)
  → converts your question to a 1536-number vector
     ↓
ChromaDB similarity search
  → finds the 5 most semantically similar chunks from your documents
     ↓
GPT-4o (LLM)
  → reads those chunks as context
  → writes a grounded answer using ONLY what is in your documents
  → cites which file the answer came from
     ↓
Your answer (streamed word by word)
```

GPT-4o does **not** use internet knowledge. If the answer is not in your documents,
it says: *"This information was not found in the uploaded contracts."*

---

## Is the JSON→PDF conversion permanent?

**No.** That conversion was typed temporarily in the terminal during the demo.
It is not part of the codebase.

The pipeline only accepts `.pdf`, `.jpg`, `.jpeg`, `.png` files natively.
If you have a `.json`, `.txt`, or `.docx` file, convert it to PDF first
(see the conversion command below), then ingest the PDF.

---

## Prerequisites — One-Time Setup

```bash
# From the project root
cd backend

# Activate virtual environment
source ../.venv/bin/activate        # if .venv is in project root
# OR
source venv/bin/activate             # if venv is in backend/

# Create uploads folder
mkdir -p uploads
```

---

## Single Entry Point — Run Everything at Once

This one command does: ETL on all files in uploads/ → shows what's stored → runs a test query.

```bash
# From the project root
bash backend/run_pipeline.sh
```

With a specific question:
```bash
bash backend/run_pipeline.sh --query "What is the return policy?"
```

Ingest only (skip query):
```bash
bash backend/run_pipeline.sh --ingest-only
```

---

## Individual Commands

### Step 0 — (If needed) Convert JSON / text to PDF

Only needed if your source file is not already a PDF or image.

```bash
cd backend
source ../.venv/bin/activate

python -c "
import json, fitz
from pathlib import Path

# --- change these two lines ---
INPUT_FILE  = 'uploads/ecomdata.pdf'    # your source file (JSON/text named .pdf)
OUTPUT_FILE = 'uploads/ecomdata_real.pdf'
# ------------------------------

# Load content — handles JSON or plain text
try:
    data = json.load(open(INPUT_FILE))
    items = data.get('questions', data if isinstance(data, list) else [data])
    lines = []
    for item in items:
        lines.append(f'Q: {item.get(\"question\",\"\")}')
        lines.append(f'A: {item.get(\"answer\",\"\")}')
        lines.append('')
    text = '\n'.join(lines)
except (json.JSONDecodeError, TypeError):
    text = open(INPUT_FILE, encoding='utf-8').read()

print(f'Text length: {len(text)} chars')

# Write as real PDF
doc = fitz.open()
split = text.split('\n')
for i in range(0, len(split), 55):
    page = doc.new_page()
    page.insert_text((50, 50), '\n'.join(split[i:i+55]), fontname='helv', fontsize=9)
doc.save(OUTPUT_FILE)
doc.close()
print(f'Saved: {OUTPUT_FILE}')
"
```

---

### Step 1 — ETL: Ingest a single file

```bash
cd backend
source ../.venv/bin/activate

python -c "
import os
from app.etl.pipeline import IngestionPipeline

pipeline = IngestionPipeline()
result = pipeline.ingest(os.path.abspath('uploads/your_file.pdf'))

print('filename:        ', result['filename'])
print('language:        ', result['language'])
print('chars_extracted: ', result['chars_extracted'])
print('chunks_created:  ', result['chunks_created'])
print('status:          ', result['status'])
print('error:           ', result.get('error'))
"
```

What happens inside ETL:
```
uploads/your_file.pdf
  ↓ PDFExtractor      — PyMuPDF reads text layer (auto OCR if scanned)
  ↓ TextCleaner       — removes artifacts, detects language (en/de)
  ↓ DocumentChunker   — splits into ~1000-char chunks with 200-char overlap
  ↓ EmbeddingService  — each chunk → 1536-dim vector via OpenAI API
  ↓ ChromaLoader      — stores vectors + text + metadata in ChromaDB
```

### Step 1b — ETL: Ingest an entire folder

```bash
python -c "
import os
from app.etl.pipeline import IngestionPipeline

pipeline = IngestionPipeline()
folder = 'uploads/'

for filename in sorted(os.listdir(folder)):
    if filename.endswith(('.pdf', '.jpg', '.jpeg', '.png')):
        result = pipeline.ingest(os.path.abspath(os.path.join(folder, filename)))
        print(f\"{result['filename']:<50} lang={result['language']}  chunks={result['chunks_created']}  status={result['status']}\")
"
```

---

### Step 2 — Check what is stored in ChromaDB

```bash
python -c "
import chromadb
from app.config import settings

client = chromadb.PersistentClient(path=settings.chroma_persist_path)
col = client.get_collection('riverty_contracts')

print('Total chunks stored:', col.count())
print()
peek = col.peek(5)
for i, doc_id in enumerate(peek['ids']):
    meta = peek['metadatas'][i]
    text = peek['documents'][i]
    print(f'  {doc_id}')
    print(f'  source: {meta[\"source_file\"]}  chunk {meta[\"chunk_index\"]}  lang={meta[\"language\"]}')
    print(f'  text:   {text[:80].strip()}...')
    print()
"
```

---

### Step 3 — RAG: Run retrieval (see which chunks + sources match)

This step embeds your question and finds the closest chunks — **no LLM called yet**.

```bash
python -c "
from app.rag.retriever import ContractRetriever

retriever = ContractRetriever()
results = retriever.retrieve('What is the return policy?', top_k=5)

print(f'Found {len(results)} chunk(s):\n')
for i, r in enumerate(results):
    print(f'  Result #{i+1}')
    print(f'  source_file:      {r[\"source_file\"]}')
    print(f'  chunk_index:      {r[\"chunk_index\"]}')
    print(f'  language:         {r[\"language\"]}')
    print(f'  similarity_score: {r[\"similarity_score\"]}   (0=unrelated, 1=identical)')
    print(f'  text:             {r[\"text\"][:100].strip()}...')
    print()
"
```

Similarity score guide:
```
0.8 – 1.0   very strong match
0.5 – 0.8   good match
0.3 – 0.5   weak but relevant
< 0.3       filtered out automatically
```

---

### Step 4 — LLM: Run full RAG + GPT-4o query

This is retrieval + LLM answer together. Response streams word by word.

```bash
python -c "
import asyncio
from app.rag.agent import stream_query

async def ask(question):
    print(f'Q: {question}')
    print('A: ', end='', flush=True)
    async for token in stream_query(question):
        if token == '[DONE]':
            print()
        else:
            print(token, end='', flush=True)

asyncio.run(ask('What is the return policy?'))
"
```

---

### Step 5 — Via HTTP API (server must be running)

```bash
# Terminal 1 — start the server
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2 — run commands below
```

```bash
# Check system health + document count
curl http://localhost:8000/health

# Ingest a file
curl -X POST http://localhost:8000/api/ingest \
  -F "file=@backend/uploads/your_file.pdf"

# Ask a question (streaming SSE)
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the return policy?"}' \
  --no-buffer
```

---

## Clearing ChromaDB (start fresh)

```bash
# Delete all stored vectors and start over
rm -rf backend/chroma_db/
```

Next ingest will recreate it automatically.

---

## Quick Reference

| What you want | Command |
|---|---|
| Run everything (ETL + query) | `bash backend/run_pipeline.sh` |
| Run with custom question | `bash backend/run_pipeline.sh --query "your question"` |
| Ingest only, no query | `bash backend/run_pipeline.sh --ingest-only` |
| Ingest one file directly | `pipeline.ingest(os.path.abspath('uploads/file.pdf'))` |
| See what's in ChromaDB | `col.peek(5)` in Python |
| See retrieval + sources | `retriever.retrieve("question", top_k=5)` |
| Ask via LLM | `asyncio.run(stream_query("question"))` |
| Start API server | `uvicorn app.main:app --reload --port 8000` |
| Clear all stored data | `rm -rf backend/chroma_db/` |
| Run all tests | `bash backend/run_tests.sh` |
