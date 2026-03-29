# Presentation Script — Riverty Contract Review
# 15–20 minutes total + Q&A

---

## [0:00–2:00] The Problem — Why This Matters

**Goal:** Establish the business pain before showing any technology.

---

"Let me start with a scenario your legal team lives every day.

A supplier sends over a new service agreement — 40 pages, German law, dense clause structure.
Before it can be signed, someone on your team needs to verify it has a GDPR data processing
clause, check that the termination notice matches your standard 90-day requirement, and confirm
the company name matches the entity in your system of record.

That is one contract. If you have ten contracts from the same procurement round, that review
process multiplies — and you are still doing it manually: open the PDF, search for 'Datenschutz',
scroll through dense legal language, make notes in a spreadsheet.

The system I built changes this. You upload the contracts. You ask a plain English question.
You get a sourced answer in seconds — with the exact clause, the exact page number, and a
relevance score so you know how confident the system is.

Let me show you how it works — and then I'll explain every technical decision behind it."

---

## [2:00–5:00] Solution Architecture — The Big Picture

**Goal:** Walk through the architecture diagram layer by layer. Keep it conversational.

---

**[Show architecture diagram from docs/architecture.md]**

"There are three layers.

At the top: the legal team opens a browser. They drag a contract in, type a question,
and see the answer appear token by token — like ChatGPT, but grounded in their specific contracts.

In the middle: a FastAPI backend. Two endpoints are all that matter:
POST /api/ingest — takes a file, runs the full pipeline.
POST /api/query — takes a question, streams back an answer.

At the bottom: two pipelines that never talk to each other.

The ETL pipeline runs when you upload. It extracts text from PDF or scanned JPEG,
cleans it, splits it into ~1000-character chunks — roughly one legal clause each —
embeds each chunk as a 1024-dimensional vector, and stores it.

The RAG agent runs when you ask a question. It embeds your question the same way,
finds the most semantically similar contract chunks, passes them to GPT-4o with a strict
instruction: answer only from these documents. Then it streams the answer back.

The key design principle: the LLM never sees a contract it does not need. It only sees
the relevant chunks. This prevents hallucination by construction."

**Transition:** "Let me go one level deeper on the parts that are most relevant to Riverty's stack."

---

## [5:00–8:00] Technical Deep Dive

**Goal:** Demonstrate LangGraph, the ETL pipeline, and the Azure path. Drop technical terms naturally.

---

### ETL Pipeline (2 minutes)

"The pipeline uses the Strategy Pattern throughout — every extractor, loader, and transformer
is swappable with one line.

For text PDFs: PyMuPDF extracts text page by page, preserving clause structure.
For scanned JPEGs: Pillow pre-processes the image, Tesseract runs OCR with the German
language pack. The pipeline does not care which path it takes — same interface, different implementation.

Text goes through a content-aware chunker. It detects whether the content is Q&A format,
legal clause structure, or narrative — and applies different splitting strategies. Legal clauses
get 1000-character chunks with 200-character overlap so no sentence is ever cut at a boundary.

Embeddings are generated locally using BAAI/bge-m3 — a multilingual model that handles
German and English contracts equally well. It runs on CPU, it is free, and it is offline.
No API call required during ingestion. The vectors are stored in ChromaDB for the demo."

**Pause for effect:** "In production, ChromaDB is replaced by Azure AI Search with one line
of code. Every component has this pattern — a clearly marked swap comment pointing to the
Azure equivalent."

### LangGraph Agent (2 minutes)

"The query agent is the most important technical decision. I chose LangGraph over a simple
LangChain chain for a reason Riverty's engineering team will appreciate: explicit state.

The agent has four nodes. Each one receives a typed state dictionary and returns an updated one.

[Draw or point to the four nodes:]

query_router classifies the question — is this a 'find a clause' question, a 'missing clause'
question, or a contract comparison? This is where future routing logic lives. Today it sets
a flag. Tomorrow it could branch to a specialised comparison node that retrieves from two
contracts in parallel.

retriever embeds the question, queries the vector store, filters by a similarity threshold
of 0.40, and returns the top-8 chunks with metadata.

reasoner builds a system prompt that strictly limits GPT-4o to the retrieved chunks — if the
information is not in these documents, the answer is 'not found'. Then it streams.

formatter appends source attribution: filename, page number, chunk index, relevance score.

Every node is independently unit-testable. The graph is debuggable as a diagram. This is
why LangGraph exists — and why it is the right tool here."

---

## [8:00–13:00] Live Demo

**Goal:** Show the actual working system. Speak less, show more. Let the streaming response do the talking.

---

**Pre-demo checklist (do this before the room fills):**
- [ ] Terminal open in backend/ with venv activated
- [ ] `curl http://localhost:8000/health` returns `{"status":"ok","document_count":X}`
- [ ] Sample contracts already ingested
- [ ] Second terminal ready for `curl` commands

---

### Demo Script (step by step)

**Step 1 — Show the health endpoint**
```bash
curl http://localhost:8000/health
```
*Say:* "The system is running. Four contracts are already indexed. Let me show you what they are."

**Step 2 — Briefly describe the sample contracts**
*Say:* "I have four contracts loaded:
- An NDA with TechCorp — English, has GDPR clause
- A service agreement with DataSystems — English, intentionally missing the GDPR clause
- A German service contract with Müller GmbH — fully bilingual pipeline test
- A scanned vendor agreement — JPEG, Tesseract OCR

These are synthetic contracts I generated to cover every scenario from the requirements."

**Step 3 — Cross-contract query: missing GDPR clause**
```bash
curl -s -N -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Which contracts are missing a GDPR data processing clause?"}'
```
*While streaming:* "Watch the tokens appear — this is the SSE stream. The LangGraph agent
is retrieving chunks from all four contracts and reasoning across them simultaneously."

*When complete, point out:*
- "It correctly identified the DataSystems agreement as missing the clause"
- "It cites the specific file and chunk so the legal team can verify directly"
- "It said 'not found' for DataSystems — that is the grounding instruction working"

**Step 4 — Termination clause comparison**
```bash
curl -s -N -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the termination notice periods in these contracts?"}'
```
*Say:* "Now a comparison query. The agent retrieves termination clauses from each contract
and synthesises the answer. Notice the source attribution at the bottom — page numbers and
relevance scores."

**Step 5 — German language query (if time allows)**
```bash
curl -s -N -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Welche Verträge enthalten eine Datenschutzklausel?"}'
```
*Say:* "Same pipeline, German question. The bge-m3 embedding model is natively multilingual —
no translation step, no separate German model."

**Step 6 — Show the Swagger UI (optional, if interviewer seems technical)**
*Open browser at* `http://localhost:8000/docs`
*Say:* "FastAPI generates this automatically from the Pydantic models. Every endpoint is
self-documenting. This is what a frontend developer or a SharePoint integration would
consume."

---

## [13:00–15:00] Production Path and Adoption Strategy

**Goal:** Show you have thought beyond the demo. Connect every component to Riverty's Azure stack.

---

"Everything I have shown runs on a laptop. Let me show you how each piece maps to production.

[Show the table from evaluation_shareable.md]

ChromaDB becomes Azure AI Search — same retrieval logic, but with hybrid keyword-plus-vector
search, RBAC, and horizontal scale. That is one line of code in pipeline.py.

The OpenAI API becomes Azure OpenAI — same SDK, same model names, but data stays within the
Azure tenant. For legal contracts, that is not optional — it is a compliance requirement.

Tesseract becomes Azure Document Intelligence for production-quality OCR on handwritten or
low-quality scans.

Local disk becomes Azure Blob Storage with versioning and legal hold for compliant contract copies.

The whole stack deploys to Azure Container Apps. Terraform modules for all of this would take
2–3 days to write properly.

And for adoption: I would not do a big-bang rollout. Phase one is a two-week pilot with two
or three people from the legal team, pre-loaded with your 50 most-referenced contracts.
We measure time saved per review. We tune the similarity threshold based on real feedback.
Phase two refines query templates and integrates with SharePoint so new contracts ingest
automatically. Phase three is full rollout with Azure AD SSO so there is no separate login —
your team uses their existing Riverty credentials."

---

## [15:00–17:00] Q&A Buffer

**Goal:** Have three topics you can go deeper on without preparation.

---

### Topic A — If they ask about scale
"Let me walk you through what changes at 10,000 contracts vs. 4..."
→ Azure AI Search scales horizontally; async ingestion queue via Azure Service Bus;
  batch embedding already implemented; deduplication on file hash prevents re-processing.

### Topic B — If they ask about security and GDPR
"Five layers, and the most important is the first..."
→ Azure OpenAI (data stays in tenant) → private endpoints on Blob → Key Vault for secrets
  → Azure AD for auth → audit log for every query → right to erasure via DELETE endpoint.

### Topic C — If they ask to go deeper on LangGraph
"Let me draw the state transitions..."
→ Walk through AgentState TypedDict fields; show how query_type from router controls
  which prompt template the reasoner uses; explain how astream_events feeds the SSE endpoint.

---

## Key Technical Terms to Use Naturally

- "Retrieval-Augmented Generation" — say the full term once, use "RAG" after
- "vector embeddings" — "we turn each clause into a 1024-dimensional vector"
- "semantic similarity" — "not keyword matching — semantic similarity"
- "grounded answers" — "the model is grounded to only the retrieved chunks"
- "Strategy Pattern" — use when explaining swappability
- "state machine" / "graph topology" — use when explaining LangGraph
- "hybrid search" — use when explaining why Azure AI Search beats ChromaDB at scale
- "SSE / Server-Sent Events" — "a standard web protocol, works through every proxy"

---

## Timing Reminders

| Section | Target | Hard Stop |
|---|---|---|
| Problem | 2 min | 2:00 |
| Architecture overview | 3 min | 5:00 |
| Technical deep dive | 3 min | 8:00 |
| Live demo | 5 min | 13:00 |
| Production + adoption | 2 min | 15:00 |
| Q&A buffer | 2 min | 17:00 |

If you are running long: cut Step 5 (German query) and the Swagger UI step from the demo.
If you are running short: go deeper on the LangGraph node walk-through in the technical section.
