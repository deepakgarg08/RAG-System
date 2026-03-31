"""
cleaner.py — Raw text cleaning and language detection.
Removes OCR artifacts, normalises German umlauts, collapses whitespace, and
detects document language via langdetect. Optionally corrects common OCR
misspellings using pyspellchecker (English + German dictionaries).
"""
import logging
import re

from langdetect import detect, LangDetectException

logger = logging.getLogger(__name__)

# Lazy-loaded spell checker — only initialised when correct_ocr_errors() is called.
# Handles both English and German without requiring a language pre-selection.
_spell_en = None
_spell_de = None


def _get_spell_checkers():
    """Lazy-load pyspellchecker for English and German."""
    global _spell_en, _spell_de
    if _spell_en is None:
        try:
            from spellchecker import SpellChecker

            _spell_en = SpellChecker(language="en", distance=1)
            _spell_de = SpellChecker(language="de", distance=1)
        except Exception as exc:
            logger.warning("TextCleaner: pyspellchecker unavailable — %s", exc)
    return _spell_en, _spell_de


def _is_safe_to_correct(word: str) -> bool:
    """Return True only for plain lowercase words that are safe to spell-check.

    Skips: proper nouns (initial uppercase), abbreviations (all-caps), words
    with digits or punctuation, and short tokens (< 5 chars) where false
    positives are common.
    """
    if len(word) < 5:
        return False
    if not word.isalpha():
        return False
    if word[0].isupper():
        return False  # likely a proper noun or sentence-start capitalisation
    if word.isupper():
        return False  # abbreviation
    return True


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

    def correct_ocr_errors(self, text: str) -> str:
        """Correct common OCR misspellings in plain lowercase words.

        Only corrects words that are:
        - All alphabetic, lowercase, and at least 5 characters long
        - Unknown to both English and German dictionaries
        - Correctable within edit-distance 1 (obvious single-character OCR errors)

        Skips proper nouns, abbreviations, numbers, and short tokens to avoid
        false positives in legal text.  Corrections require consensus — a word is
        only fixed if *both* spell checkers agree on the same correction.

        Args:
            text: Cleaned text string (run clean() first).

        Returns:
            Text with corrected OCR misspellings.
        """
        spell_en, spell_de = _get_spell_checkers()
        if spell_en is None:
            return text  # library not available — pass through unchanged

        words = text.split()
        corrected: list[str] = []

        for word in words:
            # Strip surrounding punctuation for lookup, preserve it in output
            stripped = word.strip(".,;:!?\"'()")
            if not _is_safe_to_correct(stripped):
                corrected.append(word)
                continue

            # Check both dictionaries: if the word is known in either, leave it
            unknown_en = spell_en.unknown([stripped])
            unknown_de = spell_de.unknown([stripped])

            if not unknown_en or not unknown_de:
                corrected.append(word)  # known in at least one language
                continue

            # Only correct if both suggest the *same* correction (conservative)
            fix_en = spell_en.correction(stripped)
            fix_de = spell_de.correction(stripped)

            if fix_en and fix_de and fix_en == fix_de and fix_en != stripped:
                replacement = word.replace(stripped, fix_en)
                logger.debug(
                    "TextCleaner.correct_ocr_errors: '%s' → '%s'", stripped, fix_en
                )
                corrected.append(replacement)
            else:
                corrected.append(word)

        return " ".join(corrected)

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
