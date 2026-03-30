"""
chunker.py — Content-aware text chunking with page tracking and metadata attachment.

Detects document type (Q&A, legal contract, narrative) from the extracted text
and applies the appropriate chunking strategy:

  - QAChunker:       Q&A / FAQ documents → one chunk per Q+A pair
  - LegalChunker:    Contracts / agreements → one chunk per section/article
  - NarrativeChunker: Everything else → RecursiveCharacterTextSplitter per page

Every chunk carries full source attribution metadata including page_number,
chunk_index, total_chunks, and char_count for precise retrieval pinpointing.
"""
import logging
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for content type detection and chunking
# ---------------------------------------------------------------------------

# Q&A signal: lines starting with "Q:" / "Q." / "Q :"
_QA_LINE_RE = re.compile(r"^\s*Q\s*[:.]\s*", re.IGNORECASE | re.MULTILINE)

# Legal section header: "Section 1", "ARTICLE 2.", "§ 3", "Clause 4"
# Also covers German: "Abschnitt 1", "Artikel 2", "§ 3 Vertragsgegenstand"
_LEGAL_HEADER_RE = re.compile(
    r"^(?:SECTION|Section|ARTICLE|Article|CLAUSE|Clause|§|Abschnitt|Artikel|Ziffer)\s*\d+",
    re.MULTILINE,
)

# Legal vocabulary signals — English and German
_LEGAL_KEYWORDS = [
    # English
    "whereas", "hereinafter", "termination", "indemnification",
    "confidentiality", "governing law", "force majeure",
    # German
    "hiermit", "kündigung", "haftung", "vertragspartner",
    "auftragnehmer", "auftraggeber", "gewährleistung",
    "datenschutz", "vertragslaufzeit", "gerichtsstand",
]


# ---------------------------------------------------------------------------
# Content type detector
# ---------------------------------------------------------------------------

class ContentTypeDetector:
    """Detects the type of content in a document from extracted page text.

    Checks the first ~3000 characters for structural signals before falling
    back to a vocabulary scan. No API calls — purely rule-based.
    Supports English and German legal documents.
    """

    def detect(self, pages: list[dict]) -> str:
        """Classify the document into 'qa', 'legal', or 'narrative'.

        Args:
            pages: List of {"page_number": int, "text": str} dicts from an extractor.

        Returns:
            One of: 'qa', 'legal', 'narrative'.
        """
        sample = "\n".join(p["text"] for p in pages[:3])[:3000]

        # Q&A: 3+ lines that start with "Q:" pattern
        qa_hits = len(_QA_LINE_RE.findall(sample))
        if qa_hits >= 3:
            logger.info("ContentTypeDetector: detected 'qa' (%d Q: hits)", qa_hits)
            return "qa"

        # Legal: 2+ section headers OR 3+ legal keywords
        header_hits = len(_LEGAL_HEADER_RE.findall(sample))
        keyword_hits = sum(1 for kw in _LEGAL_KEYWORDS if kw.lower() in sample.lower())
        if header_hits >= 2 or keyword_hits >= 3:
            logger.info(
                "ContentTypeDetector: detected 'legal' (headers=%d, keywords=%d)",
                header_hits,
                keyword_hits,
            )
            return "legal"

        logger.info("ContentTypeDetector: detected 'narrative'")
        return "narrative"


# ---------------------------------------------------------------------------
# DocumentChunker — selects and runs the right strategy
# ---------------------------------------------------------------------------

class DocumentChunker:
    """Splits page-tagged extracted text into chunks using content-aware strategies.

    Accepts a list of page dicts (output of any BaseExtractor) and returns
    chunk dicts with full metadata including page_number for source attribution.
    """

    def __init__(self) -> None:
        """Initialise the content type detector and the narrative splitter."""
        self._detector = ContentTypeDetector()
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.max_chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def chunk(
        self,
        pages: list[dict],
        metadata: dict,
        file_size_kb: int = 0,
        total_pages: int = 0,
        checksum: str = "",
        extraction_method: str = "",
        is_scanned: bool = False,
        embedding_model: str = "BAAI/bge-m3",
        upload_timestamp: str = "",
        uploaded_by: str = "anonymous",
    ) -> list[dict]:
        """Split page-tagged text into chunks with full source attribution metadata.

        Detects content type and delegates to the appropriate strategy:
          - 'qa'        → _chunk_qa       (one chunk per Q+A pair)
          - 'legal'     → _chunk_legal    (one chunk per section/article)
          - 'narrative' → _chunk_narrative (RecursiveCharacterTextSplitter per page)

        Args:
            pages: List of {"page_number": int, "text": str} from an extractor.
            metadata: Base metadata dict — must include source_file, file_type,
                      language. chunk_index, total_chunks, page_number added here.
            file_size_kb: File size in kilobytes.
            total_pages: Total number of pages in the source document.
            checksum: MD5 checksum of the source file, e.g. "md5:a3f8c2d1...".
            extraction_method: Extractor used, e.g. "pymupdf" or "ocr_tesseract".
            is_scanned: True if the document was processed via OCR.
            embedding_model: Name of the embedding model used, e.g. "BAAI/bge-m3".
            upload_timestamp: ISO 8601 UTC timestamp of when the file was uploaded.
            uploaded_by: Identity of the uploader. Defaults to "anonymous".

        Returns:
            List of chunk dicts, each with 'text' and 'metadata' keys.
            Returns empty list if all pages are empty.

        Note:
            contract_type (NDA / Service / Vendor) is a planned future field —
            see ContentTypeDetector for the extension point.
        """
        if not pages or not any(p.get("text", "").strip() for p in pages):
            return []

        content_type = self._detector.detect(pages)
        logger.info(
            "DocumentChunker: %s — content_type=%s",
            metadata.get("source_file", "unknown"),
            content_type,
        )

        # Build document-level metadata shared across all chunks for this file.
        # Chunk-level fields (chunk_index, total_chunks, page_number, char_count,
        # text_preview, chunking_strategy) are added per-chunk in _make_chunk().
        doc_metadata: dict = {
            # DOCUMENT group
            "source_file":       metadata.get("source_file", ""),
            "file_type":         metadata.get("file_type", ""),
            "file_size_kb":      file_size_kb,
            "total_pages":       total_pages,
            "checksum":          checksum,
            # PROCESSING group
            "language":          metadata.get("language", ""),
            "content_type":      content_type,
            "extraction_method": extraction_method,
            "is_scanned":        is_scanned,
            "embedding_model":   embedding_model,
            "ingestion_version": "1.0",
            # AUDIT group
            "upload_timestamp":  upload_timestamp,
            "uploaded_by":       uploaded_by,
        }

        if content_type == "qa":
            chunks = self._chunk_qa(pages, doc_metadata)
        elif content_type == "legal":
            chunks = self._chunk_legal(pages, doc_metadata)
        else:
            chunks = self._chunk_narrative(pages, doc_metadata)

        # Fallback: if strategy produced nothing, use narrative
        if not chunks:
            logger.warning(
                "DocumentChunker: %s strategy produced 0 chunks, falling back to narrative",
                content_type,
            )
            chunks = self._chunk_narrative(pages, doc_metadata)

        total = len(chunks)
        for chunk in chunks:
            chunk["metadata"]["total_chunks"] = total

        logger.info(
            "DocumentChunker: %s — %d chunks (%s strategy)",
            metadata.get("source_file", "unknown"),
            total,
            content_type,
        )
        return chunks

    # ------------------------------------------------------------------
    # Strategy: Q&A  — one chunk per Q+A pair
    # ------------------------------------------------------------------

    def _chunk_qa(self, pages: list[dict], base_metadata: dict) -> list[dict]:
        """Split Q&A content so every question+answer pair is one chunk.

        Scans each page for lines beginning with 'Q:' and groups each question
        with all following answer lines until the next question begins.

        Args:
            pages: Page dicts from the extractor.
            base_metadata: Metadata to attach to every chunk.

        Returns:
            List of chunk dicts, one per Q+A pair.
        """
        chunks: list[dict] = []
        chunk_index = 0

        for page_dict in pages:
            page_number = page_dict["page_number"]
            lines = page_dict["text"].split("\n")

            current_lines: list[str] = []
            current_page = page_number

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue

                is_question = bool(re.match(r"^Q\s*[:.]\s*", stripped, re.IGNORECASE))

                if is_question:
                    # Flush the previous pair as a chunk
                    if current_lines:
                        pair_text = "\n".join(current_lines)
                        chunks.append(self._make_chunk(
                            pair_text, base_metadata, chunk_index, current_page, "qa_pair"
                        ))
                        chunk_index += 1
                    current_lines = [stripped]
                    current_page = page_number
                else:
                    current_lines.append(stripped)

            # Flush the last pair on this page
            if current_lines:
                pair_text = "\n".join(current_lines)
                chunks.append(self._make_chunk(
                    pair_text, base_metadata, chunk_index, current_page, "qa_pair"
                ))
                chunk_index += 1

        return chunks

    # ------------------------------------------------------------------
    # Strategy: Legal — one chunk per section / article
    # ------------------------------------------------------------------

    def _chunk_legal(self, pages: list[dict], base_metadata: dict) -> list[dict]:
        """Split legal text at section/article/clause boundaries.

        Finds headers like 'Section 1', 'Article 2', 'CLAUSE 3', '§ 4' and
        groups all text under each header as one chunk.

        Args:
            pages: Page dicts from the extractor.
            base_metadata: Metadata to attach to every chunk.

        Returns:
            List of chunk dicts, one per section.
        """
        chunks: list[dict] = []
        chunk_index = 0

        # Track (page_number, line) pairs across all pages
        all_lines: list[tuple[int, str]] = []
        for page_dict in pages:
            for line in page_dict["text"].split("\n"):
                all_lines.append((page_dict["page_number"], line))

        current_lines: list[str] = []
        current_page: int = pages[0]["page_number"] if pages else 1

        for page_number, line in all_lines:
            is_header = bool(_LEGAL_HEADER_RE.match(line.strip()))

            if is_header and current_lines:
                section_text = "\n".join(current_lines).strip()
                if section_text:
                    chunks.append(self._make_chunk(
                        section_text, base_metadata, chunk_index, current_page,
                        "section_boundary"
                    ))
                    chunk_index += 1
                current_lines = [line]
                current_page = page_number
            else:
                current_lines.append(line)

        # Flush final section
        if current_lines:
            section_text = "\n".join(current_lines).strip()
            if section_text:
                chunks.append(self._make_chunk(
                    section_text, base_metadata, chunk_index, current_page,
                    "section_boundary"
                ))

        # If no section headers were found, split the combined text by char size
        if not chunks:
            return self._chunk_narrative(pages, base_metadata)

        return chunks

    # ------------------------------------------------------------------
    # Strategy: Narrative — RecursiveCharacterTextSplitter per page
    # ------------------------------------------------------------------

    def _chunk_narrative(self, pages: list[dict], base_metadata: dict) -> list[dict]:
        """Split narrative text using RecursiveCharacterTextSplitter.

        Processes each page independently so chunks never span page boundaries
        and every chunk has a precise page_number.

        Args:
            pages: Page dicts from the extractor.
            base_metadata: Metadata to attach to every chunk.

        Returns:
            List of chunk dicts.
        """
        chunks: list[dict] = []
        chunk_index = 0

        for page_dict in pages:
            page_number = page_dict["page_number"]
            page_text = page_dict["text"].strip()
            if not page_text:
                continue

            page_chunks = self._splitter.split_text(page_text)
            for chunk_text in page_chunks:
                if not chunk_text.strip():
                    continue
                chunks.append(self._make_chunk(
                    chunk_text, base_metadata, chunk_index, page_number,
                    "recursive_1000_200"
                ))
                chunk_index += 1

        return chunks

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _make_chunk(
        text: str,
        doc_metadata: dict,
        chunk_index: int,
        page_number: int,
        chunking_strategy: str,
    ) -> dict:
        """Build a single chunk dict with full metadata.

        Merges document-level metadata (set once in chunk()) with chunk-level
        fields that are unique to each individual chunk.

        Args:
            text: The chunk text. Full text goes in the 'text' field;
                  only the first 100 chars are stored in metadata as text_preview.
            doc_metadata: Document-level metadata built in chunk().
            chunk_index: Sequential 0-based index of this chunk within the document.
            page_number: Page in the source document where this chunk starts.
            chunking_strategy: Strategy used — "qa_pair", "section_boundary",
                               or "recursive_1000_200".

        Returns:
            Chunk dict with 'text' and 'metadata' keys.
        """
        return {
            "text": text,
            "metadata": {
                **doc_metadata,
                # CHUNK group — unique per chunk
                "chunk_index":       chunk_index,
                "total_chunks":      0,          # filled in by chunk() after all chunks are known
                "page_number":       page_number,
                "char_count":        len(text),
                "text_preview":      text[:100],  # first 100 chars only — full text in 'text' field
                "chunking_strategy": chunking_strategy,
            },
        }
