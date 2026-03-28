"""
test_routes.py — Integration tests for FastAPI HTTP endpoints.
Tests GET /health, POST /api/ingest, POST /api/query (SSE).
Uses FastAPI TestClient; all backend services are mocked.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared client fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client(temp_chroma_db):
    """Return a TestClient for the FastAPI app with a clean temp ChromaDB."""
    from app.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_shape(client):
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    assert isinstance(data["document_count"], int)
    assert data["mode"] in ("demo", "production")
    assert "app_env" in data


def test_health_mode_is_demo_without_azure(client):
    """mode should be 'demo' when AZURE_SEARCH_ENDPOINT is not set."""
    with patch("app.api.routes.health.settings") as mock_settings:
        mock_settings.azure_search_endpoint = ""
        mock_settings.app_env = "test"
        # Use a mock retriever to avoid real ChromaDB call
        with patch("app.api.routes.health.ContractRetriever") as mock_cls:
            mock_cls.return_value.get_collection_stats.return_value = {
                "total_documents": 0,
                "collection_name": "riverty_contracts",
            }
            response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["mode"] == "demo"


def test_health_document_count_reflects_collection(temp_chroma_db):
    """document_count should match what ContractRetriever reports."""
    from app.main import app
    client = TestClient(app)
    with patch("app.api.routes.health.ContractRetriever") as mock_cls:
        mock_cls.return_value.get_collection_stats.return_value = {
            "total_documents": 42,
            "collection_name": "riverty_contracts",
        }
        response = client.get("/health")
    assert response.json()["document_count"] == 42


def test_health_cors_header_present(client):
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


# ---------------------------------------------------------------------------
# POST /api/ingest
# ---------------------------------------------------------------------------

def test_ingest_unsupported_type_returns_400(client):
    response = client.post(
        "/api/ingest",
        files={"file": ("malware.exe", b"MZ binary", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_ingest_txt_returns_400(client):
    response = client.post(
        "/api/ingest",
        files={"file": ("contract.txt", b"Some text", "text/plain")},
    )
    assert response.status_code == 400


def test_ingest_pdf_success(client):
    """Valid PDF upload should return 200 with status=success."""
    fake_result = {
        "filename": "test.pdf",
        "file_type": ".pdf",
        "language": "en",
        "chunks_created": 3,
        "status": "success",
        "error": None,
    }
    with patch("app.api.routes.ingest.LocalStorage") as mock_storage_cls, \
         patch("app.api.routes.ingest.IngestionPipeline") as mock_pipeline_cls:
        mock_storage_cls.return_value.save.return_value = "/tmp/test.pdf"
        mock_pipeline_cls.return_value.ingest.return_value = fake_result

        response = client.post(
            "/api/ingest",
            files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["chunks_created"] == 3
    assert data["filename"] == "test.pdf"


def test_ingest_pipeline_failure_returns_failed_status(client):
    """Pipeline failure should return 200 with status=failed, not a 500."""
    failed_result = {
        "filename": "bad.pdf",
        "file_type": ".pdf",
        "language": "unknown",
        "chunks_created": 0,
        "status": "failed",
        "error": "Extraction failed",
    }
    with patch("app.api.routes.ingest.LocalStorage") as mock_storage_cls, \
         patch("app.api.routes.ingest.IngestionPipeline") as mock_pipeline_cls:
        mock_storage_cls.return_value.save.return_value = "/tmp/bad.pdf"
        mock_pipeline_cls.return_value.ingest.return_value = failed_result

        response = client.post(
            "/api/ingest",
            files={"file": ("bad.pdf", b"%PDF-1.4 corrupt", "application/pdf")},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error"] == "Extraction failed"


def test_ingest_response_has_required_fields(client):
    fake_result = {
        "filename": "c.pdf",
        "file_type": ".pdf",
        "language": "en",
        "chunks_created": 1,
        "status": "success",
        "error": None,
    }
    with patch("app.api.routes.ingest.LocalStorage") as mock_storage_cls, \
         patch("app.api.routes.ingest.IngestionPipeline") as mock_pipeline_cls:
        mock_storage_cls.return_value.save.return_value = "/tmp/c.pdf"
        mock_pipeline_cls.return_value.ingest.return_value = fake_result

        response = client.post(
            "/api/ingest",
            files={"file": ("c.pdf", b"%PDF-1.4", "application/pdf")},
        )

    data = response.json()
    for field in ("filename", "file_type", "language", "chunks_created", "status"):
        assert field in data, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

def test_query_streams_sse_tokens(client):
    """Response should be SSE with tokens and a [DONE] sentinel."""
    async def fake_stream(question: str):
        yield "Based "
        yield "on "
        yield "the "
        yield "contracts."
        yield "[DONE]"

    with patch("app.api.routes.query.stream_query", side_effect=fake_stream):
        response = client.post(
            "/api/query",
            json={"question": "Does this contract have a GDPR clause?"},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "data: Based " in body
    assert "data: [DONE]" in body


def test_query_short_question_returns_422(client):
    """Question shorter than 3 characters should fail Pydantic validation."""
    response = client.post("/api/query", json={"question": "hi"})
    assert response.status_code == 422


def test_query_missing_question_returns_422(client):
    response = client.post("/api/query", json={})
    assert response.status_code == 422


def test_query_sse_content_type_header(client):
    async def fake_stream(question: str):
        yield "token"
        yield "[DONE]"

    with patch("app.api.routes.query.stream_query", side_effect=fake_stream):
        response = client.post(
            "/api/query",
            json={"question": "What are the termination clauses?"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
