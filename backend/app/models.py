"""
models.py — All Pydantic request and response schemas for the API.
Centralises data validation; all route handlers import their models from here.
No business logic — only shape definitions and field validators.
"""
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """Request body for the /query endpoint."""

    question: str = Field(..., min_length=3, max_length=500)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class IngestResponse(BaseModel):
    """Response returned after a contract file is ingested via the ETL pipeline."""

    filename: str
    file_type: str
    language: str
    chunks_created: int
    status: str
    error: str | None = None


class HealthResponse(BaseModel):
    """Response returned by the /health endpoint."""

    status: str
    document_count: int
    mode: str       # "demo" or "production"
    app_env: str
