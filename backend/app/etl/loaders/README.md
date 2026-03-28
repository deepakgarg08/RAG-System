# loaders/ — Vector Store Loaders

## Pattern
All loaders extend `BaseLoader` defined in `base.py`.
They implement `load(chunks: list, embeddings: list) -> None` and
`get_collection_count() -> int`.
Swapping the loader is the single change needed to move from demo to production.

## Loaders

### `chroma_loader.py` — DEMO
ChromaDB local vector store. Runs in-process, persists to local disk.
Zero configuration required beyond setting `CHROMA_PERSIST_PATH` in `.env`.

### `azure_loader.py` — PRODUCTION STUB
Azure AI Search client. Requires `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_KEY`,
and `AZURE_SEARCH_INDEX_NAME` environment variables.
See `.claude/skills/swap-to-azure.md` for the full migration steps.

## Comparison

| Feature | ChromaDB (demo) | Azure AI Search (production) |
|---|---|---|
| Setup | `pip install`, zero config | Azure portal + API key |
| Search type | Vector only | Vector + keyword hybrid |
| Scale | Single machine | Enterprise, millions of docs |
| Security | None | Azure AD, RBAC |
| Cost | Free | ~€80–200/month depending on tier |
| Persistence | Local disk | Azure managed, geo-redundant |
| Filtering | Basic metadata filter | Full OData filter expressions |

## The Swap Point
In `pipeline.py`, the loader is selected here:

```python
# ============================================================
# DEMO MODE: ChromaDB — zero config, runs locally on any machine
# PRODUCTION SWAP → Azure AI Search (AWS: OpenSearch / Kendra):
#   Replace ChromaLoader with AzureLoader on the line below
#   Azure AI Search adds hybrid search + enterprise RBAC
# ============================================================
loader = ChromaLoader(config)   # ← swap this line only
```
