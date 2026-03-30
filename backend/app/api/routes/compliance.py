"""
compliance.py — POST /api/compliance route handler.

Accepts an uploaded contract and evaluates it against a set of compliance
guidelines. Returns a structured JSON result (compliant / violations / explanation).

This is a MODE 1 variant: the document is processed entirely in-memory and
is NEVER stored in the vector database or the uploads directory.

Default guidelines enforce Riverty's standard contract requirements:
  1. Termination clause with notice period
  2. GDPR / data protection clause
  3. Governing law and jurisdiction
  4. Liability limitations
  5. Clear identification of both parties

Custom guidelines can be submitted as a form field to override the defaults.
"""
import logging
import os
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from typing import Optional

from app.etl.extractors.pdf_extractor import PDFExtractor
from app.etl.extractors.ocr_extractor import OCRExtractor
from app.etl.transformers.cleaner import TextCleaner
from app.models import ComplianceResult
from app.rag.document_analyzer import check_compliance

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

_EXTRACTOR_MAP = {
    ".pdf": PDFExtractor,
    ".jpg": OCRExtractor,
    ".jpeg": OCRExtractor,
    ".png": OCRExtractor,
}

# Default guidelines applied when none are provided by the caller.
# These reflect Riverty's standard contract review checklist.
_DEFAULT_GUIDELINES = """\
1. The contract must include a termination clause specifying the notice period.
2. The contract must include a data protection / GDPR compliance clause \
(or DSGVO clause for German contracts).
3. The contract must specify the governing law and jurisdiction.
4. The contract must include liability limitations or indemnification terms.
5. The contract must clearly identify both contracting parties by legal name.
"""


def _extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """Extract and clean text from in-memory file bytes using a temp file.

    The temp file is deleted immediately after extraction. The uploaded
    document is never persisted to the uploads/ directory.

    Args:
        file_bytes: Raw file bytes.
        filename: Original filename — used only to determine the extension.

    Returns:
        Cleaned, concatenated page text.

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
        os.unlink(tmp_path)  # always discard

    cleaner = TextCleaner()
    return " ".join(cleaner.clean(p["text"]) for p in pages if p.get("text"))


@router.post("/compliance", response_model=ComplianceResult)
async def check_document_compliance(
    file: UploadFile = File(...),
    guidelines: Optional[str] = Form(default=None),
) -> ComplianceResult:
    """Evaluate an uploaded contract against compliance guidelines (MODE 1).

    Extracts the document text in-memory, sends it to the LLM together with
    the guidelines, and returns a structured compliance result.

    The uploaded file is NEVER stored in the uploads directory or indexed
    into the vector database.

    Args:
        file:       The contract file. Accepted: .pdf, .jpg, .jpeg, .png.
        guidelines: Optional plain-text compliance guidelines. When omitted,
                    Riverty's default checklist is used (termination, GDPR,
                    governing law, liability, party identification).

    Returns:
        ComplianceResult with:
          compliant   — True if no violations were found
          violations  — List of specific guideline failures
          explanation — 2-4 sentence plain-language summary

    Raises:
        HTTPException 400: Unsupported file type.
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

    file_bytes = await file.read()

    try:
        document_text = _extract_text_from_bytes(file_bytes, filename)
    except Exception as exc:
        logger.error(
            "check_document_compliance: extraction failed for '%s' — %s", filename, exc
        )
        raise HTTPException(status_code=422, detail=f"Text extraction failed: {exc}")

    if not document_text.strip():
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted from the document.",
        )

    active_guidelines = guidelines or _DEFAULT_GUIDELINES

    logger.info(
        "check_document_compliance: file='%s', doc_chars=%d, guidelines_chars=%d",
        filename,
        len(document_text),
        len(active_guidelines),
    )

    result = await check_compliance(document_text, active_guidelines)

    return ComplianceResult(
        compliant=result["compliant"],
        violations=result["violations"],
        explanation=result["explanation"],
    )
