#!/usr/bin/env bash
# run_rag.sh — Interactive Q&A against already-ingested documents.
#
# Usage:
#   bash backend/run_rag.sh                        # interactive loop
#   bash backend/run_rag.sh --query "your question" # one-shot then exit

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Activate venv ────────────────────────────────────────────────────────────
if   [ -f "../.venv/bin/activate" ]; then source "../.venv/bin/activate"
elif [ -f ".venv/bin/activate" ];    then source ".venv/bin/activate"
elif [ -f "venv/bin/activate" ];     then source "venv/bin/activate"
elif [ -f "riverty/bin/activate" ];  then source "riverty/bin/activate"
else
  echo "ERROR: No virtual environment found."
  echo "Run: python -m venv venv && pip install -r requirements.txt"
  exit 1
fi

# ── Shared logging setup (inline Python snippet reused in both modes) ─────────
_LOGGING_SETUP='
import logging
# Terminal: WARNING+ only (no noise during Q&A)
# File rag.log: full DEBUG — tail -f backend/rag.log to monitor internals
_file_handler = logging.FileHandler("rag.log", encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s"))
_stream_handler = logging.StreamHandler()
_stream_handler.setLevel(logging.WARNING)
logging.basicConfig(level=logging.DEBUG, handlers=[_file_handler, _stream_handler])
'

# ── Parse arguments ───────────────────────────────────────────────────────────
CUSTOM_QUERY=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --query) CUSTOM_QUERY="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── One-shot mode ─────────────────────────────────────────────────────────────
if [ -n "$CUSTOM_QUERY" ]; then
  python - <<PYEOF
import asyncio
${_LOGGING_SETUP}
from app.rag.retriever import ContractRetriever
from app.rag.agent import stream_query

QUESTION = """${CUSTOM_QUERY}"""

print(f"\n  Question: {QUESTION}\n")
retriever = ContractRetriever()
results = retriever.retrieve(QUESTION, top_k=8)
print(f"  Retrieved {len(results)} chunk(s):\n")
for i, r in enumerate(results):
    print(f"    [{i+1}] {r['source_file']}  chunk {r['chunk_index']}  score={r['similarity_score']:.2f}")
    print(f"         {r['text'][:80].strip()}...")
    print()

print("  Answer:\n")
async def run():
    print("  ", end="", flush=True)
    async for token in stream_query(QUESTION):
        if token == "[DONE]":
            print("\n")
        else:
            print(token, end="", flush=True)

asyncio.run(run())
PYEOF
  exit 0
fi

# ── Interactive loop ──────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Riverty RAG — Interactive Q&A"
echo "  Type your question and press Enter. Type 'exit' to quit."
echo "  (Internal logs → backend/rag.log)"
echo "============================================================"
echo ""

while true; do
  printf "  Your question: "
  read -r QUESTION

  if [ -z "$QUESTION" ]; then
    continue
  fi

  if [ "$QUESTION" = "exit" ] || [ "$QUESTION" = "quit" ] || [ "$QUESTION" = "q" ]; then
    echo ""
    echo "  Goodbye."
    echo ""
    break
  fi

  python - <<PYEOF
import asyncio
${_LOGGING_SETUP}
from app.rag.retriever import ContractRetriever
from app.rag.agent import stream_query

QUESTION = """${QUESTION}"""

retriever = ContractRetriever()
results = retriever.retrieve(QUESTION, top_k=8)
print(f"\n  Retrieved {len(results)} chunk(s) from your documents.\n")
for i, r in enumerate(results):
    print(f"    [{i+1}] {r['source_file']}  chunk {r['chunk_index']}  score={r['similarity_score']:.2f}")

print("\n  Answer:\n")
async def run():
    print("  ", end="", flush=True)
    async for token in stream_query(QUESTION):
        if token == "[DONE]":
            print("\n")
        else:
            print(token, end="", flush=True)

asyncio.run(run())
PYEOF

done
