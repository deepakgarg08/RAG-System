# Setup Guide — Local Development

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.11+ | [python.org](https://python.org) or `pyenv install 3.11` |
| Node.js | 20+ | [nodejs.org](https://nodejs.org) or `nvm install 20` |
| Docker | 24+ | [docker.com/get-started](https://www.docker.com/get-started) |
| Git | 2.x+ | [git-scm.com](https://git-scm.com) |
| VS Code | Latest | [code.visualstudio.com](https://code.visualstudio.com) |
| OpenAI API key | — | [platform.openai.com](https://platform.openai.com) |
| Tesseract OCR | 5.x | See below |

### Installing Tesseract OCR

Tesseract is required to extract text from scanned JPEG/PNG contract files.

**macOS:**
```bash
brew install tesseract tesseract-lang
```

**Ubuntu / Debian (Linux):**
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng
```

**Windows:**
Download the installer from the [UB Mannheim Tesseract builds](https://github.com/UB-Mannheim/tesseract/wiki).
During installation, check **"Additional language data → German"**.
Add the install directory (e.g. `C:\Program Files\Tesseract-OCR`) to your `PATH`.

Verify installation:
```bash
tesseract --version
# Expected: tesseract 5.x.x
```

---

## Local Setup (Demo Mode — No Azure Needed)

### 1. Clone and enter the project
```bash
git clone <repository-url>
cd riverty-contract-review
```

### 2. Backend setup
```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows (Command Prompt)
# venv\Scripts\Activate.ps1       # Windows (PowerShell)

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
```
Open `.env` and set your OpenAI API key:
```
OPENAI_API_KEY=sk-...your-key-here...
```
All other values have working defaults for demo mode. No Azure credentials needed.

### 4. Start backend
```bash
uvicorn app.main:app --reload --port 8000
```
Expected output:
```
Starting Riverty Contract Review — mode: demo, env: development
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

Backend is available at: `http://localhost:8000`
Swagger UI (interactive API docs): `http://localhost:8000/docs`

### 5. Frontend setup (new terminal)
```bash
cd frontend
npm install
npm run dev
```
Frontend is available at: `http://localhost:3000`

---

## Test with Sample Data

Run this script from the `backend/` directory (with venv activated) to ingest all sample contracts:

```bash
cd backend
source venv/bin/activate

python -c "
from app.etl.pipeline import IngestionPipeline
import os

pipeline = IngestionPipeline()
sample_dir = 'tests/sample_contracts'

for filename in sorted(os.listdir(sample_dir)):
    if filename.endswith(('.pdf', '.jpg', '.jpeg', '.png')):
        path = os.path.join(sample_dir, filename)
        result = pipeline.ingest(path)
        print(f\"{result['filename']}: {result['status']} — {result['chunks_created']} chunks ({result['language']})\")
"
```

Expected output:
```
contract_msa_riverty_2023.pdf: success — 4 chunks (en)
contract_nda_techcorp_2023.pdf: success — 3 chunks (en)
contract_scanned_invoice.jpg: success — 2 chunks (de)
contract_service_datasystems_2022.pdf: success — 3 chunks (en)
```

Then verify via the health endpoint:
```bash
curl http://localhost:8000/health
# {"status":"ok","document_count":12,"mode":"demo","app_env":"development"}
```

---

## Run Tests

```bash
cd backend
source venv/bin/activate

# Run all tests with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=app --cov-report=html

# Open coverage report in browser
open htmlcov/index.html          # macOS
xdg-open htmlcov/index.html      # Linux
start htmlcov/index.html         # Windows
```

Expected output:
```
tests/test_etl.py::test_pdf_extractor_extracts_text PASSED
tests/test_etl.py::test_cleaner_removes_artifacts PASSED
tests/test_rag.py::test_retriever_returns_ranked_results PASSED
...
---------- coverage: 87% ----------
```

---

## Switching to Production Azure Mode

1. Provision the six Azure services listed in [azure-services.md](azure-services.md)
2. Add Azure credentials to `.env`:
```
# Azure OpenAI
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://<resource>.search.windows.net
AZURE_SEARCH_KEY=<key>
AZURE_SEARCH_INDEX_NAME=riverty-contracts

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_CONTAINER_NAME=contracts

# Azure Document Intelligence
AZURE_DOC_INTELLIGENCE_ENDPOINT=https://<resource>.cognitiveservices.azure.com
AZURE_DOC_INTELLIGENCE_KEY=<key>
```
3. Follow the swap comments in each file — see `.claude/skills/swap-to-azure.md` for step-by-step instructions
4. Run the full test suite to verify the production stack:
```bash
pytest tests/ -v
```
5. Check `/health` — `"mode"` should now return `"production"`:
```bash
curl http://localhost:8000/health
# {"status":"ok","document_count":0,"mode":"production","app_env":"development"}
```

---

## Troubleshooting

### 1. Tesseract not found
**Error:** `pytesseract.pytesseract.TesseractNotFoundError: tesseract is not installed`

**Fix:** Install Tesseract for your OS (see Prerequisites above), then verify it is on `PATH`:
```bash
which tesseract        # macOS/Linux — should print a path
tesseract --version    # should print version 5.x
```
On Windows, check that the Tesseract install directory is in System `PATH` (Control Panel → System → Environment Variables).

### 2. ChromaDB permission error
**Error:** `PermissionError: [Errno 13] Permission denied: './chroma_db'`

**Fix:** Ensure the `CHROMA_PERSIST_PATH` directory is writable by the current user:
```bash
mkdir -p ./chroma_db
chmod 755 ./chroma_db
```
Or set a different path in `.env`:
```
CHROMA_PERSIST_PATH=/tmp/riverty_chroma
```

### 3. OpenAI rate limit or authentication error
**Error:** `openai.RateLimitError` or `openai.AuthenticationError`

**Fix for auth error:** Check `.env` has a valid `OPENAI_API_KEY` starting with `sk-`. Ensure the `.env` file is in the `backend/` directory (same level as `app/`).

**Fix for rate limit:** The free OpenAI tier has low rate limits. Either:
- Add billing to your OpenAI account (pay-as-you-go), or
- Add a `time.sleep(1)` between embedding calls in `embeddings.py` for batch ingestion

### 4. CORS error in browser
**Error:** `Access to fetch at 'http://localhost:8000' from origin 'http://localhost:3000' has been blocked by CORS policy`

**Fix:** Verify the `allow_origins` list in `backend/app/main.py` includes your frontend URL:
```python
allow_origins=["http://localhost:3000"],
```
If your frontend runs on a different port, update this list and restart the backend.

### 5. SSE not streaming in browser (response appears all at once)
**Symptom:** The query response appears in full after a delay instead of streaming token by token.

**Fix:** This is usually caused by a buffering proxy between the browser and the backend.
The `X-Accel-Buffering: no` header in `query.py` disables nginx buffering. If using another
reverse proxy (Caddy, Traefik, Azure API Management), add the equivalent no-buffer directive:
- **Caddy:** `flush_interval -1` in the reverse_proxy block
- **Azure API Management:** set policy `<set-header name="X-Accel-Buffering"><value>no</value></set-header>`
- **Local browser testing with no proxy:** ensure you are not using a browser extension that buffers responses
