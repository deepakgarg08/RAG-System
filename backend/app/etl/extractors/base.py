"""
base.py — Abstract base class for all document extractors.
Uses the Strategy Pattern: all extractors share the same interface.
The pipeline selects the correct extractor based on file extension.

Extract returns a list of page dicts so downstream components can track
which page each piece of text came from — critical for source attribution
in legal document review.
"""
from abc import ABC, abstractmethod


class BaseExtractor(ABC):
    """Abstract base for all document text extractors."""

    @abstractmethod
    def extract(self, file_path: str) -> list[dict]:
        """Extract text from a file, returning one dict per page.

        Each dict has the form:
            {"page_number": int, "text": str}

        Returns an empty list on failure — never raises.
        """
        pass

    def can_handle(self, file_extension: str) -> bool:
        """Override to declare which extensions this extractor handles."""
        return False
