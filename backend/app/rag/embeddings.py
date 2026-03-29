"""
embeddings.py — Text-to-vector embedding service.

DEMO:       BAAI/bge-m3 via sentence-transformers — free, fully offline,
            multilingual (100+ languages including German), 1024-dim vectors,
            cross-lingual retrieval (English queries match German document chunks).

PRODUCTION: Azure OpenAI text-embedding-3-large — swap the implementation block below.
"""
import logging

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# DEMO MODE: BAAI/bge-m3 (sentence-transformers) — offline, free, multilingual
#   - Cross-lingual: English queries retrieve German document chunks
#   - First run downloads ~2.3 GB to ~/.cache/huggingface/ (once only)
#   - Subsequent runs load from local cache — no internet needed
# PRODUCTION SWAP → Azure OpenAI text-embedding-3-large (AWS: Bedrock Titan):
#   1. Comment out the SentenceTransformer block below
#   2. Uncomment the AzureOpenAI block
#   3. Set AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT in .env
#   4. Clear chroma_db/ and re-ingest (different dims: 1024 → 3072)
#   Why Azure OpenAI: data never leaves Microsoft tenant — required for
#   legal document compliance at Riverty
# ============================================================

_EMBEDDING_MODEL = "BAAI/bge-m3"
_EMBEDDING_DIMS = 1024
_BATCH_SIZE = 32

# ------------------------------------------------------------------
# DEMO: sentence-transformers local model (currently active)
# ------------------------------------------------------------------
_local_model: SentenceTransformer | None = None


def _get_local_model() -> SentenceTransformer:
    """Lazy-load the bge-m3 model (downloaded once, cached locally)."""
    global _local_model
    if _local_model is None:
        logger.info(
            "EmbeddingService: loading %s from local cache "
            "(first run downloads ~2.3 GB from HuggingFace)...",
            _EMBEDDING_MODEL,
        )
        _local_model = SentenceTransformer(_EMBEDDING_MODEL)
        logger.info("EmbeddingService: model loaded (%d dims)", _EMBEDDING_DIMS)
    return _local_model


# ------------------------------------------------------------------
# PRODUCTION: Azure OpenAI (uncomment to swap)
# ------------------------------------------------------------------
# from openai import AzureOpenAI
# _EMBEDDING_MODEL = "text-embedding-3-large"
# _EMBEDDING_DIMS = 3072
# _BATCH_SIZE = 20
#
# def _get_azure_client() -> AzureOpenAI:
#     return AzureOpenAI(
#         api_key=settings.azure_openai_api_key,
#         azure_endpoint=settings.azure_openai_endpoint,
#         api_version=settings.azure_openai_api_version,
#     )
#
# -- OR direct OpenAI (demo alternative to local model) --
# from openai import OpenAI
# _EMBEDDING_MODEL = "text-embedding-3-large"
# _EMBEDDING_DIMS = 3072
# _BATCH_SIZE = 20
#
# def _get_openai_client() -> OpenAI:
#     return OpenAI(api_key=settings.openai_api_key)


class EmbeddingService:
    """Converts text to dense embedding vectors.

    Demo implementation uses BAAI/bge-m3 locally via sentence-transformers.
    Production implementation uses Azure OpenAI text-embedding-3-large.
    """

    def __init__(self) -> None:
        """Pre-load the local model so the first embed call is not slow."""
        _get_local_model()

    # ------------------------------------------------------------------
    # DEMO implementation (bge-m3 local)
    # ------------------------------------------------------------------

    def get_embedding(self, text: str) -> list[float]:
        """Embed a single text string into a 1024-dimensional vector.

        Args:
            text: Text to embed. Normalised embeddings for cosine similarity.

        Returns:
            List of 1024 floats.
        """
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
        """Embed a list of texts in a single model pass (no per-text API calls).

        Args:
            texts: List of text strings to embed.

        Returns:
            List of 1024-dim float vectors, one per input text, in input order.
        """
        if not texts:
            return []

        model = _get_local_model()
        clean = [t.replace("\n", " ") for t in texts]
        vectors: np.ndarray = model.encode(
            clean,
            normalize_embeddings=True,
            batch_size=_BATCH_SIZE,
            show_progress_bar=False,
        )
        logger.info(
            "EmbeddingService.get_embeddings_batch: %d texts → %d-dim vectors each",
            len(texts),
            vectors.shape[1] if len(vectors.shape) > 1 else _EMBEDDING_DIMS,
        )
        return [v.tolist() for v in vectors]

    # ------------------------------------------------------------------
    # PRODUCTION implementation (uncomment and replace above when swapping)
    # ------------------------------------------------------------------
    # def get_embedding(self, text: str) -> list[float]:
    #     client = _get_azure_client()
    #     response = client.embeddings.create(
    #         input=text.replace("\n", " "), model=_EMBEDDING_MODEL
    #     )
    #     return response.data[0].embedding
    #
    # def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
    #     client = _get_azure_client()
    #     results = []
    #     for i in range(0, len(texts), _BATCH_SIZE):
    #         batch = [t.replace("\n", " ") for t in texts[i:i + _BATCH_SIZE]]
    #         response = client.embeddings.create(input=batch, model=_EMBEDDING_MODEL)
    #         results.extend(item.embedding for item in sorted(response.data, key=lambda x: x.index))
    #     return results


# ---------------------------------------------------------------------------
# Module-level helpers used by chroma_loader.py and retriever.py
# ---------------------------------------------------------------------------

_service: EmbeddingService | None = None


def _get_service() -> EmbeddingService:
    """Return the shared EmbeddingService singleton."""
    global _service
    if _service is None:
        _service = EmbeddingService()
    return _service


def get_embedding(text: str) -> list[float]:
    """Embed a single text. Used by retriever at query time."""
    return _get_service().get_embedding(text)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts in one pass. Used by chroma_loader at ingest time."""
    return _get_service().get_embeddings_batch(texts)
