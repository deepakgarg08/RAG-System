"""
agent.py — LangGraph agent for legal contract question answering.
Implements a 4-node state machine: query_router → retriever → reasoner → formatter.
Answers are grounded exclusively in retrieved contract chunks; hallucination is
prevented by the system prompt. Streams tokens via async generator for SSE delivery.
"""
import logging
from typing import TypedDict, Annotated, AsyncGenerator

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from openai import AsyncOpenAI

from app.config import settings
from app.rag.retriever import ContractRetriever

logger = logging.getLogger(__name__)

# ============================================================
# DEMO MODE: OpenAI API — direct API key, simple setup
# PRODUCTION SWAP → Azure OpenAI (AWS: Bedrock):
#   Change client initialisation below:
#   FROM: AsyncOpenAI(api_key=settings.openai_api_key)
#   TO:   AsyncAzureOpenAI(
#             api_key=settings.azure_openai_api_key,
#             azure_endpoint=settings.azure_openai_endpoint,
#             api_version=settings.azure_openai_api_version,
#         )
#   Model name stays the same: "gpt-4o"
#   Why Azure OpenAI for production: data never leaves Microsoft tenant,
#   required for legal document compliance at Riverty
# ============================================================

_LLM_MODEL = "gpt-4o"

_ROUTER_PROMPT = """\
Classify this legal contract query into exactly one category:
- find_clause: user wants to know if a specific clause exists
- find_missing: user wants contracts that DON'T have something
- compare: user wants to compare multiple contracts
- update_name: user wants to find contracts with a specific company name

Query: {question}
Respond with only the category name."""

_REASONER_SYSTEM = """\
You are a legal document analyst for Riverty GmbH.
Answer ONLY using the provided contract excerpts below.
Do NOT include any source references or citations in your answer text — sources are appended automatically.
If the information is not in the provided excerpts, say exactly:
"This information was not found in the uploaded contracts."
Never guess or use outside knowledge.

Contract excerpts:
{context}"""


class AgentState(TypedDict):
    """Typed state passed between every node in the LangGraph graph."""

    question: str
    query_type: str          # classified intent from query_router
    retrieved_chunks: list   # from retriever_node
    answer: str              # final formatted answer
    sources: list            # list of unique source contract names


def _build_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into a context string for the reasoner.

    Args:
        chunks: List of retriever result dicts.

    Returns:
        Multi-line string with source labels and chunk text.
    """
    parts: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        source = chunk.get("source_file", "unknown")
        score = chunk.get("similarity_score", 0.0)
        text = chunk.get("text", "")
        parts.append(f"[{i}] Source: {source} (relevance: {score:.2f})\n{text}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

async def query_router(state: AgentState) -> dict:
    """Classify the user question into a query type category.

    Args:
        state: Current agent state containing the user question.

    Returns:
        Partial state update with query_type set.
    """
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=_LLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": _ROUTER_PROMPT.format(question=state["question"]),
            }
        ],
        temperature=0,
        max_tokens=20,
    )
    query_type = response.choices[0].message.content.strip()
    logger.info("query_router: classified '%s' → %s", state["question"], query_type)
    return {"query_type": query_type}


def retriever_node(state: AgentState) -> dict:
    """Retrieve semantically relevant contract chunks for the question.

    Args:
        state: Current agent state containing the user question.

    Returns:
        Partial state update with retrieved_chunks (and answer if none found).
    """
    retriever = ContractRetriever()
    chunks = retriever.retrieve(
        query=state["question"],
        top_k=settings.top_k_results,
    )
    if not chunks:
        logger.warning("retriever_node: no chunks found for query '%s'", state["question"])
        return {
            "retrieved_chunks": [],
            "answer": "No relevant contracts found.",
        }
    logger.info("retriever_node: retrieved %d chunks", len(chunks))
    return {"retrieved_chunks": chunks}


async def reasoner(state: AgentState) -> dict:
    """Generate a grounded answer using GPT-4o and the retrieved chunks.

    Only uses retrieved contract excerpts — never invents information.

    Args:
        state: Current agent state with question and retrieved_chunks.

    Returns:
        Partial state update with answer set.
    """
    # Short-circuit if retriever already set a terminal answer
    if state.get("answer"):
        return {}

    context = _build_context(state["retrieved_chunks"])
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=_LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": _REASONER_SYSTEM.format(context=context),
            },
            {
                "role": "user",
                "content": state["question"],
            },
        ],
        temperature=0.1,
        stream=True,
    )
    tokens: list[str] = []
    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            tokens.append(delta)
    answer = "".join(tokens)
    logger.info("reasoner: generated answer (%d chars)", len(answer))
    return {"answer": answer}


def formatter(state: AgentState) -> dict:
    """Append detailed source citations to the answer and collect unique source names.

    Each source line includes file name, page number, chunk position within the
    document, and similarity score — giving legal reviewers a precise reference
    to locate the exact passage in the original document.

    Format:
        **Sources:**
        • contract.pdf — page 3, chunk 4/21 (relevance: 0.87)
        • contract.pdf — page 5, chunk 7/21 (relevance: 0.74)

    Args:
        state: Current agent state with answer and retrieved_chunks.

    Returns:
        Partial state update with answer (amended) and sources list.
    """
    chunks = state.get("retrieved_chunks", [])
    answer = state.get("answer", "")

    if not chunks or not answer or answer == "No relevant contracts found.":
        unique_sources = list(
            dict.fromkeys(c["source_file"] for c in chunks if c.get("source_file"))
        )
        logger.info("formatter: sources=%r", unique_sources)
        return {"answer": answer, "sources": unique_sources}

    # Build one attribution line per retrieved chunk (deduplicated by chunk_index)
    seen: set[str] = set()
    source_lines: list[str] = []
    unique_sources: list[str] = []

    for c in chunks:
        source_file = c.get("source_file", "unknown")
        chunk_index = c.get("chunk_index", 0)
        total_chunks = c.get("total_chunks", 0)
        page_number = c.get("page_number", 1)
        score = c.get("similarity_score", 0.0)

        dedup_key = f"{source_file}:{chunk_index}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        chunk_ref = f"{chunk_index + 1}/{total_chunks}" if total_chunks else str(chunk_index + 1)
        source_lines.append(
            f"  • {source_file} — page {page_number}, chunk {chunk_ref} (relevance: {score:.2f})"
        )

        if source_file not in unique_sources:
            unique_sources.append(source_file)

    sources_block = "\n".join(source_lines)
    answer = f"{answer}\n\n**Sources:**\n{sources_block}"

    logger.info("formatter: %d source references from %d files", len(source_lines), len(unique_sources))
    return {"answer": answer, "sources": unique_sources}


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_agent():
    """Build and compile the LangGraph state machine.

    Returns:
        Compiled LangGraph app ready for invocation or streaming.
    """
    graph = StateGraph(AgentState)
    graph.add_node("router", query_router)
    graph.add_node("retriever", retriever_node)
    graph.add_node("reasoner", reasoner)
    graph.add_node("formatter", formatter)

    graph.set_entry_point("router")
    graph.add_edge("router", "retriever")
    graph.add_edge("retriever", "reasoner")
    graph.add_edge("reasoner", "formatter")
    graph.add_edge("formatter", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Public streaming interface
# ---------------------------------------------------------------------------

async def stream_query(question: str) -> AsyncGenerator[str, None]:
    """Stream answer tokens for a user question via the LangGraph agent.

    Invokes the full agent graph, then yields the answer word-by-word so the
    SSE endpoint can stream it to the frontend progressively.

    Args:
        question: Plain-English question about the uploaded contracts.

    Yields:
        Individual word tokens, then "[DONE]" when the stream is complete.
    """
    agent = build_agent()
    initial_state: AgentState = {
        "question": question,
        "query_type": "",
        "retrieved_chunks": [],
        "answer": "",
        "sources": [],
    }

    result = await agent.ainvoke(initial_state)
    answer = result.get("answer", "No relevant contracts found.")

    # Yield word by word so the frontend receives progressive output
    for word in answer.split(" "):
        yield word + " "

    yield "[DONE]"
