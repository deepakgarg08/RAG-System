"""
base.py — Abstract base class for all document extractors.
Uses the Strategy Pattern: all extractors share the same interface.
The pipeline selects the correct extractor based on file extension.
"""
from abc import ABC, abstractmethod


class BaseExtractor(ABC):
    """Abstract base for all document text extractors."""

    @abstractmethod
    def extract(self, file_path: str) -> str:
        """Extract raw text from a file. Returns empty string on failure — never raises."""
        pass

    def can_handle(self, file_extension: str) -> bool:
        """Override to declare which extensions this extractor handles."""
        return False
