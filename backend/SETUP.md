# Riverty Contract Review — Setup & Run Guide

Everything you need to install, configure, run, and operate this project from scratch.

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.11+ | [python.org](https://python.org) or `pyenv install 3.11` |
| Node.js | 20+ | [nodejs.org](https://nodejs.org) or `nvm install 20` |
| Docker | 24+ | [docker.com/get-started](https://www.docker.com/get-started) — optional |
| Git | 2.x+ | [git-scm.com](https://git-scm.com) |
| OpenAI API key | — | [platform.openai.com](https://platform.openai.com) — only for GPT-4o answers, not embeddings |
| Tesseract OCR | 5.x | See below |

### Install Tesseract OCR

Required for scanned JPEG/PNG contract files.

```bash
# macOS
brew install tesseract tesseract-lang

# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng

# Windows — download installer from https://github.com/UB-Mannheim/tesseract/wiki
# During install: check "Additional language data → German"
# Add C:\Program Files\Tesseract-OCR to PATH

# Verify
tesseract --version   # should print 5.x.x
```

### Install Docker (optional — for containerised run)

```bash
# macOS: install Docker Desktop from https://www.docker.com/get-started

# Ubuntu
sudo apt-get install -y docker.io docker-compose
sudo systemctl enable docker
sudo usermod -aG docker $USER   # re-login after this

# Verify
docker --version          # Docker 24+
docker compose version    # Docker Compose v2+
```

---

## First-time Setup

### 1. Clone and enter the project

```bash
git clone <repository-url>
cd riverty-contract-review/backend
```

### 2. Create and activate virtual environment

```bash
python3 -m venv .venv

source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows (Command Prompt)
# .venv\Scripts\Activate.ps1       # Windows (PowerShell)
```

Your prompt shows `(.venv)` when active — required for every command below.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

This installs `sentence-transformers` for the local `BAAI/bge-m3` embedding model
(free, offline, multilingual — handles English and German contracts).

### 4. Configure environment

```bash
cp .env.example .env
```

Open `.env` and set:

```env
# Required — GPT-4o answer generation only (embeddings run locally, no API calls during ingest)
OPENAI_API_KEY=sk-...your-key-here...

# Optional — all defaults work for demo mode
APP_ENV=development
CHROMA_PERSIST_PATH=./chroma_db
UPLOAD_DIR=./uploads
MAX_CHUNK_SIZE=1000
CHUNK_OVERLAP=200
TOP_K_RESULTS=8
```

### 5. Download the embedding model (first run only)

`BAAI/bge-m3` (~2.3 GB) downloads automatically on first use and caches locally.
To pre-download explicitly:

```bash
python -c "
from sentence_transformers import SentenceTransformer
print('Downloading BAAI/bge-m3...')
SentenceTransformer('BAAI/bge-m3')
print('Done — cached at ~/.cache/huggingface/')
"
```

All subsequent runs are fully offline.

---

## Shell Scripts Reference

Three scripts are the main entry points. All are run from the **project root** or from inside `backend/`. They auto-detect any of these virtual environment names: `.venv`, `venv`, `riverty`.

---

### `run_pipeline.sh` — Ingest documents + Q&A

Use this when you have **new documents to add** to the system.

```bash
# From project root
bash backend/run_pipeline.sh               # ingest all files in uploads/ + interactive Q&A
bash backend/run_pipeline.sh --ingest-only # ingest only, skip Q&A
bash backend/run_pipeline.sh --query "Does this contract have a GDPR clause?"  # ingest + one question then exit
```

What it does step by step:
1. **ETL** — reads every `.pdf` / `.jpg` / `.jpeg` / `.png` from `uploads/`, extracts text page by page, detects content type (Q&A / legal / narrative), chunks accordingly, embeds with bge-m3 in one batch, stores in `chroma_db/`
2. **ChromaDB stats** — prints how many chunks are now stored and previews the first 5
3. **Q&A** — drops into an interactive question loop (or runs the `--query` one-shot and exits)

> Re-run this whenever you add new files to `uploads/`. Existing chunks are upserted (not duplicated).

---

### `run_rag.sh` — Q&A only (no ingest)

Use this for **every normal session** after documents are already ingested.

```bash
bash backend/run_rag.sh                              # interactive loop
bash backend/run_rag.sh --query "termination clause" # one question then exit
```

What it does:
- Skips ETL entirely — reads only from the existing `chroma_db/`
- Embeds your question with bge-m3, retrieves the most relevant chunks, sends to GPT-4o
- Prints retrieved chunk references (file, chunk index, similarity score) then the answer
- Shows detailed source attribution: `• filename — page N, chunk X/Y (relevance: 0.87)`

**Logs:** Internal INFO/DEBUG logs (retrieval scores, LangGraph node steps) are written to `backend/rag.log` only — the terminal shows only the answer. To monitor internals in real time:
```bash
tail -f backend/rag.log
```

---

### `run_tests.sh` — Run the full test suite

```bash
bash backend/run_tests.sh
```

What it does:
- Activates the venv and sets a fake `OPENAI_API_KEY` so tests run fully offline
- Runs all 88 tests with `pytest -v --tb=short`
- Generates a coverage report in `backend/htmlcov/index.html`

```bash
# Manual equivalent (from inside backend/)
OPENAI_API_KEY=test-key pytest tests/ -v --cov=app --cov-report=html
open htmlcov/index.html       # macOS
xdg-open htmlcov/index.html   # Linux
```

---

### Typical workflow

```bash
# First time — or when adding new documents
bash backend/run_pipeline.sh --ingest-only

# Every session after that
bash backend/run_rag.sh

# After code changes
bash backend/run_tests.sh
```

---

## Starting the API Server

```bash
uvicorn app.main:app --reload --port 8000
```

| Endpoint | Description |
|---|---|
| `GET  /health` | Health check + document count |
| `POST /api/ingest` | Upload a PDF/JPG/PNG |
| `POST /api/query` | Ask a question (SSE stream) |
| `GET  /docs` | Swagger interactive API docs |

---

## Clearing / Resetting ChromaDB

Clear and re-ingest whenever you:
- Change the embedding model (different vector dimensions)
- Update chunking settings
- Want a clean slate

```bash
# From project root
rm -rf backend/chroma_db/

# Or from inside backend/
rm -rf chroma_db/

# Re-ingest after clearing
bash run_pipeline.sh --ingest-only
```

---

## Docker

```bash
# Build and start
docker compose up --build

# Background
docker compose up --build -d

# Stop
docker compose down

# Copy a contract into the container and ingest
docker compose cp your_contract.pdf backend:/app/uploads/
docker compose exec backend bash run_pipeline.sh --ingest-only

# Clear ChromaDB inside Docker
docker compose exec backend rm -rf chroma_db/

# View logs
docker compose logs -f backend
```

---

## Retrieval Tuning

### Similarity threshold

Current: **`_MIN_SIMILARITY = 0.40`** in `app/rag/retriever.py`

Tuned for `BAAI/bge-m3` normalized embeddings. Scores are higher than OpenAI models
because bge-m3 uses normalized vectors (cosine similarity = dot product).

| Score | Meaning |
|---|---|
| 0.65–1.0 | Strongly relevant — confident match |
| 0.40–0.65 | Relevant — passed to GPT-4o |
| < 0.40 | Filtered out — noise / unrelated content |

> If you switch to Azure OpenAI `text-embedding-3-large`, lower to ~**0.30**
> (OpenAI models produce lower raw scores for the same semantic similarity).

To calibrate against your own documents:
```bash
python -c "
from app.rag.retriever import ContractRetriever
r = ContractRetriever()
for q in ['termination notice period', 'GDPR compliance', 'irrelevant random text']:
    results = r.retrieve(q, top_k=3)
    scores = [round(x['similarity_score'], 3) for x in results]
    print(f'{q:<40} scores: {scores}')
"
```

Set the threshold just below the lowest score a legitimate relevant result returns.

### top_k

**`TOP_K_RESULTS=8`** in `.env` — how many chunks GPT-4o sees per query.
For large document sets (50+ contracts) raise to 10–12.

---

## Switching Embedding Models

Changing the model requires a full re-index (different vector dimensions).

```bash
# 1. Edit app/rag/embeddings.py — comment/uncomment the right block
# 2. Clear old vectors
rm -rf chroma_db/
# 3. Re-ingest
bash run_pipeline.sh --ingest-only
```

| Model | Dims | Status |
|---|---|---|
| `BAAI/bge-m3` | 1024 | Active (demo) — free, offline, multilingual |
| `text-embedding-3-large` | 3072 | Commented in `embeddings.py` — Azure OpenAI for production |

---

## Production Azure Mode

1. Provision the six Azure services — see `docs/azure-services.md`
2. Add Azure credentials to `.env`:

```env
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o

AZURE_SEARCH_ENDPOINT=https://<resource>.search.windows.net
AZURE_SEARCH_KEY=<key>
AZURE_SEARCH_INDEX_NAME=riverty-contracts

AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_CONTAINER_NAME=contracts

AZURE_DOC_INTELLIGENCE_ENDPOINT=https://<resource>.cognitiveservices.azure.com
AZURE_DOC_INTELLIGENCE_KEY=<key>
```

3. Follow the swap comments in each source file — see `.claude/skills/swap-to-azure.md`
4. Verify: `curl http://localhost:8000/health` → `"mode": "production"`

---

## Common Commands

```bash
# Activate venv
source .venv/bin/activate

# Install / update deps
pip install -r requirements.txt

# Start API server
uvicorn app.main:app --reload --port 8000

# Full interactive pipeline
bash run_pipeline.sh

# Ingest only
bash run_pipeline.sh --ingest-only

# Single question
bash run_pipeline.sh --query "What are the termination terms?"

# Run tests
bash run_tests.sh

# Clear ChromaDB
rm -rf chroma_db/

# Inspect ChromaDB contents
python -c "
import chromadb
col = chromadb.PersistentClient('./chroma_db').get_collection('riverty_contracts')
print(f'Total chunks: {col.count()}')
r = col.get(include=['metadatas'])
for m in r['metadatas'][:5]:
    print(f\"  {m['source_file']} — page {m.get('page_number','?')}, chunk {m['chunk_index']}/{m['total_chunks']}\")
"

# Health check
curl http://localhost:8000/health

# Upload contract via API
curl -X POST http://localhost:8000/api/ingest -F "file=@contract.pdf"

# Query via API
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the termination notice period?"}'
```

---

## Troubleshooting

### `sentence_transformers` not found
```bash
pip install sentence-transformers==3.4.1
```

### bge-m3 model download fails
```bash
# Check cache
ls ~/.cache/huggingface/hub/

# Manual download via HuggingFace CLI
pip install huggingface_hub
huggingface-cli download BAAI/bge-m3
```

### Tesseract not found
```bash
which tesseract && tesseract --version
# If missing, install per Prerequisites above
```

### ChromaDB dimension mismatch
```
chromadb.errors.InvalidDimensionException: Embedding dimension X does not match collection dimension Y
```
You changed the embedding model without clearing ChromaDB:
```bash
rm -rf chroma_db/ && bash run_pipeline.sh --ingest-only
```

### OpenAI auth error (`OPENAI_API_KEY`)
```bash
cat .env | grep OPENAI   # check key is set and starts with sk-
```

### Port 8000 already in use
```bash
lsof -i :8000 && kill -9 <PID>
# or use a different port:
uvicorn app.main:app --reload --port 8001
```

### CORS error in browser
Add your frontend URL to `allow_origins` in `app/main.py` and restart the server.

### SSE not streaming (response appears all at once)
Caused by a buffering proxy. The `X-Accel-Buffering: no` header disables nginx buffering.
For other proxies: Caddy → `flush_interval -1`, Azure APIM → set the no-buffer header policy.
