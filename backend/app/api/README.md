# api/ — HTTP Boundary Layer

This folder is the HTTP boundary of the application. It is the only layer
that knows about HTTP concepts (status codes, headers, multipart uploads, SSE).

## The One Rule
Routes ONLY do three things:
1. Validate and parse input (Pydantic handles this automatically)
2. Call the appropriate service function from `etl/` or `rag/`
3. Return the response

**No database calls. No AI calls. No file reading. No business logic.**

## Why This Separation Matters
If the team later wants to move from REST to GraphQL, or add a CLI interface,
the entire `etl/` and `rag/` layer remains untouched — only this folder changes.

Routes are the thinnest possible layer: HTTP in → service call → HTTP out.

## Error Handling Pattern

All route handlers follow this pattern:

```python
try:
    result = await service_function(request)
    return result
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))   # bad input
except Exception as e:
    raise HTTPException(status_code=500, detail="Internal error")  # everything else
```

`ValueError` signals a known bad-input scenario (unsupported file type, empty query).
All other exceptions are unexpected and return a generic 500 to avoid leaking internals.
