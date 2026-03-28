# Azure Services — Production Configuration Guide

## Service Mapping

| Demo Component | Azure Service | AWS Equivalent | Riverty Tier Recommendation |
|---|---|---|---|
| OpenAI API | Azure OpenAI | Bedrock (Claude/Titan) | Standard — same models, GDPR-compliant endpoint |
| ChromaDB | Azure AI Search | OpenSearch / Kendra | Basic (S1) → Standard (S2) when >50k docs |
| Local filesystem | Azure Blob Storage | S3 | LRS (locally redundant) minimum, GRS for legal hold |
| PyMuPDF + Tesseract | Azure Document Intelligence | Textract | Standard tier — prebuilt document model |

## Why Azure for Riverty?
- Riverty operates under German/EU data protection law — Azure EU regions (West Europe /
  Germany West Central) ensure data residency compliance
- Riverty is a Microsoft shop — Azure AD SSO, existing enterprise agreements, familiar ops team
- Azure OpenAI is the only Azure-hosted deployment of GPT-4o — avoids data leaving
  the Azure trust boundary

---

## Azure OpenAI

**Replaces:** Direct OpenAI API
**Purpose:** GPT-4o for answer generation + text-embedding-3-small for embeddings

### Setup
1. Create Azure OpenAI resource in Azure Portal → `West Europe` region
2. Deploy model: `gpt-4o` (deployment name can differ from model name — use same for simplicity)
3. Deploy model: `text-embedding-3-small`
4. Copy endpoint and API key to `.env`

### Environment variables
```
AZURE_OPENAI_API_KEY=<key from Azure Portal>
AZURE_OPENAI_ENDPOINT=https://<resource-name>.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

### Code change (embeddings.py + agent.py)
```python
# FROM (demo):
from openai import OpenAI
client = OpenAI(api_key=config.OPENAI_API_KEY)

# TO (production):
from openai import AzureOpenAI
client = AzureOpenAI(
    api_key=config.AZURE_OPENAI_API_KEY,
    azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
    api_version=config.AZURE_OPENAI_API_VERSION,
)
```

---

## Azure AI Search

**Replaces:** ChromaDB
**Purpose:** Vector store with hybrid search (vector + keyword)

### Setup
1. Create Azure AI Search resource in Azure Portal → `West Europe` region
2. Choose pricing tier: Basic for demo/dev, Standard S1 for production
3. Create index named `riverty-contracts` with fields: id, content, embedding, metadata
4. Copy endpoint and admin key to `.env`

### Environment variables
```
AZURE_SEARCH_ENDPOINT=https://<resource-name>.search.windows.net
AZURE_SEARCH_KEY=<admin key from Azure Portal>
AZURE_SEARCH_INDEX_NAME=riverty-contracts
```

### Additional benefit over ChromaDB
Azure AI Search supports **hybrid search** — combines vector similarity with BM25 keyword
scoring. For legal text, keyword matching on exact clause names (e.g. "Force Majeure")
improves retrieval precision beyond pure semantic similarity.

---

## Azure Blob Storage

**Replaces:** Local filesystem (`./uploads`)
**Purpose:** Raw contract file storage with legal hold and audit trail

### Setup
1. Create Storage Account in Azure Portal → `Germany West Central` region
2. Create container: `contracts`
3. Enable versioning and soft delete (legal requirement)
4. Copy connection string to `.env`

### Environment variables
```
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_CONTAINER_NAME=contracts
```

### Legal hold configuration
For production use, configure immutability policies on the container:
- Time-based retention: minimum 7 years (German commercial law requirement)
- Legal hold: can be applied to individual blobs during active disputes

---

## Azure Document Intelligence

**Replaces:** PyMuPDF + Tesseract
**Purpose:** Unified extraction for typed PDFs, scanned PDFs, and JPEG contracts

### Setup
1. Create Document Intelligence resource in Azure Portal → `West Europe` region
2. Use prebuilt `prebuilt-document` model (handles contracts, invoices, general documents)
3. Copy endpoint and key to `.env`

### Environment variables
```
AZURE_DOC_INTELLIGENCE_ENDPOINT=https://<resource-name>.cognitiveservices.azure.com
AZURE_DOC_INTELLIGENCE_KEY=<key from Azure Portal>
```

### Advantage over demo approach
Single API call replaces the two-extractor pipeline. Handles:
- Typed PDFs (replaces PyMuPDF)
- Scanned PDFs and JPEGs (replaces Tesseract)
- Tables, form fields, handwriting
- Better German language accuracy than Tesseract

---

## Migration Checklist
See `.claude/skills/swap-to-azure.md` for the complete step-by-step migration guide.

- [ ] Azure OpenAI resource created and models deployed
- [ ] Azure AI Search index created with correct field schema
- [ ] Azure Blob Storage container created with retention policies
- [ ] Azure Document Intelligence resource created
- [ ] All environment variables added to `.env`
- [ ] `demo → production` swap complete in: `embeddings.py`, `agent.py`, `pipeline.py`, `storage/`
- [ ] Test suite passes: `pytest backend/tests/`
- [ ] docs/azure-services.md updated with actual resource names
