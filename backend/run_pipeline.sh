#!/usr/bin/env bash
# run_pipeline.sh — Single entry point: ETL + optional query test.
#
# What this script does:
#   1. Activates the Python virtual environment
#   2. Runs ETL on every .pdf / .jpg / .jpeg / .png in uploads/
#   3. Shows what is now stored in ChromaDB
#   4. Runs a test query through the full RAG + LLM pipeline
#
# Usage:
#   bash backend/run_pipeline.sh                        # ingest + test query
#   bash backend/run_pipeline.sh --ingest-only          # skip the query step
#   bash backend/run_pipeline.sh --query "your question" # custom query

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

# ── Parse arguments ───────────────────────────────────────────────────────────
INGEST_ONLY=false
CUSTOM_QUERY=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --ingest-only) INGEST_ONLY=true; shift ;;
    --query)       CUSTOM_QUERY="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# API_URL="http://localhost:8000/api/ingest-all

API_URL="http://localhost:8000/api/ingest-all?force=true"
HEALTH_URL="http://localhost:8000/docs"   # simple readiness check

# ── Check if API is reachable ────────────────────────────────────────────────
if ! curl -s "$HEALTH_URL" > /dev/null; then
  echo "  FastAPI server not running. Starting it..."
  uvicorn app.main:app --port 8000 > /dev/null 2>&1 &
  SERVER_PID=$!

  echo "  Waiting for server to be ready..."

  for i in {1..20}; do
    if curl -s "$HEALTH_URL" > /dev/null; then
      echo "  Server is ready ✅"
      break
    fi
    sleep 1
  done
fi

echo ""
echo "  Calling ingestion endpoint..."
echo "  $API_URL"
echo ""

RESPONSE=$(curl -s -X POST "$API_URL")

if [ -z "$RESPONSE" ]; then
  echo "  ERROR: No response from ingestion API."
  echo "  Possible causes:"
  echo "   - Server still starting"
  echo "   - Endpoint crashed"
  echo "   - Wrong route path"
  exit 1
fi

echo "  Ingestion Result:"
echo "$RESPONSE" | python -m json.tool

# ── Step 3: RAG + LLM query ───────────────────────────────────────────────────
if [ "$INGEST_ONLY" = true ]; then
  echo ""
  echo "  --ingest-only flag set — skipping query step."
  echo ""
  exit 0
fi

# If a one-shot query was passed, run it and exit
if [ -n "$CUSTOM_QUERY" ]; then
  echo ""
  echo "============================================================"
  echo "  STEP 3 — RAG + LLM QUERY"
  echo "  Embed question → Retrieve chunks → GPT-4o answers"
  echo "============================================================"

  python - <<PYEOF
import asyncio
from app.rag.retriever import ContractRetriever
from app.rag.agent import stream_query

QUESTION = """${CUSTOM_QUERY}"""

print(f"\n  Question: {QUESTION}")

retriever = ContractRetriever()
results = retriever.retrieve(QUESTION, top_k=3)
print(f"\n  Retrieved {len(results)} chunk(s):\n")
for i, r in enumerate(results):
    print(f"    [{i+1}] {r['source_file']}  chunk {r['chunk_index']}  score={r['similarity_score']}")
    print(f"         {r['text'][:80].strip()}...")
    print()

print("  Answer (from GPT-4o):\n")
async def run():
    print("  ", end="", flush=True)
    async for token in stream_query(QUESTION):
        if token == "[DONE]":
            print()
        else:
            print(token, end="", flush=True)

asyncio.run(run())
PYEOF
  exit 0
fi

# ── Interactive Q&A loop ──────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  STEP 3 — INTERACTIVE Q&A"
echo "  Type your question and press Enter. Type 'exit' to quit."
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
import asyncio, logging, os
os.makedirs("logs", exist_ok=True)
# Q&A mode: suppress INFO logs to terminal — write them to logs/rag.log instead
logging.basicConfig(
    level=logging.WARNING,
    handlers=[
        logging.StreamHandler(),                          # WARNING+ to terminal
        logging.FileHandler("logs/rag.log", encoding="utf-8"), # INFO+ to file
    ]
)
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("app").setLevel(logging.INFO)
# redirect app.* INFO to file only
for h in logging.getLogger().handlers:
    if isinstance(h, logging.FileHandler):
        h.setLevel(logging.DEBUG)
    else:
        h.setLevel(logging.WARNING)

from app.rag.retriever import ContractRetriever
from app.rag.agent import stream_query

QUESTION = """${QUESTION}"""

retriever = ContractRetriever()
results = retriever.retrieve(QUESTION, top_k=3)
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
