"""
chroma_loader.py — Vector store loader: ChromaDB (demo) or Azure AI Search (production).
Stores embedded chunks and provides load/count operations.
Set APP_ENV=production in .env to switch to Azure AI Search automatically.
See loaders/README.md for the full migration guide.
"""
import logging

from app.config import settings
from app.etl.loaders.base import BaseLoader
from app.rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)

# ============================================================
# DEMO MODE: ChromaDB — zero config, persists to local disk
# PRODUCTION SWAP → Azure AI Search (AWS: OpenSearch / Kendra):
#   Set APP_ENV=production in .env — loader switches automatically.
#   Azure AI Search adds hybrid search + enterprise RBAC + scale.
#   See .claude/skills/swap-to-azure.md for step-by-step migration
# ============================================================

_COLLECTION_NAME = "riverty_contracts"


class ChromaLoader(BaseLoader):
    """Loads document chunks into a vector store.

    Branches automatically on APP_ENV:
      - demo/development: ChromaDB local (zero config, persists to disk)
      - production:       Azure AI Search (hybrid search, enterprise RBAC)
    """

    def __init__(self) -> None:
        """Initialise the vector store backend for the active environment."""
        if settings.app_env == "production":
            # ============================================================
            # PRODUCTION: Azure AI Search
            # AWS equivalent: Amazon OpenSearch / Kendra
            # Provides: hybrid search, enterprise security, Azure AD integration
            # Switch: set APP_ENV=production in .env + fill AZURE_SEARCH_* vars
            # ============================================================
            from app.etl.loaders.azure_loader import AzureSearchLoader  # local import

            self._azure_loader = AzureSearchLoader()
            self._mode = "azure"
            logger.info("ChromaLoader: mode=azure (Azure AI Search)")
        else:
            # ============================================================
            # DEMO: ChromaDB local vector store
            # Zero config, runs in-process, persists to local disk
            # Switch: set APP_ENV=production in .env
            # ============================================================
            import chromadb  # local import — not loaded in production

            self._client = chromadb.PersistentClient(path=settings.chroma_persist_path)
            self._collection = self._client.get_or_create_collection(
                name=_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            self._mode = "chroma"
            logger.info(
                "ChromaLoader: mode=chroma, collection='%s' at %s (%d docs)",
                _COLLECTION_NAME,
                settings.chroma_persist_path,
                self._collection.count(),
            )

    def load(self, chunks: list[dict]) -> int:
        """Embed all chunks in one batch call and store them in the active vector store.

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

        if self._mode == "azure":
            return self._azure_loader.load(chunks)

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
        """Return the total number of chunks in the active vector store."""
        if self._mode == "azure":
            return self._azure_loader.get_document_count()
        return self._collection.count()
