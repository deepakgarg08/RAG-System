"""
azure_blob.py — PRODUCTION file storage using Azure Blob Storage.
Saves and retrieves contract files from an Azure Blob container with versioning
and legal hold support. Requires AZURE_STORAGE_CONNECTION_STRING in config.
See .claude/skills/swap-to-azure.md for migration steps.
"""

# ============================================================
# DEMO MODE: Not active — this is a production-only stub.
# PRODUCTION SWAP → Azure Blob Storage (AWS: S3):
#   1. pip install azure-storage-blob
#   2. Set AZURE_STORAGE_CONNECTION_STRING and AZURE_STORAGE_CONTAINER_NAME in .env
#   3. Replace LocalStorage with AzureBlobStorage in the upload route handler
#
# Migration code (uncomment when switching to production):
#
#   from azure.storage.blob import BlobServiceClient
#   from app.config import settings
#
#   class AzureBlobStorage:
#       def __init__(self) -> None:
#           self._client = BlobServiceClient.from_connection_string(
#               settings.azure_storage_connection_string
#           )
#           self._container = settings.azure_storage_container_name
#
#       def save(self, file_bytes: bytes, filename: str) -> str:
#           blob = self._client.get_blob_client(
#               container=self._container, blob=filename
#           )
#           blob.upload_blob(file_bytes, overwrite=True)
#           return blob.url
#
#       def get_path(self, filename: str) -> str:
#           blob = self._client.get_blob_client(
#               container=self._container, blob=filename
#           )
#           return blob.url
#
# Why Azure Blob for production:
#   - Immutability policies prevent tampering with legal documents
#   - Versioning + legal hold for audit trail compliance
#   - Geo-redundant storage (GRS) for disaster recovery
#   - Private endpoint support — traffic stays inside Riverty VNet
# ============================================================


class AzureBlobStorage:
    """PRODUCTION stub — Azure Blob Storage for contract file persistence.

    Not implemented. See migration instructions in the swap comment above.
    """

    def save(self, file_bytes: bytes, filename: str) -> str:
        """Save file bytes to Azure Blob Storage.

        Args:
            file_bytes: Raw bytes of the uploaded file.
            filename: Blob name to store the file as.

        Raises:
            NotImplementedError: Always — migrate using .claude/skills/swap-to-azure.md.
        """
        raise NotImplementedError(
            "AzureBlobStorage is not yet configured. "
            "Follow .claude/skills/swap-to-azure.md to enable Azure Blob Storage."
        )

    def get_path(self, filename: str) -> str:
        """Return the Azure Blob URL for a stored file.

        Args:
            filename: Blob name to locate.

        Raises:
            NotImplementedError: Always — migrate using .claude/skills/swap-to-azure.md.
        """
        raise NotImplementedError(
            "AzureBlobStorage is not yet configured. "
            "Follow .claude/skills/swap-to-azure.md to enable Azure Blob Storage."
        )
