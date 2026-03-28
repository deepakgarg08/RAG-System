# Testing Guide — How to Run and Test the Pipeline

---

## What Files Exist (and What They're For)

```
backend/tests/sample_contracts/
├── contract_nda_techcorp_2023.txt           ← English NDA (has GDPR clause)
├── contract_service_datasystems_2022.txt    ← English service agreement (NO GDPR — intentional)
├── contract_vendor_2023_no_termination.txt  ← English vendor (NO termination clause)
├── vertrag_dienstleistung_mueller_2024.txt  ← German contract (DSGVO Art. 28)
└── scanned_vendor_agreement_2023.jpg        ← Real scanned image — OCR is tested against this
```

**Important:** The `.txt` files are reference content only — the pipeline does not process
`.txt` files. To run them through the pipeline, convert to PDF first (see below).
The `.jpg` file works directly — Tesseract OCR extracts ~1,392 chars from it.

**Supported formats:** `.pdf`, `.jpg`, `.jpeg`, `.png` — everything else returns HTTP 400.

---

## Where to Put Your Files

```
backend/uploads/    ← drop your .pdf / .jpg / .png here
```

This folder is created automatically when the server starts. You can also create it manually:

```bash
mkdir -p backend/uploads
```

---

## Option A — Test Without Starting the Server (Direct Python)

Best for: batch ingestion, debugging a single file, no HTTP overhead.

```bash
# From the project root
cd backend
source ../.venv/bin/activate     # or: source venv/bin/activate

# Create uploads folder if it doesn't exist
mkdir -p uploads

# Copy your file in
cp /path/to/your/contract.pdf uploads/

# Ingest it
python -c "
from app.etl.pipeline import IngestionPipeline

pipeline = IngestionPipeline()
result = pipeline.ingest('uploads/your_contract.pdf')

print('filename:      ', result['filename'])
print('language:      ', result['language'])
print('chunks_created:', result['chunks_created'])
print('status:        ', result['status'])
print('error:         ', result.get('error'))
"
```

Expected output:
```
filename:       your_contract.pdf
language:       en
chunks_created: 4
status:         success
error:          None
```

### Ingest a whole folder at once

```bash
python -c "
from app.etl.pipeline import IngestionPipeline
import os

pipeline = IngestionPipeline()
folder = 'uploads/'

for filename in sorted(os.listdir(folder)):
    if filename.endswith(('.pdf', '.jpg', '.jpeg', '.png')):
        result = pipeline.ingest(os.path.join(folder, filename))
        print(f\"{result['filename']:<50} lang={result['language']}  chunks={result['chunks_created']}  status={result['status']}\")
"
```

---

## Option B — Test Via the HTTP API (Server Running)

Best for: testing the full stack end-to-end including validation, CORS, and SSE streaming.

### 1. Start the server

```bash
cd backend
source ../.venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Expected startup output:
```
Starting Riverty Contract Review — mode: demo, env: development
INFO:     Uvicorn running on http://0.0.0.0:8000
```

The `uploads/` directory is created automatically at this point.

### 2. Check the system is up

```bash
curl http://localhost:8000/health
```
```json
{"status": "ok", "document_count": 0, "mode": "demo", "app_env": "development"}
```

`document_count: 0` means nothing is ingested yet — that's expected.

### 3. Upload a PDF or JPG

```bash
# PDF
curl -X POST http://localhost:8000/api/ingest \
  -F "file=@backend/uploads/your_contract.pdf"

# JPG (scanned contract)
curl -X POST http://localhost:8000/api/ingest \
  -F "file=@backend/tests/sample_contracts/scanned_vendor_agreement_2023.jpg"
```

Expected response:
```json
{
  "filename": "your_contract.pdf",
  "file_type": ".pdf",
  "language": "en",
  "chunks_created": 4,
  "status": "success",
  "error": null
}
```

### 4. Check document count increased

```bash
curl http://localhost:8000/health
```
```json
{"status": "ok", "document_count": 4, "mode": "demo", "app_env": "development"}
```

### 5. Ask a question (SSE streaming)

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Does this contract have a GDPR clause?"}' \
  --no-buffer
```

You will see tokens arriving one by one:
```
data: Based

data:  on

data:  the

data:  uploaded

data:  contracts

data: , the NDA with TechCorp contains a GDPR data protection clause in Section 7...

data: **Sources:** your_contract.pdf

data: [DONE]
```

### 6. Test a question with no answer in the contracts

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the weather in Berlin today?"}' \
  --no-buffer
```

Expected: the model responds with:
```
"This information was not found in the uploaded contracts."
```

This confirms grounding is working — GPT-4o is not using internet knowledge.

### 7. Test the 400 error for unsupported file type

```bash
curl -X POST http://localhost:8000/api/ingest \
  -F "file=@somefile.docx"
```
```json
{"detail": "Unsupported file type '.docx'. Accepted types: .jpeg, .jpg, .pdf, .png"}
```

---

## Option C — Convert the .txt Sample Contracts to PDF and Ingest All 4

The `.txt` files have realistic contract content (GDPR clauses, German language, missing
termination clauses). To run them through the pipeline, convert to PDF first:

```bash
cd backend
source ../.venv/bin/activate

python -c "
import fitz
from pathlib import Path
import os

os.makedirs('uploads', exist_ok=True)
sample_dir = Path('tests/sample_contracts')

for txt_file in sorted(sample_dir.glob('*.txt')):
    text = txt_file.read_text(encoding='utf-8')
    doc = fitz.open()
    lines = text.split('\n')
    for i in range(0, len(lines), 55):
        page = doc.new_page()
        page.insert_text((50, 50), '\n'.join(lines[i:i+55]), fontname='helv', fontsize=9)
    out = Path('uploads') / txt_file.with_suffix('.pdf').name
    doc.save(str(out))
    doc.close()
    print(f'Created: {out}')
"
```

Then ingest all of them:

```bash
python -c "
from app.etl.pipeline import IngestionPipeline
import os

pipeline = IngestionPipeline()
for f in sorted(os.listdir('uploads')):
    if f.endswith('.pdf'):
        r = pipeline.ingest(f'uploads/{f}')
        print(f\"{r['filename']:<50} lang={r['language']}  chunks={r['chunks_created']}  status={r['status']}\")
"
```

Expected output:
```
contract_nda_techcorp_2023.pdf                     lang=en  chunks=8  status=success
contract_service_datasystems_2022.pdf              lang=en  chunks=7  status=success
contract_vendor_2023_no_termination.pdf            lang=en  chunks=8  status=success
vertrag_dienstleistung_mueller_2024.pdf            lang=de  chunks=7  status=success
```

---

## Inspecting What Is Stored in ChromaDB

After ingestion, peek at the vector store to confirm data is there with full source metadata:

```bash
cd backend
source ../.venv/bin/activate

python -c "
import chromadb

client = chromadb.PersistentClient(path='./chroma_db')
col = client.get_collection('riverty_contracts')

print('Total chunks stored:', col.count())
print()

peek = col.peek(5)
for i, doc_id in enumerate(peek['ids']):
    meta = peek['metadatas'][i]
    text = peek['documents'][i]
    print(f'ID:       {doc_id}')
    print(f'Source:   {meta[\"source_file\"]}  |  chunk {meta[\"chunk_index\"]}  |  lang={meta[\"language\"]}')
    print(f'Preview:  {text[:100].strip()}...')
    print()
"
```

Example output:
```
Total chunks stored: 30

ID:       contract_nda_techcorp_2023.pdf_chunk_0
Source:   contract_nda_techcorp_2023.pdf  |  chunk 0  |  lang=en
Preview:  NON-DISCLOSURE AGREEMENT This Non-Disclosure Agreement is entered into as of January...

ID:       vertrag_dienstleistung_mueller_2024.pdf_chunk_3
Source:   vertrag_dienstleistung_mueller_2024.pdf  |  chunk 3  |  lang=de
Preview:  Auftragsverarbeitungsvertrag gemäß Artikel 28 Absatz 3 DSGVO ab. 3.3 Der Auftragnehmer...
```

---

## Inspecting Source Attribution from Retrieval

Every retrieved result carries the exact source file, chunk index, language, and similarity score:

```bash
cd backend
source ../.venv/bin/activate

python -c "
from app.rag.retriever import ContractRetriever

retriever = ContractRetriever()
results = retriever.retrieve('Does this contract have a GDPR clause?', top_k=5)

for i, r in enumerate(results):
    print(f'Result #{i+1}')
    print(f'  source_file:      {r[\"source_file\"]}')
    print(f'  chunk_index:      {r[\"chunk_index\"]}')
    print(f'  language:         {r[\"language\"]}')
    print(f'  similarity_score: {r[\"similarity_score\"]}')
    print(f'  text preview:     {r[\"text\"][:100].strip()}...')
    print()
"
```

Example output (with real OpenAI embeddings):
```
Result #1
  source_file:      contract_nda_techcorp_2023.pdf
  chunk_index:      3
  language:         en
  similarity_score: 0.87
  text preview:     Section 7: All personal data processed under this agreement shall comply with GDPR...

Result #2
  source_file:      vertrag_dienstleistung_mueller_2024.pdf
  chunk_index:      3
  language:         de
  similarity_score: 0.74
  text preview:     Auftragsverarbeitungsvertrag gemäß Artikel 28 Absatz 3 DSGVO ab...
```

The `similarity_score` ranges from 0.0 (unrelated) to 1.0 (identical meaning).
Chunks below 0.30 are filtered out automatically.

---

## Run the Automated Test Suite

```bash
# From the project root — runs all 55 tests offline (no API key needed)
bash backend/run_tests.sh
```

Expected result:
```
55 passed
Coverage: 81%
Coverage report: backend/htmlcov/index.html
```

---

## Quick Reference

| Goal | Command |
|---|---|
| Check system is up | `curl http://localhost:8000/health` |
| Ingest a PDF via API | `curl -X POST .../api/ingest -F "file=@contract.pdf"` |
| Ingest directly (no server) | `pipeline.ingest("uploads/contract.pdf")` |
| Ask a question (streaming) | `curl -X POST .../api/query -d '{"question":"..."}'` |
| Peek at ChromaDB | `col.peek(5)` in Python |
| Check retrieval + sources | `retriever.retrieve("your question", top_k=5)` |
| Run all tests | `bash backend/run_tests.sh` |
| Unsupported file type | Upload `.docx` → expect HTTP 400 |
