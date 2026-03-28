#!/usr/bin/env bash
# run_tests.sh — Single entry point for the full test suite.
# Usage (from project root):  bash backend/run_tests.sh
# Usage (from backend/):      bash run_tests.sh

set -e  # exit on first failure

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# Activate virtual environment (try both common locations)
# ---------------------------------------------------------------------------
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "../.venv/bin/activate" ]; then
    source ../.venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "ERROR: No virtual environment found. Run: python -m venv venv && pip install -r requirements.txt"
    exit 1
fi

# ---------------------------------------------------------------------------
# Ensure a fake OpenAI key is set so imports don't fail
# ---------------------------------------------------------------------------
export OPENAI_API_KEY="${OPENAI_API_KEY:-test-key-for-offline-tests}"

# ---------------------------------------------------------------------------
# Run the full test suite
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  Riverty Contract Review — Full Test Suite"
echo "============================================================"
echo ""

pytest tests/ \
    -v \
    --tb=short \
    --cov=app \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    "$@"

echo ""
echo "============================================================"
echo "  Coverage report written to: backend/htmlcov/index.html"
echo "============================================================"
