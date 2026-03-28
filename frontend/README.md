# Frontend — Riverty Contract Review

React + TypeScript + Vite web application for the legal team interface.

## Tech Stack
- **React 18** — UI framework
- **TypeScript** — type safety
- **Vite** — build tool and dev server
- **Fetch API / EventSource** — backend communication (no extra HTTP library needed)

## Layout
Two-panel layout designed as a professional legal tool:

```
┌─────────────────────────┬──────────────────────────────┐
│   Document Management   │       Query Interface         │
│                         │                               │
│  [Upload Contract]      │  Ask a question...  [Send]   │
│                         │                               │
│  📄 techcorp_nda.pdf    │  > Does the TechCorp NDA     │
│  📄 datasys_svc.pdf     │    have a GDPR clause?       │
│  📄 mueller_vtg.txt     │                               │
│                         │  Based on the provided       │
│                         │  contracts, the TechCorp     │
│                         │  NDA (Section 7.2) contains… │
│                         │                               │
│                         │  Suggested questions:        │
│                         │  · Which contracts are        │
│                         │    missing a GDPR clause?    │
└─────────────────────────┴──────────────────────────────┘
```

## Key Components

| Component | Responsibility |
|---|---|
| `FileUpload` | Drag-and-drop or browse to upload contracts via POST /api/ingest |
| `DocumentList` | Shows uploaded contracts with status |
| `QueryInput` | Text input + submit button for questions |
| `StreamingResponse` | Renders SSE token stream as progressive text |
| `SuggestedQueries` | Pre-built question buttons for common legal checks |

## Backend Communication
- **File upload:** `POST /api/ingest` — multipart form data
- **Query:** `POST /api/query` — opens EventSource, renders token stream
- **Health check:** `GET /health` — shows document count and mode

## Design Principles
- Professional legal tool — clean, minimal, no animations or flashy UI
- Readable typography — legal text needs to be easy to scan
- Source references displayed inline with answers
- No authentication in demo mode

## How to Run
```bash
npm install
npm run dev    # starts on http://localhost:3000
```

## How to Build for Production
```bash
npm run build       # outputs to dist/
npm run preview     # preview the production build locally
```
