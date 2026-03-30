# Environment Variables Reference

Copy the block below into `backend/.env` (or source from Azure Key Vault in production).

```env
# ============================================================
# ENVIRONMENT SWITCH
# development → runs fully locally, no Azure credentials needed
# production  → all four components switch to Azure automatically:
#               LLM (AsyncAzureOpenAI), Embeddings (text-embedding-3-large),
#               Vector store (Azure AI Search), File storage (Azure Blob)
#               Requires all AZURE_* variables below to be filled.
# ============================================================
APP_ENV=development

# Logging
LOG_LEVEL=INFO

# ============================================================
# DEMO — OpenAI direct API (used when APP_ENV=development)
# ============================================================
OPENAI_API_KEY=sk-...

# ============================================================
# DEMO — local storage paths (used when APP_ENV=development)
# ============================================================
CHROMA_PERSIST_PATH=./chroma_db
UPLOAD_DIR=./uploads
REGISTRY_PATH=./ingestion_registry.json

# ETL tuning
MAX_CHUNK_SIZE=1500
CHUNK_OVERLAP=200
TOP_K_RESULTS=8

# ============================================================
# PRODUCTION — Azure OpenAI (activated when APP_ENV=production)
# Replaces: direct OpenAI API in agent.py and embeddings.py
# ============================================================
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o

# ============================================================
# PRODUCTION — Azure AI Search (activated when APP_ENV=production)
# Replaces: ChromaDB local in chroma_loader.py
# ============================================================
AZURE_SEARCH_ENDPOINT=https://<your-search>.search.windows.net
AZURE_SEARCH_KEY=
AZURE_SEARCH_INDEX_NAME=riverty-contracts

# ============================================================
# PRODUCTION — Azure Blob Storage (activated when APP_ENV=production)
# Replaces: local filesystem in local_storage.py
# ============================================================
AZURE_STORAGE_CONNECTION_STRING=
AZURE_STORAGE_CONTAINER_NAME=contracts

# ============================================================
# PRODUCTION — Azure Document Intelligence (optional OCR upgrade)
# Replaces: PyMuPDF + Tesseract extractors
# ============================================================
AZURE_DOC_INTELLIGENCE_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/
AZURE_DOC_INTELLIGENCE_KEY=
```
