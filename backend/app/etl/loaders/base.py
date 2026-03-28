"""
base.py — Abstract base class for all vector store loaders.
Strategy Pattern: ChromaDB for demo, Azure AI Search for production.
Only the loader class needs to change — pipeline.py stays the same.
"""
from abc import ABC, abstractmethod


class BaseLoader(ABC):
    """Abstract base for all vector store loaders."""

    @abstractmethod
    def load(self, chunks: list[dict]) -> int:
        """Load chunks into vector store. Returns number of chunks stored."""
        pass

    @abstractmethod
    def get_document_count(self) -> int:
        """Return total number of chunks currently stored."""
        pass
