# Azure Services — Production Configuration Guide

## One-line production switch

Set `APP_ENV=production` in `backend/.env`. No code changes required.
All four components switch automatically:

| Component | `APP_ENV=development` (demo) | `APP_ENV=production` |
|---|---|---|
| LLM | `AsyncOpenAI` (gpt-4o direct) | `AsyncAzureOpenAI` (gpt-4o via Azure) |
| Embeddings | `BAAI/bge-m3` local, 1024-dim | Azure `text-embedding-3-large`, 3072-dim |
| Vector store | ChromaDB local | Azure AI Search |
| File storage | Local filesystem (`UPLOAD_DIR`) | Azure Blob Storage |

> **Re-ingestion required** when switching to production: embedding dimensions change
> from 1024 to 3072. Clear `chroma_db/` and re-upload all contracts.

---

## Service Mapping

| Demo Component | Azure Service | AWS Equivalent | Riverty Tier Recommendation |
|---|---|---|---|
| PyMuPDF + Tesseract | Azure Document Intelligence | Textract | Standard — prebuilt document model |
| ChromaDB | Azure AI Search | OpenSearch / Kendra | Basic (S1) dev → Standard (S2) production |
| Local filesystem (`./uploads`) | Azure Blob Storage | S3 | LRS minimum; GRS for legal hold |
| OpenAI API | Azure OpenAI | Bedrock | Standard — gpt-4o + text-embedding-3-small |
| Local uvicorn | Azure Container Apps | ECS Fargate | Consumption plan → Dedicated for SLA |
| `.env` file | Azure Key Vault | Secrets Manager | Standard tier |

## Why Azure for Riverty?

- Riverty operates under German/EU data protection law — Azure `Germany West Central` and
  `West Europe` regions ensure data residency compliance without additional legal review
- Riverty is a Microsoft shop — Azure AD SSO, existing Enterprise Agreements, and a
  familiar operations team reduce adoption cost
- Azure OpenAI is the only Azure-hosted deployment of GPT-4o — all contract text processed
  by the LLM stays within the Azure trust boundary and never reaches OpenAI's US servers

---

## Azure Document Intelligence

**AWS Equivalent:** Amazon Textract
**Used for:** Extracting text from uploaded contract files — typed PDFs, scanned PDFs, and JPEG images in a single unified API call
**Replaces:** PyMuPDF (`pdf_extractor.py`) + Tesseract (`ocr_extractor.py`)
**Why better for production:**
- One API call handles all document types — no need to detect whether a PDF is typed or scanned
- Significantly better German-language OCR accuracy than open-source Tesseract
- Extracts tables, form fields, and handwritten annotations — useful for contract schedules and annexes
**Estimated cost for Riverty:** ~€15/month for 1,000 pages ingested; ~€1.50/1,000 pages at scale

**How to connect:**
```python
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from app.config import settings

client = DocumentAnalysisClient(
    endpoint=settings.azure_doc_intelligence_endpoint,
    credential=AzureKeyCredential(settings.azure_doc_intelligence_key),
)
poller = client.begin_analyze_document("prebuilt-document", document=file_bytes)
result = poller.result()
text = "\n".join([line.content for page in result.pages for line in page.lines])
```

---

## Azure AI Search

**AWS Equivalent:** Amazon OpenSearch / Amazon Kendra
**Used for:** Storing 1536-dimensional contract chunk embeddings and retrieving the most relevant chunks for each user query via vector similarity search
**Replaces:** ChromaDB (`chroma_loader.py`, `retriever.py`)
**Why better for production:**
- Hybrid search (vector + BM25 keyword) — exact clause name matches (e.g. "Force Majeure") improve precision beyond pure semantic similarity
- Enterprise RBAC — restrict which legal team members can query which contract collections
- Horizontal scale — handles millions of document chunks across a large contract corpus
**Estimated cost for Riverty:** ~€80/month (Basic S1, up to 50 indexes, 2GB storage); ~€250/month Standard S2 for high-availability production

**How to connect:**
```python
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from app.config import settings

client = SearchClient(
    endpoint=settings.azure_search_endpoint,
    index_name=settings.azure_search_index_name,
    credential=AzureKeyCredential(settings.azure_search_key),
)
vector_query = VectorizedQuery(vector=query_embedding, k_nearest_neighbors=5, fields="embedding")
results = client.search(search_text=query_text, vector_queries=[vector_query])
chunks = [{"text": r["content"], "source_file": r["source_file"]} for r in results]
```

---

## Azure Blob Storage

**AWS Equivalent:** Amazon S3
**Used for:** Persisting raw uploaded contract files with versioning, legal hold, and geo-redundant backup
**Replaces:** Local filesystem (`local_storage.py`, `./uploads/` directory)
**Why better for production:**
- Immutability policies and legal hold — blobs can be locked against deletion during active disputes or audits
- 7-year retention enforcement — meets German commercial law (HGB §257) document retention requirements
- Geo-redundant storage (GRS) — contract files replicated to a second Azure region for disaster recovery
**Estimated cost for Riverty:** ~€5/month for 100GB LRS; ~€10/month GRS with versioning enabled

**How to connect:**
```python
from azure.storage.blob import BlobServiceClient
from app.config import settings

client = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
container = client.get_container_client(settings.azure_storage_container_name)

# Upload
container.upload_blob(name=filename, data=file_bytes, overwrite=True)

# Download
blob = container.download_blob(filename)
file_bytes = blob.readall()
```

---

## Azure OpenAI

**AWS Equivalent:** Amazon Bedrock (Claude or Titan)
**Used for:** GPT-4o answer generation in `agent.py` and `text-embedding-3-small` embeddings in `embeddings.py`
**Replaces:** Direct OpenAI API (`api.openai.com`)
**Why better for production:**
- Data processed by Azure OpenAI never leaves the Azure tenant — mandatory for legal document confidentiality
- Same models (gpt-4o, text-embedding-3-small), same API, same quality — zero prompt or response changes
- Azure AD authentication available alongside API key auth — fits Riverty's existing IAM setup
**Estimated cost for Riverty:** ~€0.005/1K tokens input (gpt-4o); ~€0.0001/1K tokens (text-embedding-3-small). At 100 queries/day × 2K tokens avg: ~€30/month

**How to connect:**
```python
from openai import AzureOpenAI
from app.config import settings

# Replace OpenAI(...) with this in embeddings.py and agent.py:
client = AzureOpenAI(
    api_key=settings.azure_openai_api_key,
    azure_endpoint=settings.azure_openai_endpoint,
    api_version=settings.azure_openai_api_version,
)
# All subsequent API calls (chat.completions.create, embeddings.create) are identical.
```

---

## Azure Container Apps

**AWS Equivalent:** AWS ECS Fargate / AWS App Runner
**Used for:** Running the FastAPI backend Docker container in a fully managed serverless environment — no VM provisioning, automatic scaling, built-in HTTPS
**Replaces:** Local `uvicorn app.main:app --reload` (development) or a self-managed VM (production)
**Why better for production:**
- Scales to zero when idle — no cost during nights/weekends for a legal team use case
- Built-in ingress with HTTPS and custom domain — no nginx configuration needed
- Integrates with Azure Container Registry, Azure Monitor, and Azure AD out of the box
**Estimated cost for Riverty:** ~€20–40/month (Consumption plan, typical legal team workload); ~€80/month Dedicated plan for guaranteed cold-start SLA

**How to connect:**
```bash
# Build and push image to Azure Container Registry
az acr build --registry rivertyacr --image riverty-api:latest ./backend

# Deploy to Container Apps
az containerapp create \
  --name riverty-api \
  --resource-group riverty-rg \
  --environment riverty-env \
  --image rivertyacr.azurecr.io/riverty-api:latest \
  --target-port 8000 \
  --ingress external \
  --secrets "openai-key=<value>" \
  --env-vars "AZURE_OPENAI_API_KEY=secretref:openai-key"
```

---

## Azure Key Vault

**AWS Equivalent:** AWS Secrets Manager
**Used for:** Storing all production secrets (API keys, connection strings, storage credentials) instead of a `.env` file checked into a server or container image
**Replaces:** `.env` file on the developer's machine
**Why better for production:**
- Secrets never appear in environment variables, container images, or deployment logs
- Fine-grained RBAC — the Container App's managed identity can read secrets without a static key
- Full audit log — every secret read is logged, satisfying compliance requirements
**Estimated cost for Riverty:** ~€0.03/10,000 operations — effectively free for this workload

**How to connect:**
```python
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()  # uses managed identity in Container Apps
client = SecretClient(
    vault_url="https://riverty-keyvault.vault.azure.net/",
    credential=credential,
)
openai_key = client.get_secret("azure-openai-api-key").value
search_key = client.get_secret("azure-search-key").value
```

---

## Migration Checklist

See `.claude/skills/swap-to-azure.md` for the complete step-by-step migration guide.

- [ ] Azure OpenAI resource created, `gpt-4o` and `text-embedding-3-small` models deployed
- [ ] Azure AI Search index created with correct field schema (id, content, embedding, metadata)
- [ ] Azure Blob Storage container `contracts` created with 7-year retention policy
- [ ] Azure Document Intelligence resource created in `West Europe`
- [ ] Azure Container Apps environment and app created, pointing to Container Registry
- [ ] Azure Key Vault populated with all secrets; Container App granted `Key Vault Secrets User` role
- [ ] All environment variables updated in `.env` (or sourced from Key Vault)
- [ ] Code swap complete in: `embeddings.py`, `agent.py`, `pipeline.py`, `storage/local_storage.py`
- [ ] Test suite passes: `pytest backend/tests/ -v`
- [ ] `docs/azure-services.md` updated with actual resource names and endpoints
