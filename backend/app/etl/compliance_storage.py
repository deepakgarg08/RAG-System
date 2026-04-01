"""
compliance_storage.py — Fail-safe external compliance API integration.

After a contract is saved locally, `store_contract_in_api` sends an additional
copy to an external REST API for legally compliant archival (required by Riverty's
legal framework for document retention).

Design principles:
  - Fire-and-forget: failures are logged but NEVER block the ingestion pipeline.
  - No retry logic — the external API is considered best-effort at call time.
  - Skipped silently when COMPLIANCE_API_URL is not configured (demo / local dev).
"""
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# DEMO MODE: COMPLIANCE_API_URL is empty → step is skipped silently
# PRODUCTION SWAP → Real external contract storage REST API:
#   Set COMPLIANCE_API_URL in .env to activate this step.
#   The API receives the raw file bytes via multipart POST.
#   Contract: POST {url} with multipart field "file" = (filename, bytes)
#   Expected response: 2xx on success, any non-2xx is logged as a warning.
# ============================================================


def store_contract_in_api(filename: str, file_bytes: bytes) -> bool:
    """Send a contract file to the external compliance storage API.

    Uploads the file as a multipart POST request. Any failure — timeout,
    HTTP error, network issue — is caught, logged, and silently ignored
    so the ingestion pipeline continues normally.

    Args:
        filename: Original filename including extension (e.g. "contract_nda.pdf").
        file_bytes: Raw bytes of the file to upload.

    Returns:
        True if the API call succeeded (2xx response).
        False if the URL is not configured or the call failed.
    """
    if not settings.compliance_api_url:
        logger.debug("compliance_storage: COMPLIANCE_API_URL not set — skipping archival step")
        return False

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                settings.compliance_api_url,
                files={"file": (filename, file_bytes, "application/octet-stream")},
            )
            response.raise_for_status()

        logger.info(
            "compliance_storage: '%s' archived in compliance API (HTTP %d)",
            filename,
            response.status_code,
        )
        return True

    except httpx.TimeoutException:
        logger.warning(
            "compliance_storage: timeout uploading '%s' — ingestion continues unaffected",
            filename,
        )
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "compliance_storage: API returned HTTP %d for '%s' — ingestion continues unaffected",
            exc.response.status_code,
            filename,
        )
    except Exception as exc:
        logger.warning(
            "compliance_storage: unexpected error archiving '%s': %s — ingestion continues unaffected",
            filename,
            exc,
        )

    return False
