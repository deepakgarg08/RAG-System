# Self-Evaluation — Riverty Contract Review
# PRIVATE — do not share with interviewer

---

## Section 1: Requirements Coverage Checklist

### Presentation requirements

| Requirement | Status | Notes |
|---|---|---|
| Solution explaining how you would tackle the challenge | ✅ Fully done | docs/architecture.md covers this end to end |
| Overall technical solution for the team | ✅ Fully done | architecture.md + decisions.md + azure-services.md |
| Basic explanation of infrastructure | ✅ Fully done | docs/azure-services.md maps every service; swap comments in code |
| Concept for colleague adoption | ⚠️ Partial | Mentioned in architecture summary but no dedicated adoption plan doc — covered in evaluation_shareable.md |
| Anything else relevant | ✅ Fully done | 7 ADRs, data-flow.md, testing-guide.md |

### Basic implementation requirements

| Requirement | Status | Notes |
|---|---|---|
| Pipeline showing how to analyse documents | ✅ Complete | Full ETL: PDF + OCR → clean → chunk → embed → ChromaDB |
| Frontend demonstrating how the solution can be used | ❌ Not built | frontend/ folder has only a README.md — no React app |
| End-to-end workflow | ⚠️ Partial | Backend Docker works; no docker-compose.yml to tie frontend + backend together |

### Technical stack alignment

| Requirement | Status | Notes |
|---|---|---|
| Azure | ✅ Documented | Swap comments throughout; azure-services.md; zero Azure services active |
| Azure Foundry / Azure OpenAI | ✅ Documented | ADR-007; swap comments in agent.py and embeddings.py |
| Google Gemini | ❌ Not used | Not referenced anywhere — demo uses OpenAI API |
| Containerized environments | ⚠️ Partial | Dockerfile exists and works; no docker-compose.yml (removed misleading commands from SETUP.md today) |
| Python + FastAPI | ✅ Complete | FastAPI 0.111 + uvicorn; full async implementation |
| Terraform | ❌ Not implemented | Not mentioned in code; infrastructure is all manual |
| React + TypeScript frontend | ❌ Not built | frontend/ is empty except README.md |
| LangChain + LangGraph | ✅ Complete | LangGraph 4-node agent; LangChain text splitters used |

### Specific business problem requirements

| Requirement | Status | Notes |
|---|---|---|
| PDF contracts from SharePoint | ⚠️ Partial | PDF extraction works; SharePoint integration not built |
| Scanned JPEG contracts | ✅ Complete | Tesseract OCR pipeline tested with real JPEG sample |
| Compare contracts | ✅ Functional | Cross-contract comparison works via natural language query |
| Find missing clauses | ✅ Functional | Demonstrated in tests ("no GDPR clause" query works) |
| Update company names | ⚠️ Partial | Read-only system — no write/edit contract feature |
| SharePoint integration | ❌ Not built | Graph API path documented but not implemented |
| Contract REST API storage | ❌ Not built | Files stored locally; no legally-compliant external API |

---

## Section 2: Honest Gap Analysis

### ❌ Frontend (React + TypeScript)
**What to say if asked:**
"The backend is fully implemented with a working REST API and SSE streaming — you can demo
everything via curl or the FastAPI Swagger UI at /docs. I prioritised building a solid,
tested AI pipeline over scaffolding a UI that would add noise without demonstrating the
core technical decisions. Given another day I would build a two-panel React component:
drag-drop upload on the left, streaming answer with source citations on the right. The
API is already designed for exactly that — POST /api/ingest for upload, POST /api/query
returns an SSE stream of tokens."

### ❌ Terraform
**What to say if asked:**
"Terraform is not in the demo — I focused on the AI pipeline and made every infrastructure
component clearly documented with its Azure swap. For production I would write three Terraform
modules: one for Azure Container Apps (the backend), one for Azure AI Search (vector store),
and one for Azure Blob Storage (contract files). That would take approximately 2-3 days to
implement properly, including state backend in Azure Storage and CI/CD integration."

### ❌ SharePoint integration
**What to say if asked:**
"The ingest endpoint (POST /api/ingest) is file-format agnostic — it accepts PDF and JPEG
regardless of where the file comes from. A SharePoint integration would be a separate ingestion
trigger: Microsoft Graph API with a service principal, a webhook on the document library for
new uploads, and a scheduled batch sync for existing files. That integration sits outside the
AI pipeline itself and would take 1-2 days to build."

### ❌ Contract REST API storage (legally compliant copies)
**What to say if asked:**
"The demo stores files locally in uploads/. For production, contracts need to be stored in
Azure Blob Storage with versioning and legal hold enabled — that is the swap comment in
storage/local_storage.py. The 'legally compliant copy' requirement is a storage policy
decision (immutable storage, audit logs, retention policies) rather than an AI feature. I
documented the Azure Blob path but did not provision the service for the demo."

### ❌ Google Gemini
**What to say if asked:**
"The case study mentions Azure Foundry / Google Gemini as part of Riverty's stack. I chose
OpenAI GPT-4o as the demo LLM because it has the strongest legal reasoning benchmark scores
and the Azure OpenAI swap is two lines of code — same SDK, same model names. Gemini would
require a different SDK entirely. If Riverty standardises on Gemini, the LangGraph nodes
are model-agnostic; the only change would be in the LLM client initialisation in agent.py."

### ⚠️ docker-compose.yml missing
**What to say if asked:**
"There is no docker-compose.yml because the frontend was not built. A compose file with
a single service is unnecessary — a plain Dockerfile is cleaner. Once the React frontend
is added, a two-service compose file (backend + frontend with Nginx) would be the right
next step. I updated SETUP.md today to use plain docker commands rather than misleading
compose commands."

### ⚠️ Adoption concept thin
**What to say if asked:**
"The adoption strategy is covered in the evaluation document I prepared: a three-phase
pilot → refinement → rollout plan. In a real engagement I would run a half-day workshop
with the legal team before writing any code — understanding how they currently open, read,
and annotate contracts would directly shape the UI, the suggested query templates, and
what 'a good answer' means to them."

---

## Section 3: Things That Could Go Wrong in Demo

1. **OpenAI API key invalid / rate limited**
   → Recovery: Have 2-3 pre-run answers saved as text files. Show the answer output directly
   and explain "this is exactly what the system would stream token by token."
   → Prevention: Test the key 30 minutes before the demo.

2. **ChromaDB empty / chroma_db/ directory missing**
   → Recovery: Run `bash backend/run_pipeline.sh --ingest-only` — takes ~45 seconds.
   → Prevention: Run ingest the night before and verify with
   `python -c "import chromadb; col = chromadb.PersistentClient('./chroma_db').get_collection('riverty_contracts'); print(col.count())"`.

3. **bge-m3 model not cached (first run on a new machine)**
   → Recovery: The model downloads automatically (~2.3 GB) — show the download progress
   as proof the system is self-contained. Have a hotspot ready if WiFi is slow.
   → Prevention: Pre-download on the demo machine with the explicit download command in SETUP.md.

4. **Docker build fails**
   → Recovery: Run directly with `source .venv/bin/activate && uvicorn app.main:app --reload --port 8000`.
   → Prevention: Run `docker build -t riverty-backend ./backend` the day before.

5. **Port 8000 already in use**
   → Recovery: `lsof -i :8000 | grep LISTEN` then `kill -9 <PID>`, or use `--port 8001`.
   → Prevention: Check before the demo with `curl http://localhost:8000/health`.

6. **Tesseract not installed on demo machine**
   → Recovery: Show the .txt contracts instead; explain the OCR path is identical for PDFs
   that have been scanned. The JPEG test in the test suite proves OCR works.
   → Prevention: `tesseract --version` before leaving for the interview.

7. **SSE streaming shows all tokens at once (proxy buffering)**
   → Recovery: Demo via curl: `curl -N -X POST http://localhost:8000/api/query -H "Content-Type: application/json" -d '{"question":"..."}'` — this always streams correctly.
   → Prevention: Use the FastAPI `/docs` Swagger UI or curl for the demo, not a browser through a proxy.

---

## Section 4: What Makes This Submission Strong

- **LangGraph 4-node agent** with typed state — not a simple LLM call or LCEL chain.
  Each node (query_router, retriever, reasoner, formatter) is independently unit-testable.
- **88 tests, all passing** — ETL pipeline, RAG agent, API routes, integration test.
  Tests are fully offline (mocked OpenAI + ephemeral ChromaDB).
- **Clear production upgrade path for every component** — swap comments with exact
  Azure service names, SDK package versions, and code diffs.
- **7 Architecture Decision Records** — every non-obvious choice is documented with
  context, reasoning, alternatives considered, and trade-offs.
- **Content-aware chunking** — detects Q&A, legal clause, and narrative sections and
  adjusts chunk strategy accordingly.
- **Per-folder README system** — every backend subfolder has its own README.md explaining
  the Strategy Pattern, the base class contract, and how to add a new implementation.
- **Bilingual support** — English and German contracts both work; language detected at
  ingest time via langdetect.
- **SSE streaming** — answers appear token by token, not as a 5-second blank wait.
  Proxy buffering already handled with X-Accel-Buffering: no.
- **Non-root Docker user** — Dockerfile uses a dedicated appuser; shows security awareness.
- **bge-m3 embeddings are free and offline** — no embedding API costs during ingest;
  no API dependency for the core retrieval path.

---

## Section 5: Interview Questions You Might Get

**1. "Why did you choose RAG over fine-tuning?"**

RAG is the only viable approach for this use case for three reasons that matter to Riverty's
legal team specifically. First, traceability: every answer must cite the exact clause it came
from — RAG does this automatically through chunk metadata; a fine-tuned model cannot. Second,
GDPR: storing contract content in model weights makes it harder to audit and impossible to
delete; a vector store entry can be deleted instantly. Third, freshness: a new contract is
queryable 10 seconds after upload; fine-tuning would need a full retraining cycle. See ADR-001
for the full comparison table.

**2. "How would you handle 10,000 contracts instead of 4?"**

ChromaDB would not scale to 10,000 contracts — that is why the swap to Azure AI Search is
already documented. Azure AI Search handles millions of vectors with hybrid (vector + keyword)
search, RBAC, and horizontal scale. At the pipeline level: async batch ingestion with a queue
(Azure Service Bus), parallel embedding workers, and a deduplication check on file hash before
re-embedding. The current ETL pipeline already uses batch embedding (`model.encode(texts)` not
one-by-one) so the per-file cost is already minimised.

**3. "Why ChromaDB and not Pinecone or Weaviate?"**

The demo must run on a laptop with zero cloud configuration — just an OpenAI API key. ChromaDB
runs in-process, persists to local disk, and requires no credentials. Pinecone is cloud-only
(would need a second paid API). Weaviate requires a separate Docker service which adds setup
friction. For production ChromaDB is explicitly wrong and Azure AI Search is the correct choice
— that decision is already made and documented in ADR-002.

**4. "What's the token limit problem with large contracts?"**

The chunking strategy handles this. Each chunk is ~1000 characters with 200 overlap, which
is well under GPT-4o's 128k context window even for the top-K=8 chunks passed to the model
(~8,000 characters of context). The real risk at large scale is retrieval precision — with
50+ contracts, the 8 retrieved chunks might span too many documents and dilute the answer.
The solution is hybrid search in Azure AI Search (BM25 keyword + vector) and increasing
TOP_K_RESULTS to 12-15 for broader corpus. For very long individual contracts (100+ pages),
a two-stage approach would help: first retrieve the most relevant sections, then summarise
those sections before passing to the LLM.

**5. "How would you ensure data security for legal documents?"**

Five layers: (1) Azure OpenAI processes data within the Azure tenant — contract text never
reaches OpenAI's servers. (2) Azure Blob Storage with private endpoints — contracts not
accessible from the public internet. (3) Azure Key Vault for all secrets — no .env files
in production. (4) Azure AD authentication on the frontend — only authenticated Riverty staff
can upload or query. (5) Audit logging on all query events — who asked what, when, and which
contracts were retrieved. The demo intentionally uses synthetic contracts so nothing real passes
through the OpenAI API.

**6. "How would you integrate with SharePoint?"**

Microsoft Graph API with a service principal authenticated via Azure AD. Two integration modes:
(a) Webhook: register a change notification on the contracts document library — new files
trigger a POST to the ingest endpoint automatically. (b) Batch sync: a scheduled Azure
Function that pages through the library and calls POST /api/ingest for any file modified since
the last sync timestamp. The ingest endpoint already handles deduplication via content hash so
re-syncing is safe. Total implementation: 1-2 days.

**7. "How would you make this GDPR compliant for Riverty?"**

Key measures: Azure data residency in EU West/North Europe regions; Azure OpenAI keeps
processing within the Azure tenant; no query logging in production mode (only aggregate
metrics); data retention policies on Azure Blob (contracts deleted after contract expiry
plus statutory hold period); right to erasure implemented as a DELETE endpoint that removes
the ChromaDB/Azure AI Search entries plus the blob; audit trail for every query (who,
what, when). The synthetic test data already means nothing sensitive is in the demo database.

**8. "What would you change about this architecture for production?"**

Priority order: (1) Replace ChromaDB with Azure AI Search — enables hybrid search and RBAC.
(2) Azure OpenAI instead of OpenAI API — data stays in tenant. (3) Azure Blob Storage for
contract files — durability, versioning, legal hold. (4) Azure AD authentication on the API.
(5) Async ingestion queue (Azure Service Bus) — large files won't time out the HTTP request.
(6) Terraform modules for all of the above. (7) CI/CD pipeline (GitHub Actions or Azure
DevOps). The application code barely changes — most of this is infrastructure and client
initialisation swaps.

**9. "Why FastAPI over Django or Flask?"**

Three reasons: (1) Native async — the SSE streaming endpoint and LangGraph's `astream_events`
are async by design; FastAPI handles them without workarounds. (2) Automatic OpenAPI docs —
the Swagger UI at /docs is generated from the Pydantic models with zero extra code; useful
for a legal team that wants to understand the API. (3) Pydantic integration — request/response
validation is built-in and typed; every API boundary is validated without boilerplate. Django
would be over-engineered for a single-service API with no ORM; Flask would require layering
in async support manually.

**10. "Walk me through the LangGraph agent nodes."**

State flows through four nodes as a typed `AgentState` dict:

- **query_router** — classifies the user's question into an intent category
  (find_clause, find_missing_clause, compare_contracts, general). Sets `query_type` in state.
  This is where future branching logic lives — a `compare` intent could fan out to two
  separate retrievals.

- **retriever** — calls `ContractRetriever.retrieve()`, which embeds the question with
  bge-m3, queries ChromaDB for the top-K most similar chunks, and filters by the
  similarity threshold (0.40). Stores chunks and metadata in state.

- **reasoner** — builds a system prompt that strictly limits the LLM to the retrieved
  chunks ("answer only from the documents provided, say 'not found' if the information
  is absent"). Calls GPT-4o with streaming. The grounding instruction is the primary
  hallucination prevention mechanism.

- **formatter** — appends the source attribution block to the streamed answer:
  file name, page number, chunk index, and similarity score for each retrieved chunk.

The graph is compiled with `StateGraph(AgentState)` and exposed via `astream_events`
for token-level SSE streaming to the frontend.
