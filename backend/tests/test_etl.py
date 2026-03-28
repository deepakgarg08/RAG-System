"""
test_etl.py — Tests for the ETL ingestion pipeline.
Covers TextCleaner, DocumentChunker, PDFExtractor, ChromaLoader,
and IngestionPipeline. All external services are mocked.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# TextCleaner
# ---------------------------------------------------------------------------

class TestTextCleaner:
    """Tests for cleaner.py — artifact removal and language detection."""

    def test_clean_collapses_extra_whitespace(self):
        from app.etl.transformers.cleaner import TextCleaner
        cleaner = TextCleaner()
        assert cleaner.clean("hello   world") == "hello world"

    def test_clean_collapses_excess_newlines(self):
        from app.etl.transformers.cleaner import TextCleaner
        cleaner = TextCleaner()
        result = cleaner.clean("para one\n\n\n\npara two")
        assert "\n\n\n" not in result
        assert "para one" in result
        assert "para two" in result

    def test_clean_removes_pipe_artifacts(self):
        from app.etl.transformers.cleaner import TextCleaner
        cleaner = TextCleaner()
        result = cleaner.clean("column | value | other")
        assert "|" not in result

    def test_clean_removes_long_underscores(self):
        from app.etl.transformers.cleaner import TextCleaner
        cleaner = TextCleaner()
        result = cleaner.clean("Name: ___________")
        assert "____" not in result

    def test_clean_strips_leading_trailing_whitespace(self):
        from app.etl.transformers.cleaner import TextCleaner
        cleaner = TextCleaner()
        assert cleaner.clean("  hello  ") == "hello"

    def test_clean_normalises_german_umlauts(self):
        from app.etl.transformers.cleaner import TextCleaner
        cleaner = TextCleaner()
        # OCR misread: "a¨" → "ä"
        result = cleaner.clean("Vertra¨ge")
        assert "¨" not in result

    def test_clean_returns_string_on_empty_input(self):
        from app.etl.transformers.cleaner import TextCleaner
        cleaner = TextCleaner()
        assert cleaner.clean("") == ""

    def test_detect_language_english(self):
        from app.etl.transformers.cleaner import TextCleaner
        cleaner = TextCleaner()
        text = (
            "This Non-Disclosure Agreement is entered into between TechCorp GmbH "
            "and Riverty GmbH. The parties agree to keep all shared information confidential "
            "and not to disclose it to any third party without prior written consent."
        )
        lang = cleaner.detect_language(text)
        assert lang == "en"

    def test_detect_language_german(self):
        from app.etl.transformers.cleaner import TextCleaner
        cleaner = TextCleaner()
        text = (
            "Dieser Dienstleistungsvertrag wird zwischen der Firma Müller GmbH und "
            "Riverty GmbH geschlossen. Die Parteien verpflichten sich, alle ausgetauschten "
            "Informationen vertraulich zu behandeln und nicht an Dritte weiterzugeben."
        )
        lang = cleaner.detect_language(text)
        assert lang == "de"

    def test_detect_language_returns_unknown_on_too_short(self):
        from app.etl.transformers.cleaner import TextCleaner
        cleaner = TextCleaner()
        # langdetect fails on very short text — should return "unknown" not raise
        lang = cleaner.detect_language("hi")
        assert isinstance(lang, str)  # "en", "unknown" — both acceptable; must not raise


# ---------------------------------------------------------------------------
# DocumentChunker
# ---------------------------------------------------------------------------

class TestDocumentChunker:
    """Tests for chunker.py — text splitting and metadata attachment."""

    def test_chunk_returns_list_of_dicts(self):
        from app.etl.transformers.chunker import DocumentChunker
        chunker = DocumentChunker()
        chunks = chunker.chunk("Hello world. " * 100, {"source_file": "test.pdf", "file_type": ".pdf", "language": "en"})
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        assert "text" in chunks[0]
        assert "metadata" in chunks[0]

    def test_chunk_attaches_chunk_index(self):
        from app.etl.transformers.chunker import DocumentChunker
        chunker = DocumentChunker()
        text = "word " * 500  # long enough for multiple chunks
        chunks = chunker.chunk(text, {"source_file": "test.pdf", "file_type": ".pdf", "language": "en"})
        for i, chunk in enumerate(chunks):
            assert chunk["metadata"]["chunk_index"] == i

    def test_chunk_attaches_total_chunks(self):
        from app.etl.transformers.chunker import DocumentChunker
        chunker = DocumentChunker()
        text = "word " * 500
        chunks = chunker.chunk(text, {"source_file": "test.pdf", "file_type": ".pdf", "language": "en"})
        total = len(chunks)
        for chunk in chunks:
            assert chunk["metadata"]["total_chunks"] == total

    def test_chunk_preserves_base_metadata(self):
        from app.etl.transformers.chunker import DocumentChunker
        chunker = DocumentChunker()
        base = {"source_file": "contract.pdf", "file_type": ".pdf", "language": "de"}
        chunks = chunker.chunk("text " * 300, base)
        for chunk in chunks:
            assert chunk["metadata"]["source_file"] == "contract.pdf"
            assert chunk["metadata"]["language"] == "de"

    def test_chunk_empty_text_returns_empty_list(self):
        from app.etl.transformers.chunker import DocumentChunker
        chunker = DocumentChunker()
        chunks = chunker.chunk("", {"source_file": "empty.pdf", "file_type": ".pdf", "language": "en"})
        assert chunks == []

    def test_chunk_text_within_size_limit(self):
        from app.etl.transformers.chunker import DocumentChunker
        from app.config import settings
        chunker = DocumentChunker()
        text = "word " * 500
        chunks = chunker.chunk(text, {"source_file": "t.pdf", "file_type": ".pdf", "language": "en"})
        for chunk in chunks:
            # Allow slight overshoot at sentence boundaries, but broadly within limit
            assert len(chunk["text"]) <= settings.max_chunk_size * 1.2


# ---------------------------------------------------------------------------
# PDFExtractor
# ---------------------------------------------------------------------------

class TestPDFExtractor:
    """Tests for pdf_extractor.py — PDF text extraction."""

    def test_extract_returns_string_from_valid_pdf(self, sample_pdf_path):
        from app.etl.extractors.pdf_extractor import PDFExtractor
        extractor = PDFExtractor()
        result = extractor.extract(str(sample_pdf_path))
        assert isinstance(result, str)

    def test_extract_returns_empty_string_on_missing_file(self):
        from app.etl.extractors.pdf_extractor import PDFExtractor
        extractor = PDFExtractor()
        result = extractor.extract("/tmp/does_not_exist_abc123.pdf")
        assert result == ""

    def test_can_handle_pdf_extension(self):
        from app.etl.extractors.pdf_extractor import PDFExtractor
        extractor = PDFExtractor()
        assert extractor.can_handle(".pdf") is True
        assert extractor.can_handle(".PDF") is True
        assert extractor.can_handle(".jpg") is False


# ---------------------------------------------------------------------------
# ChromaLoader
# ---------------------------------------------------------------------------

class TestChromaLoader:
    """Tests for chroma_loader.py — vector store loading."""

    def test_load_stores_chunks_and_returns_count(self, temp_chroma_db, mock_openai_embeddings, sample_chunks):
        from app.etl.loaders.chroma_loader import ChromaLoader
        with patch("app.etl.loaders.chroma_loader.get_embedding") as mock_embed:
            mock_embed.return_value = [0.1] * 1536
            loader = ChromaLoader()
            stored = loader.load(sample_chunks)
        assert stored == len(sample_chunks)

    def test_load_increments_document_count(self, temp_chroma_db, sample_chunks):
        from app.etl.loaders.chroma_loader import ChromaLoader
        with patch("app.etl.loaders.chroma_loader.get_embedding") as mock_embed:
            mock_embed.return_value = [0.1] * 1536
            loader = ChromaLoader()
            before = loader.get_document_count()
            loader.load(sample_chunks)
            after = loader.get_document_count()
        assert after == before + len(sample_chunks)

    def test_get_document_count_returns_int(self, temp_chroma_db):
        from app.etl.loaders.chroma_loader import ChromaLoader
        loader = ChromaLoader()
        assert isinstance(loader.get_document_count(), int)

    def test_load_empty_chunks_returns_zero(self, temp_chroma_db):
        from app.etl.loaders.chroma_loader import ChromaLoader
        loader = ChromaLoader()
        stored = loader.load([])
        assert stored == 0


# ---------------------------------------------------------------------------
# IngestionPipeline
# ---------------------------------------------------------------------------

class TestIngestionPipeline:
    """Tests for pipeline.py — full ETL orchestration."""

    def test_ingest_pdf_happy_path(self, temp_chroma_db, sample_pdf_path, mock_openai_embeddings):
        from app.etl.pipeline import IngestionPipeline
        with patch("app.etl.loaders.chroma_loader.get_embedding") as mock_embed:
            mock_embed.return_value = [0.1] * 1536
            pipeline = IngestionPipeline()
            result = pipeline.ingest(str(sample_pdf_path))

        assert result["status"] == "success"
        assert result["filename"] == sample_pdf_path.name
        assert result["file_type"] == ".pdf"
        assert isinstance(result["chunks_created"], int)
        assert "error" not in result or result.get("error") is None

    def test_ingest_unsupported_type_raises_value_error(self, temp_chroma_db, tmp_path):
        from app.etl.pipeline import IngestionPipeline
        txt_file = tmp_path / "contract.txt"
        txt_file.write_text("Some contract text.")
        pipeline = IngestionPipeline()
        with pytest.raises(ValueError, match="Unsupported file type"):
            pipeline.ingest(str(txt_file))

    def test_ingest_returns_failed_status_on_corrupt_file(self, temp_chroma_db, tmp_path):
        from app.etl.pipeline import IngestionPipeline
        bad_pdf = tmp_path / "corrupt.pdf"
        bad_pdf.write_bytes(b"not a real pdf")
        with patch("app.etl.loaders.chroma_loader.get_embedding") as mock_embed:
            mock_embed.return_value = [0.1] * 1536
            pipeline = IngestionPipeline()
            result = pipeline.ingest(str(bad_pdf))
        # Empty/corrupt PDF: either 0 chunks + success, or status=failed with error key
        # Both are acceptable — the pipeline must not raise an unhandled exception
        assert result["status"] in ("success", "failed")
        assert "filename" in result

    def test_ingest_result_has_required_keys(self, temp_chroma_db, sample_pdf_path, mock_openai_embeddings):
        from app.etl.pipeline import IngestionPipeline
        with patch("app.etl.loaders.chroma_loader.get_embedding") as mock_embed:
            mock_embed.return_value = [0.1] * 1536
            pipeline = IngestionPipeline()
            result = pipeline.ingest(str(sample_pdf_path))

        for key in ("filename", "file_type", "language", "chunks_created", "status"):
            assert key in result, f"Missing key: {key}"

    def test_pipeline_detects_german_language(
        self, temp_chroma_db, sample_pdf_path, mock_openai_embeddings
    ):
        """Happy path: German text extracted from PDF is detected as language='de'."""
        german_text = (
            "DIENSTLEISTUNGSVERTRAG\n"
            "Dieser Vertrag wird zwischen Müller Consulting GmbH und Riverty GmbH geschlossen.\n"
            "DSGVO-Compliance: Beide Parteien verpflichten sich zur Einhaltung der DSGVO.\n"
            "Kündigung: Der Vertrag kann mit 30 Tagen Frist gekündigt werden.\n"
        ) * 6  # repeat so langdetect has enough signal
        from app.etl.pipeline import IngestionPipeline
        with patch("app.etl.loaders.chroma_loader.get_embedding") as mock_embed, \
             patch("app.etl.extractors.pdf_extractor.PDFExtractor.extract", return_value=german_text):
            mock_embed.return_value = [0.1] * 1536
            pipeline = IngestionPipeline()
            result = pipeline.ingest(str(sample_pdf_path))
        assert result["status"] == "success"
        assert result["language"] == "de"

    def test_pipeline_handles_empty_file(self, temp_chroma_db, tmp_path):
        """Edge case: zero-byte PDF does not raise — returns a result dict with required keys."""
        empty_pdf = tmp_path / "empty.pdf"
        empty_pdf.write_bytes(b"")
        from app.etl.pipeline import IngestionPipeline
        with patch("app.etl.loaders.chroma_loader.get_embedding") as mock_embed:
            mock_embed.return_value = [0.1] * 1536
            pipeline = IngestionPipeline()
            result = pipeline.ingest(str(empty_pdf))
        # Must not raise; status can be 'success' (0 chunks) or 'failed'
        assert "status" in result
        assert "filename" in result
        assert result["status"] in ("success", "failed")


# ---------------------------------------------------------------------------
# OCRExtractor
# ---------------------------------------------------------------------------

class TestOCRExtractor:
    """Tests for ocr_extractor.py — Tesseract-based image text extraction."""

    def test_extracts_text_from_valid_image(self, tmp_path):
        """Happy path: image file with mocked OCR returns expected text."""
        from PIL import Image
        img_path = tmp_path / "contract.png"
        img = Image.new("RGB", (400, 200), color=(255, 255, 255))
        img.save(str(img_path))

        from app.etl.extractors.ocr_extractor import OCRExtractor
        with patch("app.etl.extractors.ocr_extractor.pytesseract.image_to_string",
                   return_value="NDA Agreement valid text"):
            extractor = OCRExtractor()
            result = extractor.extract(str(img_path))
        assert result == "NDA Agreement valid text"

    def test_handles_blank_image(self, tmp_path):
        """Edge case: blank white image — OCR returns empty string without raising."""
        from PIL import Image
        img_path = tmp_path / "blank.png"
        Image.new("RGB", (200, 100), color=(255, 255, 255)).save(str(img_path))

        from app.etl.extractors.ocr_extractor import OCRExtractor
        with patch("app.etl.extractors.ocr_extractor.pytesseract.image_to_string",
                   return_value=""):
            extractor = OCRExtractor()
            result = extractor.extract(str(img_path))
        assert result == ""

    def test_supports_german_language(self, tmp_path):
        """Happy path: OCR is called with lang='eng+deu' so German text is supported."""
        from PIL import Image
        img_path = tmp_path / "german.png"
        Image.new("RGB", (300, 150), color=(255, 255, 255)).save(str(img_path))

        from app.etl.extractors.ocr_extractor import OCRExtractor, _TESSERACT_LANG
        with patch("app.etl.extractors.ocr_extractor.pytesseract.image_to_string",
                   return_value="Vertragstext") as mock_ocr:
            extractor = OCRExtractor()
            extractor.extract(str(img_path))
        _, call_kwargs = mock_ocr.call_args
        assert call_kwargs.get("lang") == _TESSERACT_LANG
        assert "deu" in _TESSERACT_LANG

    def test_returns_empty_on_missing_file(self):
        """Error: missing file path returns '' without raising an exception."""
        from app.etl.extractors.ocr_extractor import OCRExtractor
        extractor = OCRExtractor()
        result = extractor.extract("/tmp/nonexistent_image_xyz123.png")
        assert result == ""

    def test_can_handle_image_extensions(self):
        """Happy path: can_handle returns True for .jpg/.jpeg/.png only."""
        from app.etl.extractors.ocr_extractor import OCRExtractor
        extractor = OCRExtractor()
        assert extractor.can_handle(".jpg") is True
        assert extractor.can_handle(".jpeg") is True
        assert extractor.can_handle(".png") is True
        assert extractor.can_handle(".pdf") is False


# ---------------------------------------------------------------------------
# Additional DocumentChunker edge cases
# ---------------------------------------------------------------------------

class TestDocumentChunkerEdgeCases:
    """Additional edge-case tests for DocumentChunker."""

    def test_short_text_produces_single_chunk(self):
        """Edge case: text shorter than chunk_size produces exactly 1 chunk."""
        from app.etl.transformers.chunker import DocumentChunker
        chunker = DocumentChunker()
        short_text = "This is a short contract clause."
        chunks = chunker.chunk(short_text, {"source_file": "t.pdf", "file_type": ".pdf", "language": "en"})
        assert len(chunks) == 1
        assert chunks[0]["text"] == short_text

    def test_overlap_is_preserved_across_chunks(self):
        """Happy path: last overlap chars of chunk N appear at start of chunk N+1."""
        from app.etl.transformers.chunker import DocumentChunker
        from app.config import settings
        chunker = DocumentChunker()
        # Build text large enough to guarantee at least 2 chunks
        word = "contract "
        text = word * (settings.max_chunk_size // len(word) * 3)
        chunks = chunker.chunk(text, {"source_file": "t.pdf", "file_type": ".pdf", "language": "en"})
        if len(chunks) >= 2:
            tail = chunks[0]["text"][-settings.chunk_overlap:]
            head = chunks[1]["text"][:settings.chunk_overlap]
            # At least some overlap content must be shared
            assert any(w in head for w in tail.split() if w)

    def test_chunk_index_is_sequential(self):
        """Happy path: chunk_index is 0, 1, 2... and total_chunks is correct."""
        from app.etl.transformers.chunker import DocumentChunker
        chunker = DocumentChunker()
        text = "word " * 500
        chunks = chunker.chunk(text, {"source_file": "t.pdf", "file_type": ".pdf", "language": "en"})
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            assert chunk["metadata"]["chunk_index"] == i
            assert chunk["metadata"]["total_chunks"] == total


# ---------------------------------------------------------------------------
# Additional ChromaLoader tests
# ---------------------------------------------------------------------------

class TestChromaLoaderExtra:
    """Additional ChromaLoader tests for metadata storage and upsert semantics."""

    def test_loads_metadata_with_each_chunk(self, temp_chroma_db, sample_chunks):
        """Happy path: metadata fields are stored alongside each chunk vector."""
        from app.etl.loaders.chroma_loader import ChromaLoader
        with patch("app.etl.loaders.chroma_loader.get_embedding") as mock_embed:
            mock_embed.return_value = [0.1] * 1536
            loader = ChromaLoader()
            loader.load(sample_chunks)
            # Query back the stored items and verify metadata
            results = loader._collection.get(include=["metadatas"])
        stored_sources = [m["source_file"] for m in results["metadatas"]]
        assert "contract_a.pdf" in stored_sources
        assert "contract_b.pdf" in stored_sources

    def test_handles_duplicate_chunk_ids(self, temp_chroma_db, sample_chunks):
        """Edge case: ingesting the same file twice (upsert) does not raise or duplicate."""
        from app.etl.loaders.chroma_loader import ChromaLoader
        with patch("app.etl.loaders.chroma_loader.get_embedding") as mock_embed:
            mock_embed.return_value = [0.1] * 1536
            loader = ChromaLoader()
            loader.load(sample_chunks)
            count_after_first = loader.get_document_count()
            loader.load(sample_chunks)   # ingest the exact same chunks again
            count_after_second = loader.get_document_count()
        # Upsert — count must stay the same, not double
        assert count_after_second == count_after_first


# ---------------------------------------------------------------------------
# AzureSearchLoader stub tests
# ---------------------------------------------------------------------------

class TestAzureLoaderStub:
    """Verify that AzureSearchLoader raises NotImplementedError with helpful messages."""

    def test_azure_loader_raises_not_implemented_on_init(self):
        """AzureSearchLoader.__init__ raises NotImplementedError — it is a stub."""
        from app.etl.loaders.azure_loader import AzureSearchLoader
        with pytest.raises(NotImplementedError):
            AzureSearchLoader()

    def test_azure_loader_error_references_migration_guide(self):
        """NotImplementedError message references the swap-to-azure skill."""
        from app.etl.loaders.azure_loader import AzureSearchLoader
        with pytest.raises(NotImplementedError, match="swap-to-azure"):
            AzureSearchLoader()
