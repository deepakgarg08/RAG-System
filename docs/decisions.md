# Architecture Decision Records

This file contains all significant technical decisions made for the Riverty Contract Review
project. New ADRs should be added using the `write-adr` skill.

---

## ADR-001: LangGraph for Agent Orchestration

**Status:** Accepted
**Date:** 2024-01-01
**Decider:** Deepak Garg

### Context
The RAG query layer needs to handle multiple types of legal questions with different
processing paths. A simple LLM call is insufficient — some queries require routing,
some require multi-step reasoning, and all require traceable intermediate states
for debugging.

### Decision
Use LangGraph to implement the query agent as an explicit state machine with four
named nodes: query_router, retriever, reasoner, formatter.

### Reasoning
- LangGraph gives full control over agent flow with explicit conditional edges
- Each node's input/output is inspectable — critical for debugging legal answer quality
- Different query types (find clause, find missing, compare, update) can route to
  different processing paths without hacking around chain limitations
- State is typed — TypedDict enforces what each node can read and write

### Alternatives Considered
| Option | Why rejected |
|---|---|
| Plain LangChain LCEL chain | Opaque intermediate states, hard to add routing logic |
| Direct OpenAI API calls | No built-in retry, state management, or flow control |
| LlamaIndex | Less control over agent flow; LangGraph integrates better with LangChain ecosystem |

### Consequences
**Positive:**
- Full control over query routing and processing
- Each step is debuggable and testable in isolation
- Easy to add new query types as new LangGraph nodes

**Negative / Trade-offs:**
- More initial boilerplate than a simple chain
- LangGraph is a newer library — API may evolve

### Production Upgrade Path
LangGraph works identically with Azure OpenAI — only the client initialisation
in `agent.py` changes when migrating.

---

## ADR-002: ChromaDB for Demo Vector Store

**Status:** Accepted
**Date:** 2024-01-01
**Decider:** Deepak Garg

### Context
The system needs a vector store for the demo. The demo must run on a laptop with
zero cloud configuration — a reviewer should be able to run `docker-compose up`
and have a working system.

### Decision
Use ChromaDB as the vector store for demo mode, with Azure AI Search as the
clearly documented production swap target.

### Reasoning
- Zero configuration — no cloud account, no API keys beyond OpenAI
- Runs in-process with Python — no separate service to start
- Persists to local disk — vectors survive restarts
- Python-native API — clean integration with LangChain and LangGraph

### Alternatives Considered
| Option | Why rejected |
|---|---|
| Qdrant | Requires a separate Docker service — adds setup complexity for demo |
| Pinecone | Cloud-only — defeats the zero-config demo goal |
| FAISS | In-memory only — vectors lost on restart, no metadata filtering |
| Azure AI Search directly | Requires Azure subscription — not suitable for demo |

### Consequences
**Positive:**
- Demo runs completely offline (no vector store cloud costs)
- Simple swap to Azure AI Search for production (one line in pipeline.py)

**Negative / Trade-offs:**
- ChromaDB does not support hybrid (vector + keyword) search — Azure AI Search does
- Single-machine only — cannot scale horizontally

### Production Upgrade Path
Replace `ChromaLoader` with `AzureLoader` in `pipeline.py`.
Azure AI Search adds hybrid search, RBAC, and enterprise scale.
See `.claude/skills/swap-to-azure.md` for step-by-step migration.

---

## ADR-003: Server-Sent Events for Query Streaming

**Status:** Accepted
**Date:** 2024-01-01
**Decider:** Deepak Garg

### Context
Legal queries take 3–5 seconds to complete. The UI must provide feedback during
this wait rather than showing a blank screen.

### Decision
Use Server-Sent Events (SSE) to stream LLM tokens to the frontend as they are
generated.

### Reasoning
- SSE is unidirectional (server → client) — perfect fit for this use case
- Works through all proxies and firewalls (plain HTTP, not a protocol upgrade)
- Native browser EventSource support — no client library needed
- Simple stream format: `data: {token}\n\n` per token, `data: [DONE]\n\n` at end

### Alternatives Considered
| Option | Why rejected |
|---|---|
| WebSocket | Bidirectional — adds connection lifecycle complexity for no benefit |
| Polling | Multiple requests, latency between tokens, more server load |
| Wait for full response | 3-5s blank screen is poor UX |

### Consequences
**Positive:**
- Simple implementation on both server (FastAPI StreamingResponse) and client
- Reliable through corporate firewalls common in Riverty's enterprise environment

**Negative / Trade-offs:**
- Cannot send data from client to server on the same SSE connection
  (acceptable — query is sent via the initial POST, stream is response only)

### Production Upgrade Path
SSE works identically in production. No changes needed when migrating to Azure.
