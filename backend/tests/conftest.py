"""
conftest.py — Shared pytest fixtures for the entire test suite.
Provides: mock_openai_client, temp_chroma_db, sample_contract_path,
mock_storage, and integration fixtures (mock_openai_embedding,
temp_chroma_dir, nda_contract_path, german_contract_path,
sample_contracts_dir). All fixtures ensure tests run fully offline.
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

def _fake_embedding(dim: int = 1024) -> list[float]:
    """Return a deterministic unit vector of the given dimension."""
    return [1.0 / dim] * dim


def _make_mock_st_model(dim: int = 1024) -> MagicMock:
    """Build a SentenceTransformer mock whose encode() returns numpy-like arrays."""
    import numpy as np

    mock_model = MagicMock()

    def _encode(input_data, normalize_embeddings=True, batch_size=32, show_progress_bar=False, **kwargs):
        if isinstance(input_data, str):
            return np.array([1.0 / dim] * dim, dtype=np.float32)
        return np.array([[1.0 / dim] * dim] * len(input_data), dtype=np.float32)

    mock_model.encode.side_effect = _encode
    return mock_model


@pytest.fixture
def mock_openai_embeddings(monkeypatch):
    """Patch SentenceTransformer to return fake 1024-dim vectors offline.

    Name kept as mock_openai_embeddings for backward compatibility with all
    existing test signatures — the underlying model is now bge-m3 (local).
    """
    import app.rag.embeddings as emb_module

    mock_model = _make_mock_st_model()
    monkeypatch.setattr(emb_module, "_local_model", mock_model)
    monkeypatch.setattr(emb_module, "_service", None)  # reset singleton
    # SentenceTransformer is now a local import inside _get_local_model() so it
    # cannot be patched at module level. Patching _local_model directly is sufficient
    # because _get_local_model() short-circuits when _local_model is already set.
    yield mock_model


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

    Uses monkeypatch.setattr on the shared settings singleton so every module
    that already imported `settings` (e.g. chroma_loader, retriever) picks up
    the temp path without needing a module reload.
    Also isolates the ingestion registry so tests don't share state.
    """
    from app.config import settings

    chroma_path = str(tmp_path / "chroma")
    registry_path = str(tmp_path / "ingestion_registry.json")
    monkeypatch.setattr(settings, "chroma_persist_path", chroma_path)
    monkeypatch.setattr(settings, "registry_path", registry_path)
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
    """Return a list of chunk dicts that mimic ETL pipeline output.

    Includes page_number and total_chunks to match the updated extractor
    and chunker interfaces.
    """
    return [
        {
            "text": "This contract is governed by German law.",
            "metadata": {
                "source_file": "contract_a.pdf",
                "chunk_index": 0,
                "total_chunks": 2,
                "page_number": 1,
                "language": "en",
                "file_type": ".pdf",
                "char_count": 40,
            },
        },
        {
            "text": "Either party may terminate with 30 days notice.",
            "metadata": {
                "source_file": "contract_a.pdf",
                "chunk_index": 1,
                "total_chunks": 2,
                "page_number": 1,
                "language": "en",
                "file_type": ".pdf",
                "char_count": 47,
            },
        },
        {
            "text": "Der Vertrag unterliegt deutschem Recht.",
            "metadata": {
                "source_file": "contract_b.pdf",
                "chunk_index": 0,
                "total_chunks": 1,
                "page_number": 1,
                "language": "de",
                "file_type": ".pdf",
                "char_count": 39,
            },
        },
    ]


# ---------------------------------------------------------------------------
# Synthetic text fixtures (no file I/O — used by unit tests directly)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_english_text() -> str:
    """Return a realistic English NDA excerpt long enough for language detection."""
    return (
        "NON-DISCLOSURE AGREEMENT\n"
        "This Agreement is made between TechCorp GmbH and Riverty GmbH.\n"
        "GDPR Compliance: Both parties agree to comply with GDPR Article 28.\n"
        "Termination: Either party may terminate with 30 days written notice.\n"
        "Penalty: Breach incurs a penalty of EUR 50,000.\n"
    ) * 3  # repeat so langdetect has enough signal


@pytest.fixture
def sample_german_text() -> str:
    """Return a realistic German contract excerpt long enough for language detection."""
    return (
        "DIENSTLEISTUNGSVERTRAG\n"
        "Dieser Vertrag wird zwischen Müller Consulting GmbH und Riverty GmbH geschlossen.\n"
        "DSGVO-Compliance: Beide Parteien verpflichten sich zur Einhaltung der DSGVO.\n"
        "Kündigung: Der Vertrag kann mit 30 Tagen Frist gekündigt werden.\n"
    ) * 3


# ---------------------------------------------------------------------------
# Azure Search mock (production swap tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_azure_search():
    """Mock the Azure AI Search SDK for production swap tests."""
    with patch("app.etl.loaders.azure_loader.AzureSearchLoader") as mock_cls:
        instance = mock_cls.return_value
        instance.upload_documents.return_value = [MagicMock(succeeded=True)]
        instance.get_document_count.return_value = 10
        yield instance


# ---------------------------------------------------------------------------
# Integration test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_openai_embedding(monkeypatch):
    """Mock all OpenAI embedding calls for integration tests.

    Patches both the module-level get_embedding in chroma_loader (used by
    ChromaLoader.load) and the OpenAI constructor (used by ContractRetriever
    via EmbeddingService). Resets the EmbeddingService singleton so every
    test gets a fresh mock client.
    """
    import app.rag.embeddings as emb_module

    # Reset singleton so new EmbeddingService() picks up the mock client
    monkeypatch.setattr(emb_module, "_service", None)

    import app.rag.embeddings as emb_module

    fake_vector = [1.0 / 1024] * 1024
    mock_model = _make_mock_st_model()

    monkeypatch.setattr(emb_module, "_local_model", mock_model)
    monkeypatch.setattr(emb_module, "_service", None)

    # SentenceTransformer is a local import inside _get_local_model() — cannot be
    # patched at module level. Patching _local_model is sufficient.
    with patch("app.etl.loaders.chroma_loader.get_embeddings",
               side_effect=lambda texts: [fake_vector] * len(texts)):
        yield mock_model


@pytest.fixture
def temp_chroma_dir(tmp_path, monkeypatch):
    """Provide isolated temp directories for ChromaDB and file uploads.

    Patches both chroma_persist_path and upload_dir on the settings singleton
    so IngestionPipeline, ChromaLoader, ContractRetriever, and LocalStorage
    all use a clean temp directory with no cross-test pollution.
    """
    from app.config import settings

    chroma_path = str(tmp_path / "chroma")
    upload_path = str(tmp_path / "uploads")
    (tmp_path / "uploads").mkdir(parents=True, exist_ok=True)

    registry_path = str(tmp_path / "ingestion_registry.json")
    monkeypatch.setattr(settings, "chroma_persist_path", chroma_path)
    monkeypatch.setattr(settings, "upload_dir", upload_path)
    monkeypatch.setattr(settings, "registry_path", registry_path)
    yield chroma_path


@pytest.fixture
def nda_contract_path(tmp_path) -> Path:
    """Create a real text-based PDF from the NDA sample contract.

    Uses PyMuPDF (fitz) to produce a genuine text PDF that PDFExtractor can
    read with get_text() — not the minimal shell PDF used in unit tests.
    """
    import fitz

    txt_path = (
        Path(__file__).parent / "sample_contracts" / "contract_nda_techcorp_2023.txt"
    )
    text = txt_path.read_text(encoding="utf-8")

    doc = fitz.open()
    # Split into ~60-line pages so text stays within page bounds
    lines = text.split("\n")
    lines_per_page = 60
    for i in range(0, len(lines), lines_per_page):
        page = doc.new_page()
        page.insert_text(
            (50, 50),
            "\n".join(lines[i : i + lines_per_page]),
            fontname="helv",
            fontsize=9,
        )

    pdf_path = tmp_path / "contract_nda.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def german_contract_path(tmp_path) -> Path:
    """Create a real text-based PDF from the German Dienstleistungsvertrag sample."""
    import fitz

    txt_path = (
        Path(__file__).parent
        / "sample_contracts"
        / "vertrag_dienstleistung_mueller_2024.txt"
    )
    text = txt_path.read_text(encoding="utf-8")

    doc = fitz.open()
    lines = text.split("\n")
    lines_per_page = 60
    for i in range(0, len(lines), lines_per_page):
        page = doc.new_page()
        page.insert_text(
            (50, 50),
            "\n".join(lines[i : i + lines_per_page]),
            fontname="helv",
            fontsize=9,
        )

    pdf_path = tmp_path / "vertrag_dienstleistung_mueller_2024.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def sample_contracts_dir(tmp_path) -> Path:
    """Create PDFs for all 4 sample contracts in a temporary directory.

    Returns the directory path so tests can glob for *.pdf files.
    """
    import fitz

    contract_dir = tmp_path / "pdfs"
    contract_dir.mkdir()

    txt_files = [
        "contract_nda_techcorp_2023.txt",
        "contract_service_datasystems_2022.txt",
        "vertrag_dienstleistung_mueller_2024.txt",
        "contract_vendor_2023_no_termination.txt",
    ]
    src_dir = Path(__file__).parent / "sample_contracts"

    for txt_name in txt_files:
        text = (src_dir / txt_name).read_text(encoding="utf-8")
        pdf_name = txt_name.replace(".txt", ".pdf")

        doc = fitz.open()
        lines = text.split("\n")
        lines_per_page = 60
        for i in range(0, len(lines), lines_per_page):
            page = doc.new_page()
            page.insert_text(
                (50, 50),
                "\n".join(lines[i : i + lines_per_page]),
                fontname="helv",
                fontsize=9,
            )
        doc.save(str(contract_dir / pdf_name))
        doc.close()

    return contract_dir
