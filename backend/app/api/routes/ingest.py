"""
ingest.py — POST /api/ingest route handler.
Accepts a multipart file upload, delegates to the ETL pipeline, and returns
{filename, chunks, status}. Contains no pipeline logic itself.
"""
import logging
import time

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.etl.compliance_storage import store_contract_in_api
from app.etl.pipeline import IngestionPipeline, ModelMismatchError
from app.models import IngestResponse
from app.storage.local_storage import LocalStorage

logger = logging.getLogger(__name__)

router = APIRouter()

# Validated against EXTRACTOR_REGISTRY in pipeline.py
_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(file: UploadFile = File(...)) -> IngestResponse:
    """Accept a contract file upload and run it through the ETL pipeline.

    Validates file type, persists the file to local storage, then runs the
    full extract → clean → chunk → load pipeline.  Returns chunk count and
    status so the frontend can confirm successful ingestion.

    Args:
        file: Multipart upload. Supported types: .pdf, .jpg, .jpeg, .png.

    Returns:
        IngestResponse with filename, file_type, language, chunks_created,
        status ("success" or "failed"), and optional error message.

    Raises:
        HTTPException 400: If the file extension is not supported.
    """
    filename = file.filename or "upload"
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if extension not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{extension}'. "
                f"Accepted types: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
            ),
        )

    file_bytes = await file.read()
    file_size = len(file_bytes)
    logger.info("ingest_document: received '%s' (%d bytes)", filename, file_size)

    start = time.perf_counter()

    # --- Persist file ---
    storage = LocalStorage()
    saved_path = storage.save(file_bytes, filename)
    logger.info("ingest_document: saved to '%s'", saved_path)

    # --- Compliance archival (fire-and-forget) ---
    # Sends a copy to the external compliance storage API if configured.
    # Failure is logged but NEVER blocks ingestion.
    store_contract_in_api(filename, file_bytes)

    # --- Run ETL pipeline ---
    # ModelMismatchError is raised at construction time if the registry was
    # built with a different embedding model. Return 409 so the client knows
    # the database must be cleared and rebuilt before ingestion can continue.
    try:
        pipeline = IngestionPipeline()
    except ModelMismatchError as exc:
        logger.error("ingest_document: model mismatch — %s", exc)
        raise HTTPException(status_code=409, detail=str(exc))

    result = pipeline.ingest(saved_path)

    elapsed = time.perf_counter() - start
    logger.info(
        "ingest_document: '%s' → status=%s, chunks=%d, elapsed=%.2fs",
        filename,
        result["status"],
        result.get("chunks_created", 0),
        elapsed,
    )

    if result["status"] == "skipped":
        logger.info("ingest_document: '%s' already ingested, returning 200 skipped", filename)

    return IngestResponse(
        filename=result["filename"],
        file_type=result["file_type"],
        language=result["language"],
        chunks_created=result["chunks_created"],
        status=result["status"],
        error=result.get("error"),
        reason=result.get("reason"),
    )
