"""
document_analyzer.py — Temporary document analysis without database storage.

Implements two analysis modes for uploaded contracts:

  MODE 1 (single):     Extract text → send directly to LLM.
                       No vector DB access. Document never stored in ChromaDB.
                       Variant: compliance check against predefined guidelines.

  MODE 2 (compare):   Extract text → query ChromaDB to find similar stored
                       contracts → compare uploaded doc vs retrieved docs via LLM.
                       Uploaded doc is used ONLY as a query — never indexed.

The key invariant: temporary documents are processed in memory and discarded
after the response is streamed. The persistent ChromaDB collection is never
modified by any function in this module.
"""
import logging
from typing import AsyncGenerator

from app.config import settings
from app.rag.llm_client import _get_llm_client, _get_model_name
from app.rag.retriever import ContractRetriever
from app.rag.document_grouper import group_by_document, build_grouped_context

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

# MODE 1: Single document Q&A — LLM sees only the uploaded document
_SINGLE_DOC_SYSTEM = """\
You are a legal document analyst for Riverty GmbH.
You are given the FULL TEXT of a single contract document.
Answer the user's question using ONLY the provided document text.
If the answer is not in the document, say exactly:
"This information was not found in the provided document."
Never guess or use outside knowledge.
Write in clear, natural prose.

Document text:
{document_text}"""

# MODE 2: Compare uploaded doc with database contracts
_COMPARE_SYSTEM = """\
You are a legal document analyst for Riverty GmbH.
You are given:
  1. An UPLOADED CONTRACT — the document the user wants to analyse.
  2. SIMILAR CONTRACTS from the existing database — for comparison.

Your task: compare the uploaded contract against the database contracts.
Highlight key differences, missing clauses, and notable similarities.
Focus on legally relevant distinctions (termination, liability, GDPR, governing law).
Use "Uploaded contract" and the exact filename when referencing specific documents.
Write in clear, natural prose.

--- UPLOADED CONTRACT ---
{uploaded_text}

--- DATABASE CONTRACTS ---
{db_context}"""

# Compliance check — structured output format enforced by the prompt
_COMPLIANCE_SYSTEM = """\
You are a legal compliance analyst for Riverty GmbH.
Evaluate the provided contract against the compliance guidelines below.

Return your response in EXACTLY this format (do not add extra sections):

COMPLIANCE STATUS: compliant | not compliant

VIOLATIONS:
- <violation 1> (or "None" if compliant)
- <violation 2>

EXPLANATION:
<2-4 sentences summarising the compliance assessment>

--- GUIDELINES ---
{guidelines}

--- CONTRACT TEXT ---
{document_text}"""

# MODE 3 (database-only): used by agent.py for cross-DB find_missing queries
_MISSING_CLAUSE_SYSTEM = """\
You are a legal document analyst for Riverty GmbH.
You are given excerpts from MULTIPLE contracts stored in the database.
The user wants to know which contracts contain a specific clause or text and which do not.

For EACH document listed, state clearly on its own line:
  "[filename] → contains the clause: <brief quote if found>"
  "[filename] → clause not found in the retrieved excerpts"

If the excerpt is ambiguous, write "[filename] → inconclusive — full review recommended".
Do not guess. Only state what is evident from the provided text.

Contract excerpts grouped by document:
{grouped_context}"""


# ---------------------------------------------------------------------------
# MODE 1: Single document analysis
# ---------------------------------------------------------------------------

async def analyze_single_document(
    document_text: str,
    question: str,
) -> AsyncGenerator[str, None]:
    """Stream an LLM answer about a single uploaded document (MODE 1).

    The document text is passed directly as context. Nothing is stored.
    The generator yields tokens and ends with "[DONE]".

    Args:
        document_text: Full cleaned text extracted from the uploaded file.
        question: The user's question about the document.

    Yields:
        Streamed content tokens from the LLM, then "[DONE]".
    """
    client = _get_llm_client()
    # Truncate to ~12 000 chars to stay within context; full contracts are rarely larger
    system_prompt = _SINGLE_DOC_SYSTEM.format(document_text=document_text[:12_000])

    logger.info(
        "document_analyzer.analyze_single: chars=%d, question=%r",
        len(document_text),
        question,
    )

    response = await client.chat.completions.create(
        model=_get_model_name(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0.1,
        stream=True,
    )

    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta

    yield "[DONE]"


# ---------------------------------------------------------------------------
# MODE 1 variant: Compliance check
# ---------------------------------------------------------------------------

async def check_compliance(
    document_text: str,
    guidelines: str,
) -> dict:
    """Evaluate a document against compliance guidelines (MODE 1 compliance variant).

    Sends the document text and guidelines to the LLM and parses the
    structured response into a typed result dict.

    The document is processed in-memory. Nothing is stored in the database.

    Args:
        document_text: Full cleaned text of the uploaded contract.
        guidelines: Plain-text list of compliance guidelines to check against.

    Returns:
        Dict with keys:
          "compliant":   bool — True if no violations were found
          "violations":  list[str] — specific guideline failures
          "explanation": str — 2-4 sentence plain-language summary
          "raw":         str — raw LLM output (for debugging)
    """
    client = _get_llm_client()
    system_prompt = _COMPLIANCE_SYSTEM.format(
        guidelines=guidelines,
        document_text=document_text[:12_000],
    )

    logger.info(
        "document_analyzer.check_compliance: doc_chars=%d, guidelines_chars=%d",
        len(document_text),
        len(guidelines),
    )

    response = await client.chat.completions.create(
        model=_get_model_name(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Evaluate this contract for compliance."},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content or ""
    logger.info("document_analyzer.check_compliance: raw response (%d chars)", len(raw))
    return _parse_compliance_response(raw)


def _parse_compliance_response(raw: str) -> dict:
    """Parse the structured compliance LLM response into a typed dict.

    Parses the three-section format enforced by _COMPLIANCE_SYSTEM:
      COMPLIANCE STATUS: compliant | not compliant
      VIOLATIONS: - item1 ...
      EXPLANATION: ...

    Args:
        raw: Raw LLM response text.

    Returns:
        Dict with keys: compliant (bool), violations (list[str]),
        explanation (str), raw (str).
    """
    lines = raw.splitlines()
    compliant = True
    violations: list[str] = []
    explanation_lines: list[str] = []
    section: str | None = None

    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()

        if upper.startswith("COMPLIANCE STATUS:"):
            value = stripped.split(":", 1)[-1].strip().lower()
            compliant = "not compliant" not in value

        elif upper.startswith("VIOLATIONS:"):
            section = "violations"

        elif upper.startswith("EXPLANATION:"):
            section = "explanation"
            # Inline text on the same line as the header
            inline = stripped.split(":", 1)[-1].strip()
            if inline:
                explanation_lines.append(inline)

        elif section == "violations" and stripped.startswith("-"):
            item = stripped.lstrip("- ").strip()
            if item.lower() not in ("none", ""):
                violations.append(item)

        elif section == "explanation" and stripped:
            explanation_lines.append(stripped)

    return {
        "compliant": compliant,
        "violations": violations,
        "explanation": " ".join(explanation_lines),
        "raw": raw,
    }


# ---------------------------------------------------------------------------
# MODE 2: Compare uploaded document with database contracts
# ---------------------------------------------------------------------------

async def compare_with_database(
    document_text: str,
    question: str,
) -> AsyncGenerator[str, None]:
    """Stream a comparison between an uploaded doc and stored contracts (MODE 2).

    Uses the first 500 characters of the uploaded document as a semantic query
    to find similar contracts in ChromaDB. The LLM then compares the uploaded
    document against the retrieved contracts.

    The uploaded document is NEVER written to the vector database.

    Args:
        document_text: Full cleaned text of the uploaded contract.
        question: The comparison question from the user.

    Yields:
        Streamed content tokens from the LLM, then "[DONE]".
    """
    retriever = ContractRetriever()
    # Use first 500 chars as a dense summary-style query for best retrieval
    query_text = document_text[:500]
    chunks = retriever.retrieve(query=query_text, top_k=settings.top_k_results)

    if not chunks:
        yield "No similar contracts found in the database for comparison."
        yield "[DONE]"
        return

    grouped = group_by_document(chunks)
    db_context = build_grouped_context(grouped)

    client = _get_llm_client()
    system_prompt = _COMPARE_SYSTEM.format(
        # Each truncated independently so neither side crowds out the other
        uploaded_text=document_text[:6_000],
        db_context=db_context[:6_000],
    )

    logger.info(
        "document_analyzer.compare_with_database: uploaded_chars=%d, db_docs=%d",
        len(document_text),
        len(grouped),
    )

    response = await client.chat.completions.create(
        model=_get_model_name(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0.1,
        stream=True,
    )

    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta

    yield "[DONE]"


# ---------------------------------------------------------------------------
# MODE 3 helper (used by agent.py for find_missing queries)
# ---------------------------------------------------------------------------

def build_missing_clause_context(chunks: list[dict]) -> str:
    """Build document-grouped context for MODE 3 (cross-DB clause search).

    Groups retrieved chunks by document and formats them for the
    _MISSING_CLAUSE_SYSTEM prompt used in agent.py.

    Args:
        chunks: Retrieved chunks from ContractRetriever.

    Returns:
        Formatted context string with one section per document.
    """
    grouped = group_by_document(chunks)
    return build_grouped_context(grouped)


def get_missing_clause_system_prompt(grouped_context: str) -> str:
    """Return the MODE 3 system prompt populated with grouped context.

    Args:
        grouped_context: Output of build_missing_clause_context().

    Returns:
        Formatted system prompt string for the reasoner node.
    """
    return _MISSING_CLAUSE_SYSTEM.format(grouped_context=grouped_context)
