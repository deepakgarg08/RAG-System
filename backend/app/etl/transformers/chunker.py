"""
chunker.py — Text chunking with metadata attachment.
Splits clean text using LangChain RecursiveCharacterTextSplitter (chunk=1000,
overlap=200) and attaches {source_file, chunk_index, total_chunks, language,
file_type} metadata to every chunk for downstream retrieval attribution.
"""
import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings

logger = logging.getLogger(__name__)


class DocumentChunker:
    """Splits cleaned text into overlapping chunks with attached metadata."""

    def __init__(self) -> None:
        """Initialise the splitter with chunk size and overlap from config."""
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.max_chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def chunk(self, text: str, metadata: dict) -> list[dict]:
        """Split text into chunks and attach metadata to each chunk.

        Args:
            text: Clean text string to split.
            metadata: Base metadata dict — must include 'source_file', 'file_type',
                      and 'language'. chunk_index and total_chunks are added here.

        Returns:
            List of chunk dicts, each with 'text' and 'metadata' keys.
        """
        raw_chunks = self._splitter.split_text(text)
        total = len(raw_chunks)

        result: list[dict] = []
        total_chars = 0

        for i, chunk_text in enumerate(raw_chunks):
            char_count = len(chunk_text)
            total_chars += char_count
            result.append(
                {
                    "text": chunk_text,
                    "metadata": {
                        **metadata,
                        "chunk_index": i,
                        "total_chunks": total,
                        "char_count": char_count,
                    },
                }
            )

        avg_size = total_chars // total if total > 0 else 0
        logger.info(
            "DocumentChunker: %s — %d chunks created, avg %d chars/chunk",
            metadata.get("source_file", "unknown"),
            total,
            avg_size,
        )
        return result
