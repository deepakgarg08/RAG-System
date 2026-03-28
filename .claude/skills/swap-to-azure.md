# Skill: Swap Demo → Production Azure

## When to use this skill
Use this when migrating any component from demo mode (local/OpenAI) to
production Azure services.

## Step-by-step process

### 1. Identify all demo swap points
Search the codebase for all comment blocks containing "DEMO MODE:" and list them.

### 2. For each swap point, follow this mapping:

| Demo Component | Azure Production | Code change location |
|---|---|---|
| ChromaDB | Azure AI Search | backend/app/etl/loaders/azure_loader.py |
| Local filesystem | Azure Blob Storage | backend/app/storage/azure_blob.py |
| OpenAI API | Azure OpenAI | backend/app/rag/embeddings.py + agent.py |
| PyMuPDF + Tesseract | Azure Document Intelligence | backend/app/etl/extractors/ |

### 3. For Azure AI Search swap
- Install: `pip install azure-search-documents`
- Replace ChromaLoader with AzureLoader in etl/loaders/
- Update config.py to read: AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY, AZURE_SEARCH_INDEX_NAME
- Uncomment Azure vars in .env

### 4. For Azure OpenAI swap
- Change in embeddings.py and agent.py:
  FROM: `client = OpenAI(api_key=...)`
  TO:   `client = AzureOpenAI(api_key=..., azure_endpoint=..., api_version="2024-02-01")`
- Model name stays the same: "gpt-4o", "text-embedding-3-small"

### 5. For Azure Blob Storage swap
- Install: `pip install azure-storage-blob`
- Replace LocalStorage with AzureBlobStorage in storage/
- Update config.py to read: AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_CONTAINER_NAME

### 6. For Azure Document Intelligence swap
- Install: `pip install azure-ai-formrecognizer`
- Replace pdf_extractor.py and ocr_extractor.py with azure_doc_extractor.py
- One API call handles both PDFs and scanned JPEGs — simplifies the pipeline

### 7. After each swap
- Run the test suite: `pytest backend/tests/`
- Update docs/azure-services.md with actual connection details
- Add a new ADR using the write-adr skill documenting the migration decision
- Update .env.example to reflect new required variables
