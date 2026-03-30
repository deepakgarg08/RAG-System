"""
ingestion_registry.py — Tracks which files have been ingested into ChromaDB.

Prevents duplicate ingestion and detects embedding model mismatches that would
corrupt the vector store with incompatible vectors.

Registry JSON structure:
{
  "embedding_model": "BAAI/bge-m3",
  "files": [
    {
      "filename": "contract.pdf",
      "checksum": "md5:a3f8c2d1...",
      "embedding_model": "BAAI/bge-m3",
      "ingestion_timestamp": "2026-03-28T14:22:01Z",
      "chunk_count": 81,
      "status": "success"
    }
  ]
}

Model mismatch behaviour:
  If the current embedding model differs from registry["embedding_model"],
  ingestion is BLOCKED entirely with a clear error message.
  The user must clear the ChromaDB collection and call registry.reset() first.
  This prevents silently mixing incompatible vectors in the same collection.
"""
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ModelMismatchError(Exception):
    """Raised when the current embedding model does not match the registry.

    The ChromaDB collection was built with a different model — mixing vectors
    from different models produces silently wrong retrieval results.

    Resolution: clear the ChromaDB collection, then call registry.reset().
    """


class IngestionRegistry:
    """Tracks ingested files by checksum to prevent duplicates and model drift.

    Thread-safety note: registry reads/writes are synchronous and single-process.
    For concurrent ingestion workers, wrap with a file lock (not needed for demo).
    """

    _EMPTY: dict = {"embedding_model": "", "files": []}

    def __init__(self, registry_path: str, current_embedding_model: str) -> None:
        """Load or create the registry file.

        If the registry does not exist, it is created with current_embedding_model.
        If it exists but records a different embedding model, ModelMismatchError
        is raised immediately — no ingestion should proceed until resolved.

        Args:
            registry_path: Absolute or relative path to the JSON registry file.
            current_embedding_model: Name of the embedding model currently in use,
                e.g. "BAAI/bge-m3".

        Raises:
            ModelMismatchError: If the registry was built with a different model.
        """
        self._path = registry_path
        self._current_model = current_embedding_model
        self._data = self._load()

        if not self._data["embedding_model"]:
            # New registry — initialise with current model
            self._data["embedding_model"] = current_embedding_model
            self._save()
            logger.info(
                "IngestionRegistry: created new registry at '%s' (model=%s)",
                self._path,
                current_embedding_model,
            )
        elif self._data["embedding_model"] != current_embedding_model:
            raise ModelMismatchError(
                f"Embedding model mismatch.\n"
                f"  Registry model : {self._data['embedding_model']}\n"
                f"  Current model  : {current_embedding_model}\n"
                f"Mixing vectors from different models corrupts retrieval.\n"
                f"To resolve: clear the ChromaDB collection and call "
                f"registry.reset() to rebuild with the new model."
            )
        else:
            logger.debug(
                "IngestionRegistry: loaded %d entries from '%s'",
                len(self._data["files"]),
                self._path,
            )

    def is_ingested(self, checksum: str) -> bool:
        """Return True if a file with this checksum was successfully ingested.

        Args:
            checksum: MD5 checksum string, e.g. "md5:a3f8c2d1...".

        Returns:
            True only if an entry exists with status='success'.
        """
        entry = self.get_entry(checksum)
        return entry is not None and entry.get("status") == "success"

    def add_entry(
        self,
        filename: str,
        checksum: str,
        chunk_count: int,
        status: str,
    ) -> None:
        """Add or update a file entry and immediately persist to disk.

        If an entry with the same checksum already exists it is replaced.
        The per-entry embedding_model is always set to the current model.

        Args:
            filename: Original filename, e.g. "contract.pdf".
            checksum: MD5 checksum string, e.g. "md5:a3f8c2d1...".
            chunk_count: Number of chunks stored in ChromaDB.
            status: One of "success", "failed", or "partial".
        """
        entry = {
            "filename": filename,
            "checksum": checksum,
            "embedding_model": self._current_model,
            "ingestion_timestamp": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "chunk_count": chunk_count,
            "status": status,
        }

        # Replace existing entry for this checksum if present
        self._data["files"] = [
            f for f in self._data["files"] if f.get("checksum") != checksum
        ]
        self._data["files"].append(entry)
        self._save()
        logger.info(
            "IngestionRegistry.add_entry: %s — status=%s, chunks=%d",
            filename,
            status,
            chunk_count,
        )

    def get_entry(self, checksum: str) -> dict | None:
        """Return the registry entry for this checksum, or None if not found.

        Args:
            checksum: MD5 checksum string to look up.

        Returns:
            The matching entry dict, or None.
        """
        for entry in self._data["files"]:
            if entry.get("checksum") == checksum:
                return entry
        return None

    def reset(self) -> None:
        """Clear all file entries and update the registry model to current.

        Use this after clearing the ChromaDB collection when switching embedding
        models. All previously ingested files must be re-ingested afterward.
        """
        self._data = {
            "embedding_model": self._current_model,
            "files": [],
        }
        self._save()
        logger.warning(
            "IngestionRegistry: registry reset (model=%s). "
            "All files must be re-ingested.",
            self._current_model,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        """Load registry from disk. Returns empty structure if file not found.

        Returns:
            Parsed registry dict with 'embedding_model' and 'files' keys.
        """
        if not os.path.exists(self._path):
            return {"embedding_model": "", "files": []}
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "IngestionRegistry: failed to load '%s' (%s) — starting fresh",
                self._path,
                exc,
            )
            return {"embedding_model": "", "files": []}

    def _save(self) -> None:
        """Write registry to disk as formatted JSON (indent=2)."""
        os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)
        logger.debug("IngestionRegistry: saved to '%s'", self._path)
