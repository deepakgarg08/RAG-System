"""
chunker.py — Text chunking with metadata attachment.
Splits clean text using LangChain RecursiveCharacterTextSplitter (chunk=1000,
overlap=200) and attaches {source_file, chunk_index, total_chunks, language,
file_type} metadata to every chunk for downstream retrieval attribution.
"""

# TODO: implemented in Prompt 1B
