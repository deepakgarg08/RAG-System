"""
pdf_extractor.py — Text extraction from PDF files using PyMuPDF.
Handles text-based PDFs; automatically falls back to OCRExtractor if fewer
than 50 characters are extracted (indicating a scanned/image-only PDF).
"""
import logging
import os
import tempfile
from typing import TYPE_CHECKING

import fitz  # PyMuPDF

from app.etl.extractors.base import BaseExtractor

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ============================================================
# DEMO MODE: PyMuPDF — zero config, runs locally on any machine
# PRODUCTION SWAP → Azure Document Intelligence (AWS: Textract):
#   Replace this extractor with azure_doc_extractor.py
#   One API call handles typed PDFs, scanned PDFs, handwritten JPEGs,
#   tables, and form fields — simpler pipeline, better accuracy
# ============================================================

_OCR_FALLBACK_THRESHOLD = 50  # chars — below this, treat as scanned PDF


class PDFExtractor(BaseExtractor):
    """Extracts text from PDF files using PyMuPDF with automatic OCR fallback."""

    def extract(self, file_path: str) -> str:
        """Extract text from a PDF file.

        Opens each page with PyMuPDF. If the total extracted text is fewer than
        50 characters, the PDF is likely scanned — falls back to OCRExtractor on
        each page rendered as an image.

        Args:
            file_path: Absolute or relative path to the PDF file.

        Returns:
            Extracted text string, or empty string on failure.
        """
        try:
            doc = fitz.open(file_path)
            pages_text: list[str] = []

            for page in doc:
                pages_text.append(page.get_text())

            raw_text = "\n".join(pages_text)
            doc.close()

            char_count = len(raw_text.strip())
            logger.info(
                "PDFExtractor: %s — %d pages, %d chars extracted",
                os.path.basename(file_path),
                len(pages_text),
                char_count,
            )

            if char_count < _OCR_FALLBACK_THRESHOLD:
                logger.warning(
                    "PDFExtractor: PDF appears to be scanned (only %d chars), "
                    "falling back to OCR for %s",
                    char_count,
                    os.path.basename(file_path),
                )
                return self._ocr_fallback(file_path)

            return raw_text

        except Exception as exc:
            logger.error("PDFExtractor: failed to extract %s — %s", file_path, exc)
            return ""

    def _ocr_fallback(self, file_path: str) -> str:
        """Render PDF pages as images and run OCR on each."""
        # Import here to avoid circular dependency at module load
        from app.etl.extractors.ocr_extractor import OCRExtractor

        ocr = OCRExtractor()
        pages_text: list[str] = []

        try:
            doc = fitz.open(file_path)
            for page_num, page in enumerate(doc):
                # Render page to image at 2× resolution for better OCR accuracy
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = tmp.name
                    pix.save(tmp_path)

                page_text = ocr.extract(tmp_path)
                pages_text.append(page_text)
                os.unlink(tmp_path)

                logger.debug("PDFExtractor OCR fallback: page %d — %d chars", page_num, len(page_text))

            doc.close()
        except Exception as exc:
            logger.error("PDFExtractor: OCR fallback failed for %s — %s", file_path, exc)
            return ""

        return "\n".join(pages_text)

    def can_handle(self, file_extension: str) -> bool:
        """Return True for .pdf files."""
        return file_extension.lower() in [".pdf"]
