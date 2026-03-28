"""
agent.py — LangGraph agent for legal contract question answering.
Implements a 4-node state machine: query_router → retriever → reasoner → formatter.
Answers are grounded exclusively in retrieved contract chunks; hallucination is
prevented by the system prompt. Streams tokens via generator for SSE delivery.
"""

# TODO: implemented in Prompt 1B
