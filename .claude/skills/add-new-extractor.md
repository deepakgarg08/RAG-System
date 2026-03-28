# Skill: Add a New Document Extractor

## When to use this skill
Use when adding support for a new file type (e.g. Word .docx, Excel .xlsx,
PowerPoint .pptx, plain text .txt).

## Step-by-step process

### 1. Read first
Read backend/app/etl/extractors/README.md and backend/app/etl/extractors/base.py
to understand the BaseExtractor interface before writing anything.

### 2. Create the new extractor file
Create: `backend/app/etl/extractors/<format>_extractor.py`

It must:
- Import and extend BaseExtractor from base.py
- Implement the `extract(file_path: str) -> str` method
- Have a module-level docstring explaining what file types it handles
- Include the DEMO/PRODUCTION swap comment if a better Azure alternative exists
- Handle errors gracefully — return empty string and log warning, never crash

### 3. Register the extractor
In `backend/app/etl/pipeline.py`, add the new file extension to the
`EXTRACTOR_REGISTRY` dictionary:
```python
EXTRACTOR_REGISTRY = {
    ".pdf": PDFExtractor,
    ".jpg": OCRExtractor,
    ".jpeg": OCRExtractor,
    ".docx": DocxExtractor,   # ← add your new one here
}
```

### 4. Add dependencies
Add the required library to `backend/requirements.txt` with a pinned version.

### 5. Write tests
Create or update `backend/tests/test_etl.py`:
- Add a sample test file to `backend/tests/sample_contracts/`
- Write happy path test: valid file extracts non-empty text
- Write error test: corrupted file returns empty string without crashing
- Write edge case: empty file returns empty string

### 6. Update documentation
- Add the new file type to `backend/app/etl/extractors/README.md`
- If it requires an Azure service swap, add an ADR using the write-adr skill
