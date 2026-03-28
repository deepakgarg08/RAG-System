"""
cleaner.py — Raw text cleaning and language detection.
Removes OCR artifacts, normalises German umlauts, collapses whitespace, and
detects document language via langdetect. Returns (clean_text, language_code).
"""
import logging
import re

from langdetect import detect, LangDetectException

logger = logging.getLogger(__name__)


class TextCleaner:
    """Cleans raw extracted text and detects its language."""

    def clean(self, text: str) -> str:
        """Clean raw extracted text by removing artifacts and normalising whitespace.

        Steps:
        - Replace multiple spaces/tabs with a single space
        - Replace 3+ consecutive newlines with 2 newlines
        - Remove common OCR artifacts: stray pipe chars, long underscores, stray @ mid-word
        - Normalise malformed German umlauts from OCR misreads
        - Strip leading/trailing whitespace

        Args:
            text: Raw text string from an extractor.

        Returns:
            Cleaned text string.
        """
        # Normalise malformed German umlauts that OCR sometimes produces
        umlaut_fixes = {
            r"a\s?¨": "ä",
            r"o\s?¨": "ö",
            r"u\s?¨": "ü",
            r"A\s?¨": "Ä",
            r"O\s?¨": "Ö",
            r"U\s?¨": "Ü",
            r"\bUe\b": "Ü",
            r"\bue\b": "ü",
            r"\bAe\b": "Ä",
            r"\bOe\b": "Ö",
        }
        for pattern, replacement in umlaut_fixes.items():
            text = re.sub(pattern, replacement, text)

        # Remove stray pipe characters (common OCR artifact from table lines)
        text = re.sub(r"\|", " ", text)

        # Remove sequences of 4+ underscores (form fields / ruled lines)
        text = re.sub(r"_{4,}", "", text)

        # Remove stray @ symbols not part of an email address
        text = re.sub(r"(?<!\S)@(?!\S)", "", text)

        # Collapse multiple spaces and tabs to a single space
        text = re.sub(r"[ \t]+", " ", text)

        # Collapse 3 or more newlines to 2 newlines
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def detect_language(self, text: str) -> str:
        """Detect the primary language of the text.

        Uses langdetect to identify the language. Returns 'unknown' if the text
        is too short or detection fails.

        Args:
            text: Cleaned text string (should be at least ~50 chars for accuracy).

        Returns:
            ISO 639-1 language code: 'en', 'de', or 'unknown'.
        """
        try:
            lang = detect(text[:2000])  # Sample first 2000 chars for speed
            logger.info("TextCleaner: detected language '%s'", lang)
            return lang
        except LangDetectException:
            logger.warning("TextCleaner: language detection failed (text too short or ambiguous)")
            return "unknown"
        except Exception as exc:
            logger.error("TextCleaner: language detection error — %s", exc)
            return "unknown"
