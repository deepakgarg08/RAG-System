# Architecture Overview

## System Purpose
Riverty Contract Review is a RAG (Retrieval-Augmented Generation) system that allows
the legal team to upload contracts and ask plain-English questions. The AI answers
using only the content of the uploaded contracts — it never invents information.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
│         FileUpload │ DocumentList │ QueryInput │ StreamingResponse│
└──────────────────────────┬──────────────────┬───────────────────┘
                           │ POST /api/ingest  │ POST /api/query (SSE)
                           ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                               │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐   │
│  │  ingest.py  │  │  query.py   │  │      health.py       │   │
│  └──────┬──────┘  └──────┬──────┘  └──────────────────────┘   │
│         │                │                                       │
│  ┌──────▼──────┐  ┌──────▼──────────────────────────────────┐  │
│  │ ETL Pipeline│  │            RAG Agent (LangGraph)         │  │
│  │             │  │  router → retriever → reasoner → format  │  │
│  │ extract     │  └──────────────────┬────────────────────── ┘  │
│  │ clean       │                     │                           │
│  │ chunk       │              ┌──────▼──────┐                   │
│  │ embed       │              │  ChromaDB   │                   │
│  │ load   ─────┼─────────────►│ (demo)      │                   │
│  └─────────────┘              └─────────────┘                   │
│         │                                                        │
│  ┌──────▼──────┐                                                 │
│  │  Storage    │                                                 │
│  │ (./uploads) │                                                 │
│  └─────────────┘                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Two Data Paths

### Ingest Path (file upload)
`Frontend → POST /api/ingest → ETL Pipeline → ChromaDB + local storage`

### Query Path (question answering)
`Frontend → POST /api/query → LangGraph Agent → ChromaDB retrieval → GPT-4o → SSE stream`

## Key Architectural Principles
- **No business logic in routes** — API layer is purely HTTP translation
- **Strategy Pattern throughout ETL** — every component is swappable
- **Single config source** — only `config.py` reads from `.env`
- **Grounded answers only** — LLM uses retrieved chunks exclusively, no hallucination

## Production Architecture
See [azure-services.md](azure-services.md) for how each component maps to Azure.
