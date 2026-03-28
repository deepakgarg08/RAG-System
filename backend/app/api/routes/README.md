# routes/ — API Route Handlers

## Endpoints

| File | Method | Path | Accepts | Returns |
|---|---|---|---|---|
| `ingest.py` | POST | `/api/ingest` | multipart file upload | `{filename, chunks, status}` |
| `query.py` | POST | `/api/query` | `{question: str}` | Server-Sent Events stream |
| `health.py` | GET | `/health` | — | `{status, document_count, mode}` |

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
