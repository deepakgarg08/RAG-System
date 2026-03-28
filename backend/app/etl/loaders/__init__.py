"""
loaders — Vector store loader package.
Each loader extends BaseLoader and implements load() and get_collection_count().
Swapping the active loader in pipeline.py is the single change needed to move
from ChromaDB (demo) to Azure AI Search (production).
"""

# TODO: implemented in Prompt 1B
