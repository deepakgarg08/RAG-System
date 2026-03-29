"""
ocr_extractor.py — Text extraction from scanned images via Tesseract OCR.
Handles JPEG and PNG inputs; pre-processes (grayscale, contrast enhance) before OCR.
Supports English and German via lang='eng+deu'. Returns empty list on failure.
Images are single-page by definition, so always returns one page dict.
"""
import logging
import os

import pytesseract
from PIL import Image, ImageEnhance

from app.etl.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)

# ============================================================
# DEMO MODE: Tesseract OCR — free, runs locally, supports eng+deu
# PRODUCTION SWAP → Azure Document Intelligence (AWS: Textract):
#   Replace this extractor with azure_doc_extractor.py
#   Azure Document Intelligence has higher accuracy for legal documents,
#   handles handwriting, tables, and form fields out of the box
# ============================================================

_TESSERACT_LANG = "eng+deu"
_TESSERACT_CONFIG = "--psm 6"  # Assume a single uniform block of text
_CONTRAST_FACTOR = 2.0


class OCRExtractor(BaseExtractor):
    """Extracts text from scanned images using Tesseract OCR with pre-processing.

    Images are single-page by definition — always returns a one-element list
    with page_number=1.
    """

    def extract(self, file_path: str) -> list[dict]:
        """Extract text from a scanned image file.

        Pre-processes the image (grayscale + contrast enhancement) before running
        Tesseract with English and German language support.

        Args:
            file_path: Absolute or relative path to the image file (.jpg, .jpeg, .png).

        Returns:
            List with one dict: [{"page_number": 1, "text": str}].
            Returns empty list on failure.
        """
        try:
            image = Image.open(file_path)
            width, height = image.size
            logger.info(
                "OCRExtractor: %s — size %dx%d, lang=%s",
                os.path.basename(file_path),
                width,
                height,
                _TESSERACT_LANG,
            )

            # Pre-process: grayscale → contrast enhancement
            image = image.convert("L")
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(_CONTRAST_FACTOR)

            text = pytesseract.image_to_string(
                image,
                lang=_TESSERACT_LANG,
                config=_TESSERACT_CONFIG,
            )

            char_count = len(text.strip())
            logger.info(
                "OCRExtractor: %s — %d chars extracted",
                os.path.basename(file_path),
                char_count,
            )
            return [{"page_number": 1, "text": text}]

        except Exception as exc:
            logger.error("OCRExtractor: failed to extract %s — %s", file_path, exc)
            return []

    def can_handle(self, file_extension: str) -> bool:
        """Return True for .jpg, .jpeg, .png files."""
        return file_extension.lower() in [".jpg", ".jpeg", ".png"]
