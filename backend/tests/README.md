# tests/ — Test Suite

## Strategy

| Layer | Test file | What is tested |
|---|---|---|
| ETL pipeline | `test_etl.py` | Extractors, chunker, cleaner, loaders |
| RAG layer | `test_rag.py` | Embeddings, retriever, agent nodes |
| API routes | `test_routes.py` | HTTP endpoints, status codes, response shapes |

## Offline Testing Principle
All external services — OpenAI, ChromaDB, Azure — are **mocked**.
Tests must run with no internet connection and no API keys.
This keeps the CI pipeline fast and free, and prevents flaky tests due to
external service outages.

## Shared Fixtures (`conftest.py`)
Provides reusable fixtures for all test files:
- `mock_openai_client` — returns deterministic fake embeddings and completions
- `temp_chroma_db` — in-memory ChromaDB instance, cleaned up after each test
- `sample_contract_path(name)` — returns absolute path to a file in `sample_contracts/`
- `mock_storage` — in-memory file store replacing local disk

## Test Data
Sample contracts live in `sample_contracts/`.
See [sample_contracts/README.md](sample_contracts/README.md) for the full index.

## Running Tests

```bash
# Run all tests
pytest backend/tests/ -v

# Run with coverage report
pytest backend/tests/ --cov=app --cov-report=html

# Run a specific test file
pytest backend/tests/test_etl.py -v

# Run a specific test
pytest backend/tests/test_etl.py::test_pdf_extraction_happy_path -v
```
