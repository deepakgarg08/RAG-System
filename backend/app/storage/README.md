# storage/ — Raw File Persistence

This folder handles persistence of **raw uploaded contract files**.
Vector embeddings go to ChromaDB (via `etl/loaders/`); this layer stores the
original binary files so they can always be retrieved and audited.

## Components

### `local_storage.py` — DEMO
Saves uploaded files to a local `./uploads` directory.
Path is configured via `UPLOAD_DIR` in `.env`.

### `azure_blob.py` — PRODUCTION STUB
Azure Blob Storage client. Requires `AZURE_STORAGE_CONNECTION_STRING` and
`AZURE_STORAGE_CONTAINER_NAME` environment variables.
See `.claude/skills/swap-to-azure.md` for migration steps.

## Why Store Raw Files Separately From Vectors?

| Reason | Detail |
|---|---|
| Different purposes | Vectors are for searching; originals are for downloading and auditing |
| Legal requirement | The original contract must always be retrievable exactly as uploaded — bit-for-bit identical |
| Audit trail | Azure Blob provides versioning and legal hold policies |
| Immutability | Azure Blob immutability policies prevent tampering — important for legal documents |

## Production Swap Note
```
# ============================================================
# DEMO MODE: Local filesystem — instant setup, no config needed
# PRODUCTION SWAP → Azure Blob Storage (AWS: S3):
#   Replace LocalStorage with AzureBlobStorage in storage/
#   Azure Blob adds versioning, legal hold, immutability policies,
#   and geo-redundant storage — all required for legal document compliance
# ============================================================
```
