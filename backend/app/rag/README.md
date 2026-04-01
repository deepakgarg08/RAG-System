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
Pure dense vector retrieval from ChromaDB. Minimum similarity threshold: `0.40`.
Used internally by `hybrid_retriever.py`. Not called directly by the agent.

### `hybrid_retriever.py`
**Primary retriever used by the agent.** Combines two retrieval methods via Reciprocal Rank Fusion:
- **Dense (vector)**: semantic similarity via bge-m3 embeddings — handles paraphrased queries
- **BM25 (keyword)**: exact term matching over an in-memory index — handles company names, clause numbers, legal abbreviations like `§12`

The BM25 index is built lazily from ChromaDB chunk texts and cached until new documents are ingested.
RRF merges the two ranked lists without requiring comparable score scales.
**Production swap**: Azure AI Search runs BM25 + vector natively in one API call — this file is replaced by the Azure retriever.

### `reranker.py`
Two post-retrieval quality filters applied after hybrid retrieval:
- **`rerank()`**: cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) rescores top candidates by reading query + chunk *together* — more accurate than cosine similarity. Falls back gracefully if the model fails to load.
- **`mmr_filter()`**: Maximal Marginal Relevance removes near-duplicate chunks so GPT-4o sees diverse, non-redundant context. Uses Jaccard token overlap to measure inter-chunk similarity.

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
  1. HybridRetriever fetches top_k*2 candidates (BM25 + dense, RRF merged)
  2. CrossEncoder reranker rescores candidates by reading query+chunk together
  3. MMR filter removes near-duplicate chunks → final top_k diverse, relevant chunks
     ↓
[reasoner]
  GPT-4o generates answer using ONLY the retrieved chunks as context.
  System prompt enforces: "If the answer is not in the provided chunks,
  say 'Not found in the provided contracts.' Do not invent information."
  For find_missing queries: chunks are grouped by document for per-contract verdicts.
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
