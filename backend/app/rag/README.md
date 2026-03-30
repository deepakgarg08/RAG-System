# rag/ — AI Query Layer

This folder contains the AI query layer. It takes a user's plain-English question,
finds the most relevant contract chunks, and generates a grounded answer with source
references. It never invents information not present in the contracts.

## Components

### `embeddings.py`
Converts text strings to vectors using **BAAI/bge-m3** locally (1024 dimensions, demo)
or **Azure OpenAI text-embedding-3-large** (3072 dimensions, production).
Used both at ingest time (to embed chunks) and query time (to embed the question).

### `retriever.py`
Queries ChromaDB for the top-8 most semantically similar chunks to the embedded question.
Returns chunks with full metadata including `page_number`, `chunk_index`, `total_chunks`,
and `similarity_score`. Minimum similarity threshold: `0.40`.
Top-K is configurable via `TOP_K_RESULTS` in config.

### `agent.py`
LangGraph agent with 4 nodes that process a query as a state machine.
For `find_missing` queries (MODE 3), the reasoner branches to use document-level
grouped context so the LLM can identify which contracts contain or lack a clause.

### `document_grouper.py`
Groups a flat list of retriever chunks by `source_file`. Used by:
- `agent.py` for MODE 3 (find_missing cross-DB queries)
- `document_analyzer.py` for MODE 2 (compare uploaded doc with DB)

### `document_analyzer.py`
Temporary document analysis — uploaded files are processed in-memory and never
stored in the vector database. Provides:
- `analyze_single_document()` — MODE 1: Q&A on the uploaded doc only
- `check_compliance()` — MODE 1 variant: evaluate against guidelines
- `compare_with_database()` — MODE 2: compare uploaded doc vs DB contracts

## Why LangGraph Over Plain LangChain?

| Consideration | LangGraph | Plain LangChain Chain |
|---|---|---|
| Agent flow control | Explicit state machine — full control | Implicit chain — hard to customise |
| Routing | Built-in conditional edges | Requires manual workarounds |
| Debuggability | Each node's input/output is inspectable | Opaque intermediate states |
| Multi-step reasoning | Natural — nodes pass typed state | Awkward — requires custom callbacks |
| Suitability for legal reasoning | High — different query types need different paths | Medium |

LangGraph is the correct choice when the agent needs to make routing decisions
(e.g. "is this a 'find missing clause' query or a 'compare two contracts' query?")
and when each step needs to be traceable for debugging.

## LangGraph Node Responsibilities

```
User question
     ↓
[query_router]
  Classifies intent into one of:
  - "find_clause"       — "Does this contract have a GDPR clause?"
  - "find_missing"      — "Which contracts are missing a termination clause?"
  - "compare"           — "Compare the liability clauses in these two contracts"
  - "update_name"       — "What should change if the company name changes?"
     ↓
[retriever]
  Embeds the question → queries ChromaDB → returns top-5 chunks with metadata
     ↓
[reasoner]
  GPT-4o generates answer using ONLY the retrieved chunks as context
  System prompt enforces: "If the answer is not in the provided chunks,
  say 'Not found in the provided contracts.' Do not invent information."
     ↓
[formatter]
  Structures the final response:
  - Answer text
  - Source references with page, chunk position, and relevance score:
    "contract.pdf — page 3, chunk 4/21 (relevance: 0.87)"
```

## Production Swap Note
```
# ============================================================
# DEMO MODE: OpenAI API — direct API key, simple setup
# PRODUCTION SWAP → Azure OpenAI (AWS: Bedrock):
#   Change client initialisation in embeddings.py and agent.py
#   FROM: OpenAI(api_key=...)
#   TO:   AzureOpenAI(api_key=..., azure_endpoint=..., api_version="2024-02-01")
#   Model names remain the same: "gpt-4o", "text-embedding-3-large"
# ============================================================
```
