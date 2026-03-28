# docs/ — Project Documentation

## Document Index

| File | Description |
|---|---|
| [architecture.md](architecture.md) | System architecture overview — components, boundaries, data stores |
| [decisions.md](decisions.md) | Architecture Decision Records — why each key choice was made |
| [data-flow.md](data-flow.md) | End-to-end trace of a contract from upload to query answer |
| [azure-services.md](azure-services.md) | Production Azure service mapping and configuration guide |
| [setup.md](setup.md) | Step-by-step local setup instructions |

## Recommended Reading Order for a New Team Member

1. **[architecture.md](architecture.md)** — understand the big picture: what the system does
   and how the major components fit together
2. **[decisions.md](decisions.md)** — understand *why* each choice was made: LangGraph vs
   plain LangChain, ChromaDB vs Azure AI Search, SSE vs WebSocket, etc.
3. **[data-flow.md](data-flow.md)** — trace a real contract from upload through ETL to a
   query answer, with concrete data at each step
4. **[azure-services.md](azure-services.md)** — understand the production path: what each
   demo component maps to in Azure, and how to migrate
5. **[setup.md](setup.md)** — run it locally: prerequisites, environment setup, first run

## Keeping Docs Up to Date
- `setup.md` must be updated whenever setup steps change
- `decisions.md` must be updated when a new significant technical decision is made
  (use the `write-adr` skill for this)
- `azure-services.md` is updated when production services are provisioned
