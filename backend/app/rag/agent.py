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
from openai import AsyncOpenAI, AsyncAzureOpenAI

from app.config import settings
from app.rag.retriever import ContractRetriever

logger = logging.getLogger(__name__)

# ============================================================
# DEMO MODE: OpenAI API — direct API key, simple setup
# PRODUCTION SWAP → Azure OpenAI (AWS: Bedrock):
#   Set APP_ENV=production in .env — no code changes required.
#   _get_llm_client() and _LLM_MODEL branch automatically.
#   Why Azure OpenAI: data never leaves Microsoft tenant,
#   required for legal document compliance at Riverty
# ============================================================


def _get_llm_client() -> AsyncOpenAI | AsyncAzureOpenAI:
    """Return the correct async LLM client based on APP_ENV.

    Returns:
        AsyncAzureOpenAI when APP_ENV=production (data stays in Azure tenant).
        AsyncOpenAI otherwise (demo/development — direct OpenAI API).
    """
    if settings.app_env == "production":
        # ============================================================
        # PRODUCTION: Azure OpenAI
        # AWS equivalent: Amazon Bedrock
        # Set APP_ENV=production in .env to activate
        # ============================================================
        return AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
    # ============================================================
    # DEMO: Plain OpenAI API
    # Switch to production: set APP_ENV=production in .env
    # ============================================================
    return AsyncOpenAI(api_key=settings.openai_api_key)


def _get_model_name() -> str:
    """Return the deployment/model name for the active environment.

    Returns:
        Azure deployment name in production, 'gpt-4o' in demo.
    """
    if settings.app_env == "production":
        return settings.azure_openai_deployment_name
    return "gpt-4o"

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

Write in clear, natural prose. Insert 1-2 line breaks between paragraphs.
Each distinct idea must be its own paragraph. Never write fragmented or chunked text.

STRICTLY FORBIDDEN IN YOUR ANSWER:
- chunk_index, total_chunks, char_count
- raw metadata or internal IDs
- relevance scores inline with text
- Any mention of "chunk" or "embedding"

Contract excerpts:
{context}"""

# Documents the output contract for the formatter node.
# The formatter itself is pure Python — no extra LLM call needed.
_FORMATTER_SYSTEM_PROMPT = """
You are responsible for transforming retrieved RAG outputs into a clean,
user-friendly response suitable for legal and business users.

ANSWER FORMATTING RULES:
- Combine all retrieved chunks into a single coherent answer
- Remove duplicate or overlapping content
- Write in clear, natural prose
- Insert 1-2 line breaks between paragraphs
- Each distinct idea must be its own paragraph
- Never write fragmented or chunked text
- If the answer was not found in the documents, say exactly:
  "This information was not found in the uploaded contracts."

STRICTLY FORBIDDEN IN OUTPUT:
- chunk_index, total_chunks, char_count
- raw metadata dictionaries
- text previews or internal IDs
- relevance scores shown inline with text
- Any mention of "chunk" or "embedding"

SOURCE DISPLAY FORMAT:
After the answer, list sources using this exact format:

Sources:
[●] filename.pdf (Page X)

Rules for sources:
- One line per unique file
- If multiple chunks came from same file, merge pages: (Page 1, 3, 5)
- Use colored dot based on highest relevance score from that file:
    Green dot  → relevance ≥ 65%  → use unicode ● with note "high relevance"
    Amber dot  → relevance 50-64% → use unicode ● with note "medium relevance"
    Grey dot   → relevance < 50%  → use unicode ● with note "low relevance"
- Each source must be a clickable link in this format:
    /files/{filename}#page={page_number}
- Do NOT show raw relevance percentages unless they clearly add value
- Do NOT show chunk numbers

OUTPUT STRUCTURE — always follow this exactly:
{answer paragraphs}

Sources:
[●] filename.pdf (Page X)
"""


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
    client = _get_llm_client()
    response = await client.chat.completions.create(
        model=_get_model_name(),
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
    client = _get_llm_client()
    response = await client.chat.completions.create(
        model=_get_model_name(),
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


def _relevance_dot(score: float) -> str:
    """Return a relevance dot indicator string based on similarity score.

    Args:
        score: Cosine similarity score in [0, 1].

    Returns:
        Unicode dot with relevance label:
          ● high relevance   (score ≥ 0.65)
          ● medium relevance (score 0.50–0.64)
          ● low relevance    (score < 0.50)
    """
    if score >= 0.65:
        return "● high relevance"
    if score >= 0.50:
        return "● medium relevance"
    return "● low relevance"


def formatter(state: AgentState) -> dict:
    """Build clean source citations grouped by file and append to the answer.

    Groups retrieved chunks by source_file, merges page numbers per file,
    tracks the highest relevance score per file, and assigns a coloured dot
    indicator. Builds clickable /files/{filename}#page={N} links.

    No chunk-level metadata (chunk_index, char_count, etc.) appears in output.

    Format:
        {answer prose}

        Sources:
        ● high relevance  contract.pdf (Page 1, 3)  /files/contract.pdf#page=1

    Args:
        state: Current agent state with answer and retrieved_chunks.

    Returns:
        Partial state update with answer (amended) and sources list.
    """
    chunks = state.get("retrieved_chunks", [])
    answer = state.get("answer", "")

    if not chunks or not answer or answer == "No relevant contracts found.":
        unique_sources = list(
            dict.fromkeys(c.get("source_file", "") for c in chunks if c.get("source_file"))
        )
        logger.info("formatter: no chunks or terminal answer — sources=%r", unique_sources)
        return {"answer": answer, "sources": unique_sources}

    # --- Group chunks by source_file ---
    # file_data maps filename → {"pages": set[int], "best_score": float}
    file_data: dict[str, dict] = {}
    for c in chunks:
        source_file = c.get("source_file", "unknown")
        page_number = c.get("page_number", 1)
        score = c.get("similarity_score", 0.0)

        if source_file not in file_data:
            file_data[source_file] = {"pages": set(), "best_score": 0.0}

        file_data[source_file]["pages"].add(page_number)
        if score > file_data[source_file]["best_score"]:
            file_data[source_file]["best_score"] = score

    # --- Build source lines ---
    source_lines: list[str] = []
    unique_sources: list[str] = list(file_data.keys())

    for filename, data in file_data.items():
        best_score = data["best_score"]
        pages = sorted(data["pages"])
        dot = _relevance_dot(best_score)

        # Page display: single page or comma-separated list
        page_label = ", ".join(str(p) for p in pages)
        page_display = f"Page {page_label}" if len(pages) == 1 else f"Pages {page_label}"

        # Clickable link anchored to first (lowest) page
        first_page = pages[0]
        link = f"/files/{filename}#page={first_page}"

        source_lines.append(f"  {dot}  [{filename} ({page_display})]({link})")

    sources_block = "\n".join(source_lines)
    answer = f"{answer}\n\nSources:\n{sources_block}"

    logger.info(
        "formatter: %d source file(s) referenced",
        len(unique_sources),
    )
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
