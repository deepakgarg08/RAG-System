# tests/ — Test Suite

## Strategy

| Layer | Test file | What is tested |
|---|---|---|
| ETL pipeline | `test_etl.py` | TextCleaner, DocumentChunker, PDFExtractor, ChromaLoader, IngestionPipeline |
| RAG layer | `test_rag.py` | EmbeddingService, ContractRetriever, LangGraph agent nodes |
| API routes | `test_routes.py` | GET /health, POST /api/ingest, POST /api/query (SSE) |

## Offline Testing Principle
All external services — OpenAI, ChromaDB, Azure — are **mocked**.
Tests must run with no internet connection and no API keys.
`os.environ.setdefault("OPENAI_API_KEY", "test-key")` is set at the top of `conftest.py`
so every test file imports safely.

## Shared Fixtures (`conftest.py`)

| Fixture | What it provides |
|---|---|
| `mock_openai_embeddings` | Patches `app.rag.embeddings.OpenAI` → returns deterministic 1536-dim fake vectors |
| `mock_openai_chat` | Patches `app.rag.agent.AsyncOpenAI` → returns a canned streamed completion |
| `temp_chroma_db` | Monkeypatches `settings.chroma_persist_path` to a `tmp_path` — real ChromaDB, temp data |
| `sample_pdf_path` | Returns path to a minimal valid PDF binary written to `tmp_path` |
| `sample_chunks` | Returns 3 pre-built chunk dicts (2 English, 1 German) for loader/retriever tests |

## Test Data
Sample contract text files live in `sample_contracts/`.
These are used as reference content — see [sample_contracts/README.md](sample_contracts/README.md).
For pipeline tests that need a real file, use the `sample_pdf_path` fixture which creates
a minimal PDF in `tmp_path`.

## Running Tests

```bash
# From the backend/ directory (with venv activated):

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=app --cov-report=html
open htmlcov/index.html

# Run a specific file
pytest tests/test_etl.py -v
pytest tests/test_rag.py -v
pytest tests/test_routes.py -v

# Run a specific test class or test
pytest tests/test_etl.py::TestTextCleaner -v
pytest tests/test_routes.py::test_health_returns_ok -v
```

## Single-Command Runner
From the project root:
```bash
bash backend/run_tests.sh
```
