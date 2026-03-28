# app/ — Main Application Package

This is the root Python package for the Riverty Contract Review backend.

## Entry Point
`main.py` initialises FastAPI and registers all routers. Start here when tracing
any request through the system.

## Key Rule: Config is the Single Source of Truth
`config.py` is the **only** file that reads from `.env`.
Every other file imports its settings from `config.py`. Never call `os.getenv()`
or `dotenv` anywhere else in the codebase.

## Models
`models.py` contains all Pydantic schemas for API requests and responses.
If a new endpoint needs a new input/output shape, add it here.

## Sub-packages and Their Single Responsibilities

| Package | Responsibility |
|---|---|
| `api/` | HTTP interface layer only — validate input, delegate, return response |
| `etl/` | Document ingestion pipeline — fully decoupled from HTTP layer |
| `rag/` | AI query layer — LangGraph agent, embeddings, retrieval |
| `storage/` | File persistence — swappable local disk vs Azure Blob Storage |

## Dependency Direction
```
api/routes → etl/ and rag/   (routes call services)
etl/ → storage/              (pipeline saves files)
rag/ → embeddings, ChromaDB  (agent queries vector store)
config.py ← everything       (all modules import config)
models.py ← api/routes       (routes use Pydantic models)
```
No circular imports. `api/` never imports from `rag/` internals directly —
it calls service functions exposed at the package level.
