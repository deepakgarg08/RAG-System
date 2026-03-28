"""
query.py — POST /api/query route handler.
Accepts {question: str}, delegates to the RAG agent, and streams the answer
back to the client as Server-Sent Events (SSE). No AI logic here.
"""
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models import QueryRequest
from app.rag.agent import stream_query

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query")
async def query_contracts(request: QueryRequest) -> StreamingResponse:
    """Stream a legal contract query answer via Server-Sent Events.

    Delegates to the LangGraph agent which retrieves relevant contract chunks
    and generates a grounded answer.  Tokens are yielded one by one as they
    arrive from GPT-4o, so the frontend can display them progressively.

    Args:
        request: QueryRequest containing the user's question (3–500 chars).

    Returns:
        StreamingResponse with media type "text/event-stream".  Each line is
        formatted as ``data: <token>\\n\\n``, terminated by ``data: [DONE]\\n\\n``.
    """
    logger.info("query_contracts: question=%r", request.question)

    async def event_generator():
        async for token in stream_query(request.question):
            if token == "[DONE]":
                yield "data: [DONE]\n\n"
            else:
                yield f"data: {token}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
            "Connection": "keep-alive",
        },
    )
