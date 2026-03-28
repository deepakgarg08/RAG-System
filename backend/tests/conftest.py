"""
conftest.py — Shared pytest fixtures for the entire test suite.
Provides: mock_openai_client, temp_chroma_db, sample_contract_path,
and mock_storage. All fixtures ensure tests run fully offline.
"""
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Environment — set fake keys before any app module is imported
# ---------------------------------------------------------------------------
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("APP_ENV", "test")


# ---------------------------------------------------------------------------
# OpenAI mock
# ---------------------------------------------------------------------------

def _fake_embedding(dim: int = 1536) -> list[float]:
    """Return a deterministic unit vector of the given dimension."""
    return [1.0 / dim] * dim


@pytest.fixture
def mock_openai_embeddings(monkeypatch):
    """Patch the OpenAI embeddings client to return fake vectors offline."""
    fake_item = MagicMock()
    fake_item.embedding = _fake_embedding()
    fake_item.index = 0

    fake_response = MagicMock()
    fake_response.data = [fake_item]

    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = fake_response

    with patch("app.rag.embeddings.OpenAI", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_openai_chat(monkeypatch):
    """Patch the AsyncOpenAI chat completions to return a canned answer."""
    async def _fake_astream(*args, **kwargs):
        """Async generator that yields one streamed chunk."""
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "Mocked answer."
        yield chunk

    fake_response = MagicMock()
    fake_response.__aiter__ = lambda self: _fake_astream()

    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(
        return_value=fake_response
    )

    with patch("app.rag.agent.AsyncOpenAI", return_value=mock_client):
        yield mock_client


# ---------------------------------------------------------------------------
# ChromaDB temp collection
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_chroma_db(tmp_path, monkeypatch):
    """Provide a real ChromaDB client backed by a temp directory.

    Monkeypatches CHROMA_PERSIST_PATH so all components use the same tmp db.
    """
    chroma_path = str(tmp_path / "chroma")
    monkeypatch.setenv("CHROMA_PERSIST_PATH", chroma_path)

    # Re-import settings after env change so the path is picked up
    import importlib
    import app.config as cfg_module
    importlib.reload(cfg_module)
    from app.config import settings
    settings.chroma_persist_path = chroma_path

    yield chroma_path


# ---------------------------------------------------------------------------
# Sample file fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_pdf_path(tmp_path) -> Path:
    """Return the path to a minimal valid PDF file for extractor tests."""
    # Minimal single-page PDF binary (well-formed, no fonts, no images)
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF\n"
    )
    p = tmp_path / "sample_contract.pdf"
    p.write_bytes(pdf_bytes)
    return p


# ---------------------------------------------------------------------------
# Sample chunks fixture (pre-built, no API calls needed)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_chunks() -> list[dict]:
    """Return a list of chunk dicts that mimic ETL pipeline output."""
    return [
        {
            "text": "This contract is governed by German law.",
            "metadata": {
                "source_file": "contract_a.pdf",
                "chunk_index": 0,
                "language": "en",
            },
        },
        {
            "text": "Either party may terminate with 30 days notice.",
            "metadata": {
                "source_file": "contract_a.pdf",
                "chunk_index": 1,
                "language": "en",
            },
        },
        {
            "text": "Der Vertrag unterliegt deutschem Recht.",
            "metadata": {
                "source_file": "contract_b.pdf",
                "chunk_index": 0,
                "language": "de",
            },
        },
    ]
