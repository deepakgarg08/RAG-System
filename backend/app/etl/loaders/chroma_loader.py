"""
chroma_loader.py — DEMO vector store loader using ChromaDB.
Stores embedded chunks in a local ChromaDB collection persisted to disk.
Zero configuration required beyond CHROMA_PERSIST_PATH in config.
See loaders/README.md for the production swap to Azure AI Search.
"""
import logging

import chromadb

from app.config import settings
from app.etl.loaders.base import BaseLoader
from app.rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)

# ============================================================
# DEMO MODE: ChromaDB — zero config, persists to local disk
# PRODUCTION SWAP → Azure AI Search (AWS: OpenSearch / Kendra):
#   Replace ChromaLoader with AzureSearchLoader in pipeline.py
#   Azure AI Search adds hybrid search + enterprise RBAC + scale
#   See .claude/skills/swap-to-azure.md for step-by-step migration
# ============================================================

_COLLECTION_NAME = "riverty_contracts"


class ChromaLoader(BaseLoader):
    """Loads document chunks into a local ChromaDB vector store."""

    def __init__(self) -> None:
        """Initialise ChromaDB client and get/create the contracts collection."""
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_path)
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "ChromaLoader: connected to collection '%s' at %s (%d docs)",
            _COLLECTION_NAME,
            settings.chroma_persist_path,
            self._collection.count(),
        )

    def load(self, chunks: list[dict]) -> int:
        """Embed all chunks in one batch call and store them in ChromaDB.

        Previously called get_embedding() once per chunk (N HTTP requests for
        OpenAI, or N model forward passes for local). Now calls get_embeddings()
        once for all chunks — a single model pass regardless of chunk count.

        Args:
            chunks: List of chunk dicts with 'text' and 'metadata' keys
                    (output of DocumentChunker.chunk()).

        Returns:
            Number of chunks successfully stored.
        """
        if not chunks:
            return 0

        texts = [chunk["text"] for chunk in chunks]

        logger.info(
            "ChromaLoader: embedding %d chunks in one batch pass...", len(chunks)
        )
        embeddings = get_embeddings(texts)  # single call — all chunks at once

        ids = []
        docs = []
        metas = []

        for i, chunk in enumerate(chunks):
            source = chunk["metadata"].get("source_file", "unknown")
            chunk_idx = chunk["metadata"].get("chunk_index", i)
            ids.append(f"{source}_chunk_{chunk_idx}")
            docs.append(chunk["text"])
            metas.append(chunk["metadata"])

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=docs,
            metadatas=metas,
        )

        logger.info(
            "ChromaLoader: load complete — %d chunks stored (total in collection: %d)",
            len(chunks),
            self._collection.count(),
        )
        return len(chunks)

    def get_document_count(self) -> int:
        """Return the total number of chunks in the ChromaDB collection."""
        return self._collection.count()
