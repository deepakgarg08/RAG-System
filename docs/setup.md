# Setup Guide — Local Development

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.11+ | python.org or pyenv |
| Tesseract OCR | 5.x | See below |
| Node.js | 20+ | nodejs.org or nvm |
| Docker (optional) | 24+ | docker.com |
| OpenAI API key | — | platform.openai.com |

### Installing Tesseract

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-deu
```

**macOS:**
```bash
brew install tesseract tesseract-lang
```

**Windows:**
Download installer from: https://github.com/UB-Mannheim/tesseract/wiki

---

## Backend Setup

```bash
# 1. Clone the repo and enter backend
cd backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate      # Linux/Mac
# venv\Scripts\activate       # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY

# 5. Run the backend
uvicorn app.main:app --reload --port 8000
```

Backend will be available at: http://localhost:8000
API docs (Swagger UI): http://localhost:8000/docs

---

## Frontend Setup

```bash
# In a new terminal
cd frontend

npm install
npm run dev
```

Frontend will be available at: http://localhost:3000

---

## Docker Setup (Alternative)

```bash
# Build and run backend only
docker build -t riverty-backend ./backend
docker run -p 8000:8000 --env-file backend/.env riverty-backend

# Or use docker-compose (TODO: add docker-compose.yml in Prompt 2)
```

---

## Verify Installation

```bash
# Check backend health
curl http://localhost:8000/health

# Expected response:
# {"status": "ok", "document_count": 0, "mode": "demo"}
```

---

## Running Tests

```bash
cd backend
pytest tests/ -v
pytest tests/ --cov=app --cov-report=html
```

---

## Common Issues

| Problem | Solution |
|---|---|
| `tesseract not found` | Add Tesseract to PATH — see install instructions above |
| `OPENAI_API_KEY not set` | Check `.env` file exists and has a valid key |
| ChromaDB permission error | Ensure `CHROMA_PERSIST_PATH` directory is writable |
| Port 8000 in use | `lsof -i :8000` to find process, or change port in uvicorn command |
