"""
local_storage.py — File storage: local filesystem (demo) or Azure Blob Storage (production).
Saves and retrieves uploaded contract files.
Set APP_ENV=production in .env to switch to Azure Blob Storage automatically.
See storage/README.md for the full migration guide.
"""
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# DEMO MODE: Local filesystem — instant setup, no config needed
# PRODUCTION SWAP → Azure Blob Storage (AWS: S3):
#   Set APP_ENV=production in .env — storage switches automatically.
#   Azure Blob adds versioning, legal hold, immutability policies,
#   and geo-redundant storage — all required for legal document compliance.
#   See .claude/skills/swap-to-azure.md for step-by-step migration
# ============================================================


class LocalStorage:
    """Stores and retrieves uploaded contract files.

    Branches automatically on APP_ENV:
      - demo/development: local filesystem (UPLOAD_DIR from config)
      - production:       Azure Blob Storage (versioning, legal hold, GRS)
    """

    def __init__(self) -> None:
        """Initialise the storage backend for the active environment."""
        if settings.app_env == "production":
            # ============================================================
            # PRODUCTION: Azure Blob Storage
            # AWS equivalent: Amazon S3
            # Provides: versioning, legal hold, immutability policies,
            # 7-year retention (HGB §257), geo-redundant backup (GRS)
            # Switch: set APP_ENV=production in .env + AZURE_STORAGE_CONNECTION_STRING
            # ============================================================
            from app.storage.azure_blob import AzureBlobStorage  # local import

            self._backend = AzureBlobStorage()
            self._mode = "azure"
            logger.info("LocalStorage: mode=azure (Azure Blob Storage)")
        else:
            # ============================================================
            # DEMO: Local filesystem — zero config, files in UPLOAD_DIR
            # Switch: set APP_ENV=production in .env
            # ============================================================
            self._upload_dir = Path(settings.upload_dir)
            self._upload_dir.mkdir(parents=True, exist_ok=True)
            self._mode = "local"
            logger.info("LocalStorage: mode=local, upload_dir='%s'", self._upload_dir)

    def save(self, file_bytes: bytes, filename: str) -> str:
        """Persist raw file bytes to the active storage backend.

        Args:
            file_bytes: Raw bytes of the uploaded file.
            filename: Original filename to save as.

        Returns:
            Path or blob URL identifying the saved file.
        """
        if self._mode == "azure":
            return self._backend.save(file_bytes, filename)

        dest = self._upload_dir / filename
        dest.write_bytes(file_bytes)
        logger.info("LocalStorage.save: saved %d bytes to '%s'", len(file_bytes), dest)
        return str(dest.resolve())

    def get_path(self, filename: str) -> str:
        """Return the full path (or URL) to a previously saved file.

        Args:
            filename: Name of the file to locate.

        Returns:
            Absolute path string (local) or blob URL (Azure).

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        if self._mode == "azure":
            return self._backend.get_path(filename)

        path = self._upload_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"LocalStorage.get_path: '{filename}' not found in '{self._upload_dir}'"
            )
        return str(path.resolve())
