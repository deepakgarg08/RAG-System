"""
query.py — POST /api/query route handler.
Accepts {question: str}, delegates to the RAG agent, and streams the answer
back to the client as Server-Sent Events (SSE). No AI logic here.
"""

# TODO: implemented in Prompt 1B
