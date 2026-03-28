"""
local_storage.py — DEMO file storage using the local filesystem.
Saves uploaded contract files to the UPLOAD_DIR path from config.
Suitable for demo and development — no cloud credentials required.
See storage/README.md for the production swap to Azure Blob Storage.
"""
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# DEMO MODE: Local filesystem — instant setup, no config needed
# PRODUCTION SWAP → Azure Blob Storage (AWS: S3):
#   Replace LocalStorage with AzureBlobStorage in the upload route
#   Azure Blob adds versioning, legal hold, immutability policies,
#   and geo-redundant storage — all required for legal document compliance
#   See .claude/skills/swap-to-azure.md for step-by-step migration
# ============================================================


class LocalStorage:
    """Stores and retrieves uploaded contract files on the local filesystem."""

    def __init__(self) -> None:
        """Ensure the upload directory exists."""
        self._upload_dir = Path(settings.upload_dir)
        self._upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info("LocalStorage: upload directory is '%s'", self._upload_dir)

    def save(self, file_bytes: bytes, filename: str) -> str:
        """Persist raw file bytes to the upload directory.

        Args:
            file_bytes: Raw bytes of the uploaded file.
            filename: Original filename to save as.

        Returns:
            Absolute path to the saved file.
        """
        dest = self._upload_dir / filename
        dest.write_bytes(file_bytes)
        logger.info("LocalStorage.save: saved %d bytes to '%s'", len(file_bytes), dest)
        return str(dest.resolve())

    def get_path(self, filename: str) -> str:
        """Return the full path to a previously saved file.

        Args:
            filename: Name of the file to locate.

        Returns:
            Absolute path string.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        path = self._upload_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"LocalStorage.get_path: '{filename}' not found in '{self._upload_dir}'"
            )
        return str(path.resolve())
