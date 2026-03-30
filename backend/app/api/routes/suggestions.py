"""
suggestions.py — GET /api/suggested-questions route handler.
Samples the vector store and uses the LLM to generate 4 questions that
can actually be answered from the indexed content.
"""
import logging
import random

import chromadb
from fastapi import APIRouter
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

_COLLECTION_NAME = "riverty_contracts"

_SUGGESTION_PROMPT = """\
You are helping users query a document database. Below are excerpts from the \
indexed documents. Generate exactly 4 short, specific questions (max 12 words each) \
that a user could ask and get a useful answer from these documents.

Rules:
- Each question must be answerable from the content shown
- Write questions a non-technical user would naturally ask
- One question per line, no numbering, no bullet points

Document excerpts:
{excerpts}

Output 4 questions, one per line:"""


class SuggestedQuestionsResponse(BaseModel):
    """Response model for the suggested questions endpoint."""
    questions: list[str]


@router.get("/suggested-questions", response_model=SuggestedQuestionsResponse)
async def get_suggested_questions() -> SuggestedQuestionsResponse:
    """Generate suggested questions from a random sample of indexed content.

    Samples up to 10 chunks from ChromaDB, sends them to GPT-4o, and returns
    4 questions that are answerable from the actual indexed documents.

    Returns:
        SuggestedQuestionsResponse with a list of 4 question strings.
        Falls back to empty list if the collection is empty or LLM call fails.
    """
    try:
        client_db = chromadb.PersistentClient(path=settings.chroma_persist_path)
        collection = client_db.get_or_create_collection(_COLLECTION_NAME)
        total = collection.count()

        if total == 0:
            logger.info("suggested-questions: collection empty, returning []")
            return SuggestedQuestionsResponse(questions=[])

        # Sample up to 10 random chunks for broad coverage
        sample_size = min(10, total)
        offset = random.randint(0, max(0, total - sample_size))
        result = collection.get(
            include=["documents"],
            limit=sample_size,
            offset=offset,
        )

        excerpts = "\n\n---\n\n".join(
            doc[:300] for doc in result["documents"] if doc.strip()
        )

        llm = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await llm.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": _SUGGESTION_PROMPT.format(excerpts=excerpts)}],
            temperature=0.4,
            max_tokens=200,
        )

        raw = response.choices[0].message.content or ""
        questions = [q.strip() for q in raw.strip().splitlines() if q.strip()][:4]

        logger.info("suggested-questions: generated %d questions", len(questions))
        return SuggestedQuestionsResponse(questions=questions)

    except Exception as exc:  # noqa: BLE001
        logger.warning("suggested-questions: failed — %s", exc)
        return SuggestedQuestionsResponse(questions=[])
