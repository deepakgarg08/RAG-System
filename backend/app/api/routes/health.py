"""
health.py — GET /health route handler.
Returns system status, current document count from the vector store,
and the active mode (demo or production). Used for monitoring and smoke tests.
"""
import logging

from fastapi import APIRouter

from app.config import settings
from app.models import HealthResponse
from app.rag.retriever import ContractRetriever

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return system health status, vector store document count, and active mode.

    Mode is "demo" when AZURE_SEARCH_ENDPOINT is empty (ChromaDB stack),
    or "production" when it is configured (Azure AI Search stack).
    """
    retriever = ContractRetriever()
    stats = retriever.get_collection_stats()
    mode = "production" if settings.azure_search_endpoint else "demo"

    logger.info("health_check: mode=%s, document_count=%d", mode, stats["total_documents"])

    return HealthResponse(
        status="ok",
        document_count=stats["total_documents"],
        mode=mode,
        app_env=settings.app_env,
    )
