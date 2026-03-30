# routes/ — API Route Handlers

## Endpoints

| File | Method | Path | Accepts | Returns |
|---|---|---|---|---|
| `health.py` | GET | `/health` | — | `{status, document_count, mode}` |
| `ingest.py` | POST | `/api/ingest` | multipart file upload | `{filename, chunks, status}` |
| `query.py` | POST | `/api/query` | `{question: str}` | SSE stream (MODE 3 cross-DB) |
| `files.py` | GET | `/api/files/{filename}` | — | FileResponse (PDF/image) |
| `suggestions.py` | GET | `/api/suggested-questions` | — | `{questions: list[str]}` |
| `analyze.py` | POST | `/api/analyze` | file + question + mode | SSE stream (MODE 1/2 temp docs) |
| `compliance.py` | POST | `/api/compliance` | file + guidelines? | `{compliant, violations, explanation}` |

## Three Analysis Modes

| Mode | Endpoint | Description | DB access |
|---|---|---|---|
| MODE 1 (single) | `POST /api/analyze?mode=single` | Q&A on uploaded doc only | None — doc never indexed |
| MODE 1 (compliance) | `POST /api/compliance` | Evaluate doc against guidelines | None — doc never indexed |
| MODE 2 (compare) | `POST /api/analyze?mode=compare` | Compare uploaded doc vs DB | Read-only (retrieval only) |
| MODE 3 (cross-DB) | `POST /api/query` | Query across all stored contracts | Read (grouped by document) |

## Why Server-Sent Events (SSE) for query.py?

Legal contract queries through GPT-4o take 3–5 seconds to complete.
Streaming the response token-by-token gives the user immediate feedback instead
of a blank screen. SSE was chosen over WebSocket for these reasons:

| Consideration | SSE | WebSocket |
|---|---|---|
| Communication direction | Server → Client only | Bidirectional |
| Fit for this use case | Perfect — query is fire-and-forget | Overkill |
| Proxy/firewall compatibility | Works everywhere (plain HTTP) | Can be blocked |
| Browser support | Native, no library needed | Native |
| Connection lifecycle | Simple — opens, streams, closes | Requires ping/pong, reconnect logic |

For a legal query tool where the client sends one question and receives one streamed
answer, SSE is the correct choice. WebSocket would add complexity with zero benefit.

## SSE Stream Format

```
data: {"token": "Based"}\n\n
data: {"token": " on"}\n\n
data: {"token": " the"}\n\n
...
data: [DONE]\n\n
```

Each `data:` line is one token from the LLM. The client appends tokens to the display.
`data: [DONE]` signals the stream is complete.
