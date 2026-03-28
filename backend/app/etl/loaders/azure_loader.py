"""
azure_loader.py — PRODUCTION vector store loader using Azure AI Search.
Stores embedded chunks in an Azure AI Search index with hybrid search support.
Requires AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY, AZURE_SEARCH_INDEX_NAME in config.
See .claude/skills/swap-to-azure.md for the full migration steps.
"""
# ============================================================
# PRODUCTION STUB — Azure AI Search
#
# This file is a documented stub. It will not run until you complete
# the 5-step migration below. The ChromaLoader is active by default.
#
# Migration steps (see also .claude/skills/swap-to-azure.md):
#
# Step 1 — Install the SDK:
#   pip install azure-search-documents==11.6.0b4
#   (Uncomment the import block below)
#
# Step 2 — Provision Azure resources:
#   Create Azure AI Search resource in Azure Portal (West Europe region)
#   Create index 'riverty-contracts' with fields: id, content, embedding, metadata_json
#   Copy endpoint + admin key to .env
#
# Step 3 — Swap the loader in pipeline.py:
#   FROM: loader = ChromaLoader()
#   TO:   loader = AzureSearchLoader()
#
# Step 4 — Run tests:
#   pytest backend/tests/ -v
#   (Tests mock Azure SDK — no live Azure needed for tests)
#
# Step 5 — Update docs:
#   Fill in actual resource names in docs/azure-services.md
#   Add ADR using the write-adr skill
# ============================================================

# Uncomment when ready to migrate:
# from azure.search.documents import SearchClient
# from azure.search.documents.models import VectorizedQuery
# from azure.core.credentials import AzureKeyCredential

import logging

from app.config import settings
from app.etl.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class AzureSearchLoader(BaseLoader):
    """PRODUCTION loader that stores document chunks in Azure AI Search.

    This is a documented stub. All methods raise NotImplementedError with
    instructions explaining what the production implementation would do.
    """

    def __init__(self) -> None:
        """Initialise Azure AI Search client.

        Production implementation would:
            client = SearchClient(
                endpoint=settings.azure_search_endpoint,
                index_name=settings.azure_search_index_name,
                credential=AzureKeyCredential(settings.azure_search_key),
            )
        """
        raise NotImplementedError(
            "AzureSearchLoader is a production stub. "
            "Follow the 5-step migration in .claude/skills/swap-to-azure.md, "
            "then uncomment the azure-search-documents import and implement this class."
        )

    def load(self, chunks: list[dict]) -> int:
        """Upload chunks to Azure AI Search index.

        Production implementation would:
        - Build documents with fields: id, content, embedding (vector), metadata_json
        - Call search_client.upload_documents(documents=batch)
        - Use batch size of 100 for efficiency
        - Return total documents uploaded

        Args:
            chunks: List of chunk dicts with 'text' and 'metadata' keys.

        Returns:
            Number of chunks successfully stored.
        """
        raise NotImplementedError(
            "AzureSearchLoader.load() is not implemented. "
            "See .claude/skills/swap-to-azure.md — Step 3: For Azure AI Search swap."
        )

    def get_document_count(self) -> int:
        """Return total document count from Azure AI Search index.

        Production implementation would:
            result = search_client.search(search_text="*", select=["id"], top=0)
            return result.get_count()
        """
        raise NotImplementedError(
            "AzureSearchLoader.get_document_count() is not implemented. "
            "See .claude/skills/swap-to-azure.md for migration steps."
        )
