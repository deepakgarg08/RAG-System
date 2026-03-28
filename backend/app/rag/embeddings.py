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
# DEMO MODE: OpenAI API — direct API key, simple setup
# PRODUCTION SWAP → Azure OpenAI (AWS: Bedrock):
#   Change client initialisation below:
#   FROM: OpenAI(api_key=...)
#   TO:   AzureOpenAI(api_key=..., azure_endpoint=..., api_version="2024-02-01")
#   Model name stays the same: "text-embedding-3-small"
# ============================================================

_EMBEDDING_MODEL = "text-embedding-3-small"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Return the OpenAI client, initialising it on first call."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def get_embedding(text: str) -> list[float]:
    """Convert a text string to a 1536-dimensional embedding vector.

    Args:
        text: Text to embed. Will be truncated to model's token limit if needed.

    Returns:
        List of 1536 floats representing the embedding vector.

    Raises:
        Exception: Re-raises any OpenAI API error for the caller to handle.
    """
    client = _get_client()
    # Replace newlines — OpenAI recommends this for embedding quality
    clean_text = text.replace("\n", " ")
    response = client.embeddings.create(input=clean_text, model=_EMBEDDING_MODEL)
    vector = response.data[0].embedding
    logger.debug("get_embedding: %d chars → %d-dim vector", len(text), len(vector))
    return vector


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Batch embed multiple texts in a single API call.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of embedding vectors, one per input text.
    """
    client = _get_client()
    clean_texts = [t.replace("\n", " ") for t in texts]
    response = client.embeddings.create(input=clean_texts, model=_EMBEDDING_MODEL)
    # API returns results sorted by index
    vectors = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
    logger.info("get_embeddings: %d texts embedded", len(vectors))
    return vectors
