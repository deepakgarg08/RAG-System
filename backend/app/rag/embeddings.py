"""
embeddings.py — Text-to-vector embedding service.

DEMO:       BAAI/bge-m3 via sentence-transformers — free, fully offline,
            multilingual (100+ languages including German), 1024-dim vectors,
            cross-lingual retrieval (English queries match German document chunks).

PRODUCTION: Azure OpenAI text-embedding-3-large — set APP_ENV=production in .env.
            No code changes required; the service branches automatically.
"""
import logging

import numpy as np

from app.config import settings
from app import state

logger = logging.getLogger(__name__)

# ============================================================
# DEMO MODE: BAAI/bge-m3 (sentence-transformers) — offline, free, multilingual
#   - Cross-lingual: English queries retrieve German document chunks
#   - First run downloads ~2.3 GB to ~/.cache/huggingface/ (once only)
#   - Subsequent runs load from local cache — no internet needed
# PRODUCTION SWAP → Azure OpenAI text-embedding-3-large (AWS: Bedrock Titan):
#   Set APP_ENV=production in .env — client switches automatically.
#   NOTE: dims change 1024 → 3072; clear chroma_db/ and re-ingest.
#   Why Azure OpenAI: data never leaves Microsoft tenant — required for
#   legal document compliance at Riverty
# ============================================================

# Active model name and dimensions — set by APP_ENV at import time.
# Imported by pipeline.py and ingestion_registry.py for metadata tagging.
if settings.app_env == "production":
    _EMBEDDING_MODEL = "text-embedding-3-large"
    _EMBEDDING_DIMS = 3072
    _BATCH_SIZE = 20
else:
    _EMBEDDING_MODEL = "BAAI/bge-m3"
    _EMBEDDING_DIMS = 1024
    _BATCH_SIZE = 32

# ------------------------------------------------------------------
# DEMO: sentence-transformers local model (lazy-loaded, cached globally)
# ------------------------------------------------------------------
# _local_model = None  # type: ignore[assignment]


def _get_local_model():
    from sentence_transformers import SentenceTransformer

    if state.embedding_model is None:
        logger.info("🔄 Loading embedding model (ONCE)...")
        state.embedding_model = SentenceTransformer(_EMBEDDING_MODEL)

    return state.embedding_model


# ------------------------------------------------------------------
# PRODUCTION: Azure OpenAI embeddings client helper
# ------------------------------------------------------------------

def _get_azure_client():  # type: ignore[return]
    """Return a synchronous AzureOpenAI client for embeddings."""
    from openai import AzureOpenAI  # local import — not loaded in demo

    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )


class EmbeddingService:
    """Converts text to dense embedding vectors.

    Branches automatically on APP_ENV:
      - demo/development: BAAI/bge-m3 local via sentence-transformers (offline, 1024-dim)
      - production:       Azure OpenAI text-embedding-3-large (3072-dim, data stays in Azure)
    """

    def __init__(self) -> None:
        """Initialise the embedding backend for the active environment."""
        self.mode = "azure" if settings.app_env == "production" else "local"
        self.model_name = _EMBEDDING_MODEL
        # if self.mode == "local":
        #     _get_local_model()  # pre-load so first embed call is fast
        logger.info(
            "EmbeddingService: mode=%s, model=%s, dims=%d",
            self.mode, self.model_name, _EMBEDDING_DIMS,
        )

    def get_embedding(self, text: str) -> list[float]:
        """Embed a single text string into a dense vector.

        Args:
            text: Text to embed. Normalised embeddings for cosine similarity.

        Returns:
            List of floats (1024-dim in demo, 3072-dim in production).
        """
        if self.mode == "azure":
            # ============================================================
            # PRODUCTION: Azure OpenAI text-embedding-3-large
            # Data stays within Azure tenant — legal compliance requirement
            # ============================================================
            client = _get_azure_client()
            response = client.embeddings.create(
                input=text.replace("\n", " "),
                model=_EMBEDDING_MODEL,
            )
            return response.data[0].embedding

        # ============================================================
        # DEMO: local BAAI/bge-m3 via sentence-transformers (offline)
        # ============================================================
        model = _get_local_model()
        vector: np.ndarray = model.encode(
            text.replace("\n", " "),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        logger.debug(
            "EmbeddingService.get_embedding: %d chars → %d-dim vector",
            len(text),
            len(vector),
        )
        return vector.tolist()

    def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts in one pass.

        Args:
            texts: List of text strings to embed.

        Returns:
            One float vector per input text, in input order.
        """
        if not texts:
            return []

        if self.mode == "azure":
            # ============================================================
            # PRODUCTION: Azure OpenAI — batched in groups of _BATCH_SIZE
            # ============================================================
            client = _get_azure_client()
            results: list[list[float]] = []
            for i in range(0, len(texts), _BATCH_SIZE):
                batch = [t.replace("\n", " ") for t in texts[i : i + _BATCH_SIZE]]
                response = client.embeddings.create(input=batch, model=_EMBEDDING_MODEL)
                results.extend(
                    item.embedding
                    for item in sorted(response.data, key=lambda x: x.index)
                )
            logger.info(
                "EmbeddingService.get_embeddings_batch (azure): %d texts → %d-dim each",
                len(texts), _EMBEDDING_DIMS,
            )
            return results

        # ============================================================
        # DEMO: single model forward pass for all texts at once
        # ============================================================
        model = _get_local_model()
        clean = [t.replace("\n", " ") for t in texts]
        vectors: np.ndarray = model.encode(
            clean,
            normalize_embeddings=True,
            batch_size=_BATCH_SIZE,
            show_progress_bar=False,
        )
        logger.info(
            "EmbeddingService.get_embeddings_batch (local): %d texts → %d-dim each",
            len(texts),
            vectors.shape[1] if len(vectors.shape) > 1 else _EMBEDDING_DIMS,
        )
        return [v.tolist() for v in vectors]


# ---------------------------------------------------------------------------
# Module-level helpers used by chroma_loader.py and retriever.py
# ---------------------------------------------------------------------------

_service: EmbeddingService | None = None


def _get_service() -> EmbeddingService:
    if state.embedding_service is None:
        state.embedding_service = EmbeddingService()
    return state.embedding_service


def get_embedding(text: str) -> list[float]:
    """Embed a single text. Used by retriever at query time."""
    return _get_service().get_embedding(text)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts in one pass. Used by chroma_loader at ingest time."""
    return _get_service().get_embeddings_batch(texts)
