# What Was Built

## New Files

| File | Purpose |
|------|--------|
| `app/etl/compliance_storage.py` | External archival — `store_contract_in_api()`: fire-and-forget POST to compliance API; any failure is logged and skipped |
| `app/rag/llm_client.py` | Shared `_get_llm_client()` / `_get_model_name()` factory (extracted to break circular import) |
| `app/rag/document_grouper.py` | `group_by_document()` + `build_grouped_context()` — aggregates flat chunk lists into per-document structures |
| `app/rag/document_analyzer.py` | Temporary document analysis — `analyze_single_document()` (MODE 1), `compare_with_database()` (MODE 2), `check_compliance()` |
| `app/api/routes/analyze.py` | `POST /api/analyze` — SSE stream, `mode=single|compare`, file never stored in DB |
| `app/api/routes/compliance.py` | `POST /api/compliance` — JSON structured result: `{compliant, violations, explanation}` |
| `tests/test_analysis.py` | 29 new tests covering all new components |

---

## Modified Files

| File | Change |
|------|--------|
| `app/config.py` | Added `COMPLIANCE_API_URL` setting |
| `app/models.py` | Added `ComplianceResult` Pydantic model |
| `app/api/routes/ingest.py` | Calls `store_contract_in_api()` after save (fail-safe) |
| `app/rag/agent.py` | Reasoner branches on `find_missing` → document-level grouped context (MODE 3) |
| `app/main.py` | Registers two new routers |
| `tests/conftest.py` + `test_rag.py` | Updated AsyncOpenAI patch paths to `app.rag.llm_client` |

---

## The Three Modes (Clearly Separated)

- `POST /api/analyze  mode=single`  
  → LLM sees **ONLY the uploaded document** (no DB)

- `POST /api/analyze  mode=compare`  
  → LLM compares **uploaded document vs database** (DB read-only)

- `POST /api/compliance`  
  → **Structured compliance check** (no DB)

- `POST /api/query`  
  → **Cross-database retrieval**, `find_missing` groups (DB read-only)

- `POST /api/ingest`  
  → **Persistent ingestion + archival** (DB write)