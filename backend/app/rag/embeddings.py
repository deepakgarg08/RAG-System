"""
embeddings.py — Text-to-vector embedding using OpenAI text-embedding-3-small.
Used both at ingest time (embed chunks) and query time (embed user question).
Returns 1536-dimensional float vectors. Swap client to AzureOpenAI for production.
"""

# TODO: implemented in Prompt 1B
