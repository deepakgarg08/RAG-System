"""
embeddings.py — Text-to-vector embedding using OpenAI text-embedding-3-small.
Used both at ingest time (embed chunks) and query time (embed user question).
Returns 1536-dimensional float vectors. Swap client to AzureOpenAI for production.
"""
import logging

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# DEMO MODE: OpenAI text-embedding-3-small
#   Fast setup, great quality, pay-per-use
# PRODUCTION SWAP → Azure OpenAI (same model, different client):
#   FROM: client = OpenAI(api_key=config.OPENAI_API_KEY)
#   TO:   client = AzureOpenAI(
#             api_key=config.AZURE_OPENAI_API_KEY,
#             azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
#             api_version=config.AZURE_OPENAI_API_VERSION
#         )
#   Model name stays identical: "text-embedding-3-small"
#   Why Azure OpenAI for production: data never leaves Microsoft tenant,
#   required for legal document compliance at Riverty
# ============================================================

_EMBEDDING_MODEL = "text-embedding-3-small"
_BATCH_SIZE = 20


class EmbeddingService:
    """Service for converting text to embedding vectors via OpenAI API."""

    def __init__(self) -> None:
        """Initialise OpenAI client from config settings."""
        self._client = OpenAI(api_key=settings.openai_api_key)

    def get_embedding(self, text: str) -> list[float]:
        """Convert a text string to a 1536-dimensional embedding vector.

        Args:
            text: Text to embed. Newlines replaced for embedding quality.

        Returns:
            List of 1536 floats representing the embedding vector.

        Raises:
            Exception: Re-raises any OpenAI API error for the caller to handle.
        """
        clean_text = text.replace("\n", " ")
        try:
            response = self._client.embeddings.create(
                input=clean_text, model=_EMBEDDING_MODEL
            )
            vector = response.data[0].embedding
            logger.debug(
                "EmbeddingService.get_embedding: %d chars → %d-dim vector",
                len(text),
                len(vector),
            )
            return vector
        except Exception:
            logger.error(
                "EmbeddingService.get_embedding: failed for input of %d chars",
                len(text),
                exc_info=True,
            )
            raise

    def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in batches to stay within API limits.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors, one per input text, in input order.
        """
        results: list[list[float]] = []
        for batch_start in range(0, len(texts), _BATCH_SIZE):
            batch = texts[batch_start : batch_start + _BATCH_SIZE]
            clean_batch = [t.replace("\n", " ") for t in batch]
            response = self._client.embeddings.create(
                input=clean_batch, model=_EMBEDDING_MODEL
            )
            batch_vectors = [
                item.embedding
                for item in sorted(response.data, key=lambda x: x.index)
            ]
            results.extend(batch_vectors)
            logger.debug(
                "EmbeddingService.get_embeddings_batch: processed %d / %d texts",
                min(batch_start + _BATCH_SIZE, len(texts)),
                len(texts),
            )
        logger.info(
            "EmbeddingService.get_embeddings_batch: total processed %d texts",
            len(results),
        )
        return results


# ---------------------------------------------------------------------------
# Module-level helpers — kept for backward compatibility with chroma_loader.py
# ---------------------------------------------------------------------------

_service: EmbeddingService | None = None


def _get_service() -> EmbeddingService:
    """Return the shared EmbeddingService singleton."""
    global _service
    if _service is None:
        _service = EmbeddingService()
    return _service


def get_embedding(text: str) -> list[float]:
    """Module-level wrapper around EmbeddingService.get_embedding.

    Args:
        text: Text to embed.

    Returns:
        List of 1536 floats.
    """
    return _get_service().get_embedding(text)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Module-level wrapper around EmbeddingService.get_embeddings_batch.

    Args:
        texts: List of texts to embed.

    Returns:
        List of embedding vectors.
    """
    return _get_service().get_embeddings_batch(texts)
