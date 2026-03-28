"""
pipeline.py — ETL pipeline orchestrator.
Selects the correct extractor via EXTRACTOR_REGISTRY, runs the transform chain
(cleaner → chunker), embeds chunks, and delegates to the configured loader.
This file is the only place that knows which concrete implementations are active.
"""
import logging
import os

from app.etl.extractors.base import BaseExtractor
from app.etl.extractors.ocr_extractor import OCRExtractor
from app.etl.extractors.pdf_extractor import PDFExtractor
from app.etl.loaders.chroma_loader import ChromaLoader
from app.etl.transformers.chunker import DocumentChunker
from app.etl.transformers.cleaner import TextCleaner

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extractor registry — maps file extensions to extractor classes.
# To add a new file type, follow .claude/skills/add-new-extractor.md
# and add the extension here.
# ---------------------------------------------------------------------------
EXTRACTOR_REGISTRY: dict[str, type[BaseExtractor]] = {
    ".pdf": PDFExtractor,
    ".jpg": OCRExtractor,
    ".jpeg": OCRExtractor,
    ".png": OCRExtractor,
}

_SUPPORTED_TYPES = ", ".join(sorted(EXTRACTOR_REGISTRY.keys()))


class IngestionPipeline:
    """Orchestrates the full ETL pipeline: extract → clean → chunk → load."""

    def __init__(self) -> None:
        """Initialise pipeline components using the demo (ChromaDB) stack."""
        self._cleaner = TextCleaner()
        self._chunker = DocumentChunker()

        # ============================================================
        # DEMO MODE: ChromaDB — zero config, runs locally on any machine
        # PRODUCTION SWAP → Azure AI Search (AWS: OpenSearch / Kendra):
        #   Replace ChromaLoader() with AzureSearchLoader() on the line below
        #   Azure AI Search adds hybrid search + enterprise RBAC
        # ============================================================
        self._loader = ChromaLoader()

        # PRODUCTION: add Azure Blob upload step before extraction

    def ingest(self, file_path: str) -> dict:
        """Run the full ETL pipeline on a single file.

        Steps:
            1. Detect file extension and select extractor
            2. Extract raw text
            3. Clean text and detect language
            4. Chunk text with metadata
            5. Load chunks into vector store

        Args:
            file_path: Path to the file to ingest.

        Returns:
            Result dict with keys: filename, file_type, language,
            chars_extracted, chunks_created, status. On failure,
            status='failed' and an 'error' key is included.

        Raises:
            ValueError: If the file extension is not supported.
        """
        filename = os.path.basename(file_path)
        extension = os.path.splitext(filename)[1].lower()

        result: dict = {
            "filename": filename,
            "file_type": extension,
            "language": "unknown",
            "chars_extracted": 0,
            "chunks_created": 0,
            "status": "failed",
        }

        if extension not in EXTRACTOR_REGISTRY:
            raise ValueError(
                f"Unsupported file type '{extension}'. "
                f"Supported types: {_SUPPORTED_TYPES}"
            )

        try:
            # --- Step 1: Extract ---
            extractor_class = EXTRACTOR_REGISTRY[extension]
            extractor = extractor_class()
            logger.info("Pipeline: extracting %s with %s", filename, extractor_class.__name__)
            raw_text = extractor.extract(file_path)
            result["chars_extracted"] = len(raw_text)
            logger.info("Pipeline: extracted %d chars from %s", len(raw_text), filename)

            # --- Step 2: Clean ---
            clean_text = self._cleaner.clean(raw_text)
            language = self._cleaner.detect_language(clean_text)
            result["language"] = language
            logger.info("Pipeline: cleaned text (%d chars), language=%s", len(clean_text), language)

            # --- Step 3: Chunk ---
            base_metadata = {
                "source_file": filename,
                "file_type": extension,
                "language": language,
            }
            chunks = self._chunker.chunk(clean_text, base_metadata)
            result["chunks_created"] = len(chunks)
            logger.info("Pipeline: created %d chunks for %s", len(chunks), filename)

            # --- Step 4: Load ---
            stored = self._loader.load(chunks)
            logger.info("Pipeline: loaded %d chunks into vector store", stored)

            result["status"] = "success"
            return result

        except Exception as exc:
            logger.error("Pipeline: ingestion failed for %s — %s", filename, exc)
            result["error"] = str(exc)
            return result

    def get_document_count(self) -> int:
        """Return total number of chunks currently in the vector store."""
        return self._loader.get_document_count()
