"""
files.py — GET /api/files/{filename} route handler.
Serves uploaded contract files from the local uploads/ directory.
Enables the frontend to open source PDFs/images directly in the browser,
optionally jumping to a specific page via the #page=N URL fragment.
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Map file extensions to MIME types for correct browser handling
_MIME_TYPES: dict[str, str] = {
    ".pdf":  "application/pdf",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
}


@router.get("/files/{filename}")
async def serve_file(filename: str) -> FileResponse:
    """Serve an uploaded contract file for in-browser viewing.

    The browser handles page navigation for PDFs via the #page=N URL fragment
    appended by the frontend — no server-side logic required for page targeting.

    Args:
        filename: The base filename (e.g. 'ecomdata_converted.pdf').
                  Path traversal is blocked by resolving against uploads/.

    Returns:
        FileResponse with the correct Content-Type for browser rendering.

    Raises:
        HTTPException 404: File not found in uploads directory.
        HTTPException 400: File extension not supported for browser viewing.
    """
    upload_root = Path(settings.upload_dir).resolve()
    file_path = (upload_root / filename).resolve()

    # Block path traversal — resolved path must stay inside uploads/
    if not str(file_path).startswith(str(upload_root)):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")

    extension = file_path.suffix.lower()
    media_type = _MIME_TYPES.get(extension)
    if not media_type:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{extension}'.")

    logger.info("serve_file: serving '%s' (%s)", filename, media_type)
    return FileResponse(path=file_path, media_type=media_type, filename=filename)
