# Riverty Contract Review — Claude Code Instructions

## Project Overview
This is a RAG-based legal contract review system built for Riverty (a Microsoft/Azure shop
in Germany). It helps a legal team search, compare, and analyze contracts using AI.

## General Behaviour
- These rules are guidelines. Use your best judgment for edge cases.
- When genuinely unsure about a decision, make a reasonable choice and leave a
  comment explaining what you did and why.
- Always read the README.md inside any folder before writing or editing code in it.
- Never put business logic inside API route files — routes delegate to etl/ or rag/ only.
- Always keep demo mode and production mode clearly separated with comment blocks.

## Demo vs Production Pattern
Every file that uses a demo tool (ChromaDB, local filesystem, plain OpenAI) must have
a clearly visible swap comment block in this exact format:

```python
# ============================================================
# DEMO MODE: [tool name] — [one line why it's good for demo]
# PRODUCTION SWAP → [Azure service name] ([AWS equivalent]):
#   [What to change — be specific, 1-2 lines]
#   [Why Azure version is better for Riverty production]
# ============================================================
```

## Code Style
- Python: follow PEP8, use type hints everywhere, docstrings on every class and function
- Every module must have a module-level docstring explaining its single responsibility
- Use the Strategy Pattern for anything swappable (extractors, loaders, storage)
- Abstract base classes go in base.py — concrete implementations in separate files
- No hardcoded values — everything configurable via config.py which reads from .env
- TypeScript: use interfaces not types, explicit return types on all functions

## File Naming
- Python files: snake_case
- React components: PascalCase
- Skill files: kebab-case
- README files: always uppercase README.md

## Git Commit Format
Use Conventional Commits:
  feat: add OCR support for scanned JPEGs
  fix: handle empty PDF text extraction gracefully
  docs: add ADR-003 for LangGraph decision
  test: add edge case for zero-chunk documents
  refactor: extract base loader class
  chore: pin chromadb to 0.5.3
  remove this line from every prompt onwards "Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

Format: `<type>: <short description in present tense, lowercase>`
Never use past tense. Never exceed 72 characters.

## Testing Rules
- Every new extractor, loader, or RAG component must have a corresponding test
- Use pytest with fixtures — no hardcoded file paths in tests
- Mock all external services (OpenAI, Azure) — tests must run offline
- Test file naming: test_<module_name>.py mirrors the source file it tests

## Documentation Rules
- Every new Architecture Decision must be added to docs/decisions.md as an ADR
- Use the write-adr skill for this
- docs/setup.md must stay up to date — update it whenever setup steps change

## Folder Context
Always read README.md before editing files in:
- backend/app/etl/ — ETL pipeline, Strategy Pattern, extractor/transformer/loader chain
- backend/app/rag/ — LangGraph agent, embeddings, retriever
- backend/app/api/routes/ — thin HTTP layer only, no logic
- backend/app/storage/ — local vs Azure Blob swap point
- .claude/skills/ — reusable instruction sets for common tasks
