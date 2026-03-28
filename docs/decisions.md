# Architecture Decision Records

This file contains all significant technical decisions made for the Riverty Contract Review
project. New ADRs should be added using the `write-adr` skill.

---

## ADR-001: RAG over Fine-tuning for Contract Question Answering

**Status:** Accepted
**Date:** 2026-03-01
**Decider:** Deepak Garg

### Context
The system must answer questions about specific contracts — citing exact clauses, comparing
terms across documents, and flagging missing provisions. Two approaches exist: fine-tune
an LLM on contract data, or use Retrieval-Augmented Generation (RAG) to retrieve relevant
chunks at query time.

### Decision
Use RAG: embed contract chunks into a vector store at ingestion time; retrieve the most
relevant chunks at query time; pass them as context to GPT-4o for grounded answer generation.

### Reasoning
- Contracts change frequently — a new contract is available for querying seconds after
  upload; fine-tuning would require a full retraining cycle for each update
- Legal requirement: every answer must cite the source clause — RAG provides this
  automatically through chunk metadata; fine-tuning cannot
- GDPR data minimisation: storing contract content in model weights is harder to audit
  and harder to delete than a vector store entry
- Fine-tuning would bake specific contract facts into model weights permanently —
  a terminated contract's terms would persist in the model indefinitely

### Alternatives Considered
| Option | Why rejected |
|---|---|
| Full fine-tuning on contract corpus | Cannot cite sources; expensive to retrain; GDPR concerns about data in weights |
| LoRA / PEFT fine-tuning | Same source-citation and GDPR problems; still requires retraining on data changes |
| Keyword search only (no LLM) | Cannot handle paraphrased questions or cross-contract comparisons |

### Consequences
**Positive:**
- New contracts are queryable immediately after ingestion
- Every answer is traceable to a specific document and chunk
- Vector store entries can be deleted (GDPR right to erasure) — model weights are unchanged
- Base model can be upgraded (GPT-4o → GPT-5) without losing any document data

**Negative / Trade-offs:**
- Retrieval quality depends on embedding quality — poor chunking or embeddings degrade answers
- Top-K retrieval may miss relevant chunks if the corpus is very large (mitigated by Azure AI Search hybrid search in production)

### Production Upgrade Path
The RAG architecture is unchanged in production. Only the vector store (ChromaDB → Azure AI Search)
and embedding client (OpenAI → Azure OpenAI) are swapped. The retrieval logic itself is identical.

---

## ADR-002: ChromaDB for Demo Vector Store, Azure AI Search for Production

**Status:** Accepted
**Date:** 2026-03-01
**Decider:** Deepak Garg

### Context
The system needs a vector store. The demo must run on a laptop with zero cloud configuration —
a reviewer must be able to run the app with only an OpenAI API key. Production needs enterprise
scale, hybrid search, and RBAC.

### Decision
Use ChromaDB as the vector store for demo mode. Document the exact one-line swap to Azure AI
Search for production. Both are abstracted behind the `BaseLoader` interface in `etl/loaders/`.

### Reasoning
- ChromaDB requires zero configuration — no cloud account, no additional API keys
- Runs in-process with Python — no separate service to start for the demo
- Persists to local disk — vectors survive restarts without a database server
- The Strategy Pattern in `pipeline.py` makes the swap a single line change

### Alternatives Considered
| Option | Why rejected |
|---|---|
| Qdrant | Requires a separate Docker service — adds setup friction for the demo |
| Pinecone | Cloud-only — defeats the zero-config demo goal; introduces a second paid API |
| FAISS | In-memory only by default — vectors lost on restart; no metadata filtering |
| Azure AI Search directly | Requires Azure subscription and resource provisioning — not suitable for demo |

### Consequences
**Positive:**
- Demo runs completely offline (beyond OpenAI API calls)
- Production swap is one line in `pipeline.py`: `ChromaLoader()` → `AzureSearchLoader()`

**Negative / Trade-offs:**
- ChromaDB does not support hybrid (vector + keyword) search — Azure AI Search does
- ChromaDB is single-machine only — cannot scale horizontally across pods

### Production Upgrade Path
Replace `ChromaLoader()` with `AzureSearchLoader()` in `pipeline.py` and update `ContractRetriever`
in `retriever.py`. Azure AI Search adds hybrid search, RBAC, and horizontal scale required
for multi-tenant production at Riverty. See `.claude/skills/swap-to-azure.md`.

---

## ADR-003: LangGraph over Plain LangChain for Agent Orchestration

**Status:** Accepted
**Date:** 2026-03-01
**Decider:** Deepak Garg

### Context
The RAG query layer needs to handle multiple types of legal questions — finding a specific
clause, identifying missing provisions, comparing contracts, finding contracts by company name.
Each type may need a different processing path. A plain LLM call or a simple chain cannot
route between these paths cleanly, and intermediate states must be inspectable for debugging.

### Decision
Use LangGraph to implement the query agent as an explicit 4-node state machine:
`query_router → retriever → reasoner → formatter`. Each node receives and returns a typed
`AgentState` dict.

### Reasoning
- Explicit graph topology means the flow is readable as a diagram, not inferred from code
- Each node's input/output is inspectable — critical for debugging legal answer quality
- `query_router` can classify intent and future versions can branch to specialised nodes
  (e.g. a `compare` node that retrieves from two contracts separately)
- State is typed via `TypedDict` — each node declares what it reads and writes
- Nodes are independently unit-testable with a mock state dict

### Alternatives Considered
| Option | Why rejected |
|---|---|
| Plain LangChain LCEL chain | Opaque intermediate states; routing requires hacks; hard to add conditional paths |
| Direct OpenAI API calls | No built-in state management, retry logic, or streaming integration |
| OpenAI function calling / Assistants API | Tightly coupled to OpenAI — harder to swap to Azure OpenAI; less control over flow |
| LlamaIndex agents | Less control over node-level routing; LangGraph integrates better with LangChain ecosystem |

### Consequences
**Positive:**
- Full control over query routing — adding a new query type is adding a new node and edge
- Each step is debuggable and testable in isolation
- `astream_events` provides token-level streaming hooks used directly by the SSE endpoint

**Negative / Trade-offs:**
- More initial boilerplate than a simple chain
- LangGraph API evolves — `astream_events` version parameter (`v1`/`v2`) must be tracked

### Production Upgrade Path
LangGraph works identically with Azure OpenAI. Only the `AsyncOpenAI` client initialisation
in `agent.py` changes. The graph topology, node functions, and streaming interface are unchanged.

---

## ADR-004: Server-Sent Events over WebSocket for Query Streaming

**Status:** Accepted
**Date:** 2026-03-01
**Decider:** Deepak Garg

### Context
Legal queries processed by GPT-4o take 3–5 seconds end-to-end. Showing a blank screen for
that duration degrades user experience significantly, especially during a live demo. The UI
must display tokens progressively as they arrive from the LLM.

### Decision
Use Server-Sent Events (SSE) to stream LLM tokens from the FastAPI backend to the React
frontend. Each token is sent as `data: {token}\n\n`; the stream ends with `data: [DONE]\n\n`.

### Reasoning
- SSE is strictly server → client — a perfect fit since the client sends one question and
  only needs to receive one streamed answer
- Works through all HTTP proxies and corporate firewalls (plain HTTP, no protocol upgrade)
- Native `EventSource` browser API — no client library needed
- FastAPI `StreamingResponse` supports SSE natively with `media_type="text/event-stream"`
- Simpler lifecycle than WebSocket: open → stream → close, no ping/pong, no reconnect logic

### Alternatives Considered
| Option | Why rejected |
|---|---|
| WebSocket | Bidirectional adds connection lifecycle complexity (ping/pong, reconnect) with zero benefit for this use case |
| HTTP long polling | Multiple requests introduce latency between tokens; more server load; worse UX |
| Wait for complete response | 3–5 second blank screen is unacceptable UX, especially during demos |
| gRPC streaming | Requires a gRPC client in the browser — not practical without a proxy layer |

### Consequences
**Positive:**
- Simple implementation: `StreamingResponse` on server, `EventSource` on client
- Reliable through Riverty's enterprise proxies and Azure API Management
- Token-by-token display gives immediate feedback during the 3–5 second generation window

**Negative / Trade-offs:**
- Cannot send data from client → server on the same SSE connection (acceptable —
  the question is sent via the initial POST body before the stream opens)
- Requires `X-Accel-Buffering: no` header to disable nginx/Azure Front Door buffering

### Production Upgrade Path
SSE works identically in production behind Azure Application Gateway or Azure API Management.
The `X-Accel-Buffering: no` header already set in `query.py` handles proxy buffering.

---

## ADR-005: Chunk Size 1000 Characters with 200-Character Overlap

**Status:** Accepted
**Date:** 2026-03-01
**Decider:** Deepak Garg

### Context
The chunking strategy directly affects retrieval quality. Chunks that are too small lose
clause context; chunks that are too large return mixed-topic blocks that reduce precision.
Legal contracts have a natural structure — numbered clauses — that should be preserved.

### Decision
Use `RecursiveCharacterTextSplitter` with `chunk_size=1000` and `chunk_overlap=200`,
configurable via `MAX_CHUNK_SIZE` and `CHUNK_OVERLAP` environment variables.

### Reasoning
- 1000 characters ≈ one legal clause — the natural atomic unit of meaning in a contract
  A clause that fits in one chunk is returned whole by retrieval, not split across results
- 200-character overlap prevents a sentence from being cut at a chunk boundary — the tail
  of chunk N appears at the head of chunk N+1, preserving context across the join
- `RecursiveCharacterTextSplitter` tries to split on `\n\n`, then `\n`, then `.` before
  falling back to character count — respects paragraph and sentence boundaries

### Alternatives Considered
| Option | Why rejected |
|---|---|
| 500-char chunks | A typical legal clause spans 600–1200 chars — small chunks split clauses across multiple results, losing context |
| 2000-char chunks | Retrieval returns large blocks mixing multiple clauses on different topics — hurts precision |
| Sentence-level chunking | Sentence boundaries are inconsistent in legal text; German compound sentences can be 200+ chars alone |
| Fixed page-level chunking | PDF pages vary widely in text density; a short clause on a full page wastes retrieval budget |

### Consequences
**Positive:**
- Each retrieved chunk is typically a complete, coherent legal clause
- Overlap ensures no sentence is permanently lost at a boundary

**Negative / Trade-offs:**
- Overlap increases storage by ~20% versus zero-overlap chunking
- Long clauses (>1000 chars) still split — currently acceptable; future work could detect numbered clause boundaries

### Production Upgrade Path
Chunk size is configurable via environment variables — no code change needed to tune for
production. Azure AI Search supports larger payloads; chunk size can be increased to 2000
if the document corpus is predominantly long-form German contracts.

---

## ADR-006: Synthetic Contract Test Data

**Status:** Accepted
**Date:** 2026-03-01
**Decider:** Deepak Garg

### Context
The test suite needs realistic contract documents to exercise the ETL pipeline and RAG agent.
Real Riverty contracts are confidential and unavailable in the development environment.
Tests must run offline and must not contain sensitive business information.

### Decision
Generate synthetic fictional contracts designed to match the characteristics of real
Riverty documents: mix of German and English, varying clause structures, some intentionally
missing GDPR clauses, and at least one scanned (image-only) document.

### Reasoning
- Covers all test scenarios: missing clauses, bilingual content, scanned PDFs, multi-page documents
- No risk of real contract data appearing in version control, CI logs, or bug reports
- Easy to add new edge cases — just write the scenario as a fictional contract
- Real contracts can be added to the test suite later without any code changes — same fixtures

### Alternatives Considered
| Option | Why rejected |
|---|---|
| Real Riverty contracts | Confidential — cannot be stored in git or used in CI |
| Publicly available contracts | Inconsistent format and language; don't cover Riverty-specific scenarios (German law, GDPR clauses) |
| Mocking the extractor entirely | Does not exercise the actual PDF/OCR extraction path — misses real-world bugs |

### Consequences
**Positive:**
- Full test coverage of all document types without confidentiality risk
- Tests always pass offline — no dependency on external contract databases
- Synthetic contracts can intentionally encode edge cases that real documents may not contain

**Negative / Trade-offs:**
- Synthetic contracts may not capture all formatting quirks of real Riverty documents
- Language detection accuracy on synthetic text may differ from production documents

### Production Upgrade Path
No change needed. Real contracts can be added to `tests/sample_contracts/` alongside synthetic
ones. The test fixtures are file-path based — drop in a real contract and the tests exercise it.

---

## ADR-007: OpenAI API for Demo, Azure OpenAI for Production

**Status:** Accepted
**Date:** 2026-03-01
**Decider:** Deepak Garg

### Context
Azure OpenAI requires a Microsoft approval process (typically 1–2 business days) before a
resource can be provisioned. The demo must work immediately without waiting for Azure access.
The production system must keep all data within the Microsoft Azure trust boundary for
GDPR compliance.

### Decision
Use the plain OpenAI API (api.openai.com) for the demo. Document the exact 2-line swap to
`AsyncAzureOpenAI` / `AzureOpenAI` for production. The swap comment is present in both
`agent.py` and `embeddings.py`.

### Reasoning
- Same `openai` Python SDK for both — only the client class and init parameters differ
- Same model names (`gpt-4o`, `text-embedding-3-small`) — no prompt or embedding changes
- Demo can be run and evaluated immediately, independently of Azure provisioning status
- Azure OpenAI is required for production: data processed by Azure OpenAI stays within
  the Azure tenant and never reaches OpenAI's servers — mandatory for Riverty's legal data

### Alternatives Considered
| Option | Why rejected |
|---|---|
| Use Azure OpenAI for demo too | Requires Azure subscription and 1-2 day approval; blocks immediate demo setup |
| Use a local model (Ollama/LM Studio) | Quality gap on legal reasoning tasks; GPT-4o is the benchmark |
| Anthropic Claude API | Different SDK entirely; makes the Azure swap more complex; no Azure-hosted Claude at equivalent tier |

### Consequences
**Positive:**
- Demo is immediately runnable with just an OpenAI API key
- Production swap is exactly 2 lines in each of `embeddings.py` and `agent.py`
- No quality difference — Azure OpenAI serves the same GPT-4o model

**Negative / Trade-offs:**
- Demo data (contract text) passes through OpenAI's API — acceptable for synthetic test data,
  not acceptable for real contracts (which is why the production swap is mandatory before real use)

### Production Upgrade Path
In `embeddings.py` and `agent.py`, change:
```python
# FROM (demo):
client = OpenAI(api_key=settings.openai_api_key)

# TO (production):
client = AzureOpenAI(
    api_key=settings.azure_openai_api_key,
    azure_endpoint=settings.azure_openai_endpoint,
    api_version=settings.azure_openai_api_version,
)
```
No other code changes required. All prompt strings, model names, and response parsing are identical.
