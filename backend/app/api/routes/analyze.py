"""
analyze.py — POST /api/analyze route handler.

Supports two temporary-document analysis modes:

  single  (MODE 1) — Analyse an uploaded document directly without any DB access.
                     The document text is sent straight to the LLM. Nothing is
                     stored in the vector database.

  compare (MODE 2) — Use the uploaded document to query the vector DB for similar
                     stored contracts, then compare them via the LLM. The uploaded
                     document is NEVER written to ChromaDB.

For compliance checking (a MODE 1 variant), use POST /api/compliance instead.

Design: temporary documents are extracted in-memory via a temp file and discarded
immediately after the response is streamed. The persistent ingestion pipeline
(POST /api/ingest) is completely unaffected.
"""
import logging
import os
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.etl.extractors.pdf_extractor import PDFExtractor
from app.etl.extractors.ocr_extractor import OCRExtractor
from app.etl.transformers.cleaner import TextCleaner
from app.rag.document_analyzer import analyze_single_document, compare_with_database

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

_EXTRACTOR_MAP = {
    ".pdf": PDFExtractor,
    ".jpg": OCRExtractor,
    ".jpeg": OCRExtractor,
    ".png": OCRExtractor,
}

_VALID_MODES = {"single", "compare"}


def _extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """Extract and clean text from in-memory file bytes.

    Writes to a temporary file (required by extractor interface), extracts
    text, then immediately deletes the temp file. The uploaded contract is
    never persisted to the uploads/ directory.

    Args:
        file_bytes: Raw file bytes.
        filename: Original filename — used only to determine the extension.

    Returns:
        Cleaned, concatenated text from all pages.

    Raises:
        ValueError: If the file extension is not supported.
    """
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    extractor_cls = _EXTRACTOR_MAP.get(extension)
    if not extractor_cls:
        raise ValueError(f"Unsupported file type: '{extension}'")

    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        pages = extractor_cls().extract(tmp_path)
    finally:
        os.unlink(tmp_path)  # always discard — temporary document must not persist

    cleaner = TextCleaner()
    return " ".join(cleaner.clean(p["text"]) for p in pages if p.get("text"))


@router.post("/analyze")
async def analyze_document(
    file: UploadFile = File(...),
    question: str = Form(...),
    mode: str = Form(default="single"),
) -> StreamingResponse:
    """Analyse an uploaded contract without storing it in the vector database.

    Supports two modes:
      single  — Q&A on the uploaded document using only its own text (no DB).
      compare — Compare the uploaded document against contracts in the database.

    The uploaded file is extracted in-memory and discarded after the response.
    It is NEVER indexed into ChromaDB.

    Args:
        file:     The contract file. Accepted: .pdf, .jpg, .jpeg, .png.
        question: The question to ask about the document.
        mode:     "single" (default) or "compare".

    Returns:
        StreamingResponse (text/event-stream). Tokens stream progressively;
        "[DONE]" marks end of stream.

    Raises:
        HTTPException 400: Unsupported file type or invalid mode.
        HTTPException 422: Text extraction failed or document is empty.
    """
    filename = file.filename or "upload"
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if extension not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{extension}'. "
                f"Accepted: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
            ),
        )

    if mode not in _VALID_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode '{mode}'. Choose: {', '.join(sorted(_VALID_MODES))}",
        )

    file_bytes = await file.read()

    try:
        document_text = _extract_text_from_bytes(file_bytes, filename)
    except Exception as exc:
        logger.error("analyze_document: extraction failed for '%s' — %s", filename, exc)
        raise HTTPException(status_code=422, detail=f"Text extraction failed: {exc}")

    if not document_text.strip():
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted from the document.",
        )

    logger.info(
        "analyze_document: file='%s', mode='%s', chars=%d",
        filename,
        mode,
        len(document_text),
    )

    if mode == "compare":
        token_stream = compare_with_database(document_text, question)
    else:
        token_stream = analyze_single_document(document_text, question)

    async def event_generator():
        async for token in token_stream:
            if token == "[DONE]":
                yield "data: [DONE]\n\n"
            else:
                yield f"data: {token}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
