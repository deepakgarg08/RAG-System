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

# ── Step 1: ETL ───────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  STEP 1 — ETL PIPELINE"
echo "  Extract → Clean → Chunk → Embed → Store"
echo "============================================================"

python - <<'PYEOF'
import os, sys, logging
from pathlib import Path

# Show INFO logs so you can see chunking, embedding, and chunk IDs
logging.basicConfig(
    level=logging.INFO,
    format="  [%(name)s] %(message)s",
)

SUPPORTED = {".pdf", ".jpg", ".jpeg", ".png"}
upload_dir = Path("uploads")

if not upload_dir.exists():
    print("  uploads/ folder not found — creating it.")
    upload_dir.mkdir(parents=True)

files = [f for f in sorted(upload_dir.iterdir()) if f.suffix.lower() in SUPPORTED]

if not files:
    print(f"  No supported files in uploads/")
    print(f"  Add .pdf / .jpg / .jpeg / .png files there and re-run.")
    sys.exit(0)

from app.etl.pipeline import IngestionPipeline
pipeline = IngestionPipeline()

total_chunks = 0
for f in files:
    print(f"\n  ── {f.name} ──────────────────────────────────────")
    result = pipeline.ingest(str(f.resolve()))
    print(f"  status:          {result['status']}")
    print(f"  language:        {result['language']}")
    print(f"  chars_extracted: {result['chars_extracted']}")
    print(f"  chunks_created:  {result['chunks_created']}")
    if result.get("error"):
        print(f"  error:           {result['error']}")
    total_chunks += result["chunks_created"]

print(f"\n  Done. Total chunks stored this run: {total_chunks}")
PYEOF

# ── Step 2: Show ChromaDB stats ───────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  STEP 2 — CHROMADB: What is stored"
echo "============================================================"

python - <<'PYEOF'
import chromadb
from app.config import settings

client = chromadb.PersistentClient(path=settings.chroma_persist_path)
try:
    col = client.get_collection("riverty_contracts")
    count = col.count()
    print(f"\n  Total chunks in store: {count}")
    if count > 0:
        peek = col.peek(min(count, 5))
        print(f"\n  First {min(count,5)} stored chunks:\n")
        for i, doc_id in enumerate(peek["ids"]):
            meta = peek["metadatas"][i]
            text = peek["documents"][i]
            print(f"    [{i+1}] {doc_id}")
            print(f"         source:  {meta['source_file']}  |  chunk {meta['chunk_index']}  |  lang={meta['language']}")
            print(f"         preview: {text[:90].strip()}...")
            print()
except Exception as e:
    print(f"  Could not read ChromaDB: {e}")
PYEOF

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
import asyncio, logging
# Q&A mode: suppress INFO logs to terminal — write them to rag.log instead
logging.basicConfig(
    level=logging.WARNING,
    handlers=[
        logging.StreamHandler(),                          # WARNING+ to terminal
        logging.FileHandler("rag.log", encoding="utf-8"), # INFO+ to file
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
