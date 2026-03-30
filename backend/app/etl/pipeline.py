"""
pipeline.py — ETL pipeline orchestrator.
Selects the correct extractor via EXTRACTOR_REGISTRY, runs the transform chain
(cleaner → chunker), embeds chunks, and delegates to the configured loader.
This file is the only place that knows which concrete implementations are active.
"""
import hashlib
import logging
import os
from datetime import datetime, timezone

from app.etl.extractors.base import BaseExtractor
from app.etl.extractors.ocr_extractor import OCRExtractor
from app.etl.extractors.pdf_extractor import PDFExtractor
from app.etl.loaders.chroma_loader import ChromaLoader
from app.etl.transformers.chunker import DocumentChunker
from app.etl.transformers.cleaner import TextCleaner
from app.rag.embeddings import _EMBEDDING_MODEL

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

    def ingest(self, file_path: str, uploaded_by: str = "anonymous") -> dict:
        """Run the full ETL pipeline on a single file.

        Steps:
            1. Detect file extension and select extractor
            2. Compute file-level metadata (size, checksum, timestamp)
            3. Extract raw text (returns list of page dicts)
            4. Clean each page's text and detect document language
            5. Chunk with content-aware strategy (Q&A / legal / narrative)
            6. Load chunks into vector store

        Args:
            file_path: Path to the file to ingest.
            uploaded_by: Identity of the uploader. Defaults to "anonymous".

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
            # --- Step 1: File-level metadata ---
            upload_timestamp = datetime.now(timezone.utc).isoformat()
            file_size_kb = max(1, os.path.getsize(file_path) // 1024)

            with open(file_path, "rb") as fh:
                checksum = "md5:" + hashlib.md5(fh.read()).hexdigest()

            # --- Step 2: Extract — returns list of {"page_number": int, "text": str} ---
            extractor_class = EXTRACTOR_REGISTRY[extension]
            is_scanned = extractor_class is OCRExtractor
            extraction_method = "ocr_tesseract" if is_scanned else "pymupdf"

            extractor = extractor_class()
            logger.info("Pipeline: extracting %s with %s", filename, extractor_class.__name__)
            pages = extractor.extract(file_path)
            total_pages = len(pages)
            result["chars_extracted"] = sum(len(p["text"]) for p in pages)
            logger.info(
                "Pipeline: extracted %d chars across %d page(s) from %s",
                result["chars_extracted"],
                total_pages,
                filename,
            )

            # --- Step 3: Clean each page ---
            cleaned_pages = [
                {"page_number": p["page_number"], "text": self._cleaner.clean(p["text"])}
                for p in pages
            ]

            # Detect language from combined text
            combined_text = " ".join(p["text"] for p in cleaned_pages)
            language = self._cleaner.detect_language(combined_text)
            result["language"] = language
            logger.info("Pipeline: language=%s for %s", language, filename)

            # --- Step 4: Chunk (content-aware: Q&A / legal / narrative) ---
            base_metadata = {
                "source_file": filename,
                "file_type": extension,
                "language": language,
            }
            chunks = self._chunker.chunk(
                cleaned_pages,
                base_metadata,
                file_size_kb=file_size_kb,
                total_pages=total_pages,
                checksum=checksum,
                extraction_method=extraction_method,
                is_scanned=is_scanned,
                embedding_model=_EMBEDDING_MODEL,
                upload_timestamp=upload_timestamp,
                uploaded_by=uploaded_by,
            )
            result["chunks_created"] = len(chunks)
            logger.info("Pipeline: created %d chunks for %s", len(chunks), filename)

            # --- Step 5: Load ---
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
