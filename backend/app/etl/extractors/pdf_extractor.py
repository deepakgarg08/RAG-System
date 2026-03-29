"""
pdf_extractor.py — Text extraction from PDF files using PyMuPDF.
Returns one dict per page so the chunker can track page-level source attribution.
Handles text-based PDFs; automatically falls back to OCR if fewer than 50 characters
are extracted across all pages (indicating a scanned/image-only PDF).
"""
import logging
import os
import tempfile

import fitz  # PyMuPDF
from PIL import Image, ImageEnhance

from app.etl.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)

# ============================================================
# DEMO MODE: PyMuPDF — zero config, runs locally on any machine
# PRODUCTION SWAP → Azure Document Intelligence (AWS: Textract):
#   Replace this extractor with azure_doc_extractor.py
#   One API call handles typed PDFs, scanned PDFs, handwritten JPEGs,
#   tables, and form fields — simpler pipeline, better accuracy
# ============================================================

_OCR_FALLBACK_THRESHOLD = 50  # chars total — below this, treat as scanned PDF
_TESSERACT_LANG = "eng+deu"
_TESSERACT_CONFIG = "--psm 6"
_CONTRAST_FACTOR = 2.0


class PDFExtractor(BaseExtractor):
    """Extracts text from PDF files using PyMuPDF with automatic OCR fallback.

    Returns a list of page dicts: [{"page_number": int, "text": str}, ...]
    so downstream components know exactly which page each text chunk came from.
    """

    def extract(self, file_path: str) -> list[dict]:
        """Extract text from a PDF file, one dict per page.

        Opens each page with PyMuPDF. If total extracted text is fewer than
        50 characters across all pages, the PDF is likely scanned — falls back
        to OCR on each page rendered as an image.

        Args:
            file_path: Absolute or relative path to the PDF file.

        Returns:
            List of {"page_number": int, "text": str} dicts, one per page.
            Returns empty list on failure.
        """
        try:
            doc = fitz.open(file_path)
            pages: list[dict] = []

            for page_num, page in enumerate(doc):
                pages.append({
                    "page_number": page_num + 1,
                    "text": page.get_text(),
                })

            doc.close()

            total_chars = sum(len(p["text"].strip()) for p in pages)
            logger.info(
                "PDFExtractor: %s — %d pages, %d chars extracted",
                os.path.basename(file_path),
                len(pages),
                total_chars,
            )

            if total_chars < _OCR_FALLBACK_THRESHOLD:
                logger.warning(
                    "PDFExtractor: PDF appears to be scanned (%d chars total), "
                    "falling back to OCR for %s",
                    total_chars,
                    os.path.basename(file_path),
                )
                return self._ocr_fallback(file_path)

            return pages

        except Exception as exc:
            logger.error("PDFExtractor: failed to extract %s — %s", file_path, exc)
            return []

    def _ocr_fallback(self, file_path: str) -> list[dict]:
        """Render PDF pages as images and run OCR on each, preserving page numbers."""
        pages: list[dict] = []

        try:
            doc = fitz.open(file_path)
            for page_num, page in enumerate(doc):
                mat = fitz.Matrix(2, 2)  # 2× resolution for better OCR accuracy
                pix = page.get_pixmap(matrix=mat)

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = tmp.name
                    pix.save(tmp_path)

                text = self._ocr_image(tmp_path)
                pages.append({"page_number": page_num + 1, "text": text})
                os.unlink(tmp_path)

                logger.debug(
                    "PDFExtractor OCR fallback: page %d — %d chars",
                    page_num + 1,
                    len(text),
                )

            doc.close()
        except Exception as exc:
            logger.error("PDFExtractor: OCR fallback failed for %s — %s", file_path, exc)
            return []

        return pages

    def _ocr_image(self, image_path: str) -> str:
        """Run Tesseract OCR on a single image file after pre-processing.

        Args:
            image_path: Path to the image file.

        Returns:
            Extracted text string, or empty string on failure.
        """
        try:
            import pytesseract
            image = Image.open(image_path).convert("L")
            image = ImageEnhance.Contrast(image).enhance(_CONTRAST_FACTOR)
            return pytesseract.image_to_string(
                image, lang=_TESSERACT_LANG, config=_TESSERACT_CONFIG
            )
        except Exception as exc:
            logger.error("PDFExtractor._ocr_image: failed — %s", exc)
            return ""

    def can_handle(self, file_extension: str) -> bool:
        """Return True for .pdf files."""
        return file_extension.lower() in [".pdf"]
