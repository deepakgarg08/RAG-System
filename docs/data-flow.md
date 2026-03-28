# Data Flow — End-to-End Trace

This document traces two real operations through the system with concrete data at every step:
a contract upload and a cross-contract query.

---

## Flow 1: Ingesting a Contract File

**Input:** User uploads `contract_nda_techcorp_2023.pdf` via the React drag-drop interface.

### Step 1 — Frontend → POST /api/ingest
User drops the file onto the `FileUpload` component.
```
POST /api/ingest
Content-Type: multipart/form-data
file: contract_nda_techcorp_2023.pdf (47 KB)
```

### Step 2 — FastAPI validates and saves
`ingest.py` checks the extension (`.pdf` is in `_ALLOWED_EXTENSIONS`).
`LocalStorage.save()` writes the bytes to disk:
```
./uploads/contract_nda_techcorp_2023.pdf  (47,104 bytes written)
```

### Step 3 — IngestionPipeline selects PDFExtractor
`pipeline.py` looks up `.pdf` in `EXTRACTOR_REGISTRY` → selects `PDFExtractor`.
Logs: `Pipeline: extracting contract_nda_techcorp_2023.pdf with PDFExtractor`

### Step 4 — PDFExtractor reads text
`PyMuPDF` opens the 4-page PDF and reads all text layers.
```
raw_text length: 2,847 characters
Text detected (>50 chars) → no OCR fallback needed
```

### Step 5 — TextCleaner normalises
`cleaner.py` removes OCR artefacts, collapses whitespace, strips stray symbols.
```
clean_text length: 2,801 characters  (46 chars removed)
language detected: "en"
```

### Step 6 — DocumentChunker splits into chunks
`RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)` produces 3 chunks:
```
chunk[0]: chars    0–1000  metadata: {source_file="contract_nda_techcorp_2023.pdf", chunk_index=0, language="en"}
chunk[1]: chars  801–1800  metadata: {source_file="contract_nda_techcorp_2023.pdf", chunk_index=1, language="en"}
chunk[2]: chars 1601–2801  metadata: {source_file="contract_nda_techcorp_2023.pdf", chunk_index=2, language="en"}
```
200-char overlap: the tail of chunk[0] (chars 800–1000) also appears at the head of chunk[1].

### Step 7 — EmbeddingService converts chunks to vectors
`EmbeddingService.get_embedding()` calls OpenAI `text-embedding-3-small` for each chunk:
```
3 API calls → 3 vectors, each 1536 dimensions
chunk[0] → [0.0023, -0.0187, 0.0041, ...]  (1536 floats)
chunk[1] → [0.0019, -0.0201, 0.0038, ...]  (1536 floats)
chunk[2] → [-0.0012, 0.0094, 0.0173, ...]  (1536 floats)
```

### Step 8 — ChromaLoader stores vectors
`ChromaLoader.load()` upserts all 3 chunks into the `riverty_contracts` collection:
```
ChromaDB collection: riverty_contracts
Documents before: 9
Documents after:  12
Persisted to: ./chroma_db/
```

### Step 9 — API returns IngestResponse
```json
{
  "filename": "contract_nda_techcorp_2023.pdf",
  "file_type": ".pdf",
  "language": "en",
  "chunks_created": 3,
  "status": "success",
  "error": null
}
```

---

## Flow 2: Querying Across Contracts

**Input:** User types: *"Which contracts don't have a GDPR clause?"*

### Step 1 — Frontend → POST /api/query (SSE)
User submits the `QueryInput` component.
```
POST /api/query
Content-Type: application/json
{"question": "Which contracts don't have a GDPR clause?"}
```
The `EventSource` connection opens — the browser is now listening for SSE tokens.

### Step 2 — FastAPI starts SSE stream
`query.py` validates `QueryRequest` (question is 3–500 chars ✓).
Calls `stream_query("Which contracts don't have a GDPR clause?")`.
Returns `StreamingResponse(media_type="text/event-stream")` immediately.
The LangGraph agent starts executing in the background.

### Step 3 — query_router node — intent classification
GPT-4o classifies the question against the 4 intent categories:
```
prompt: "Classify this legal contract query into exactly one category: ..."
response: "find_missing"
AgentState.query_type = "find_missing"
```
Logs: `query_router: classified 'Which contracts...' → find_missing`

### Step 4 — retriever_node — semantic search
`EmbeddingService` embeds the question:
```
"Which contracts don't have a GDPR clause?" → 1536-dim query vector
```
`ContractRetriever.retrieve()` queries ChromaDB (top_k=5):
```
ChromaDB collection count: 12 chunks (4 contracts × ~3 chunks each)
n_results requested: 5
```

### Step 5 — Top-5 chunks returned, ranked by similarity
ChromaDB returns chunks across all ingested contracts, ordered by cosine similarity:
```
[0] contract_service_datasystems_2022.pdf / chunk_1  score=0.84  "Confidentiality and Data Handling..."
[1] contract_nda_techcorp_2023.pdf / chunk_2         score=0.79  "Section 7: Data Protection..."
[2] contract_software_globaltech_2021.pdf / chunk_0  score=0.71  "Privacy and Data Processing..."
[3] contract_nda_techcorp_2023.pdf / chunk_0         score=0.58  "Parties and Recitals..."
[4] contract_msa_riverty_2023.pdf / chunk_1          score=0.51  "Obligations of the Parties..."
```
Chunks with similarity < 0.30 are filtered out. All 5 pass.

### Step 6 — reasoner node — GPT-4o generates answer
`reasoner` builds the context string from the 5 chunks and calls GPT-4o with streaming:
```
System prompt: "Answer ONLY using the provided contract excerpts below. Always cite
               which contract your answer comes from..."
Context: [5 formatted chunks with source labels and relevance scores]
Question: "Which contracts don't have a GDPR clause?"
```
GPT-4o streams the response token by token.

### Step 7 — Tokens yield through SSE
Each token from the LangGraph `on_chat_model_stream` event is yielded immediately:
```
data: Based\n\n
data:  on\n\n
data:  the\n\n
data:  uploaded\n\n
data:  contracts\n\n
data: ,\n\n
data:  the\n\n
data:  Service\n\n
data:  Agreement\n\n
...
```
The React frontend appends each token to the display as it arrives.
The user sees the answer building word by word within ~300ms of the first token.

### Step 8 — formatter node — append source citations
`formatter` collects unique source filenames from the retrieved chunks and appends them:
```
unique_sources = [
  "contract_service_datasystems_2022.pdf",
  "contract_nda_techcorp_2023.pdf",
  "contract_software_globaltech_2021.pdf",
  "contract_msa_riverty_2023.pdf"
]
answer += "\n\n**Sources:** contract_service_datasystems_2022.pdf, contract_nda_techcorp_2023.pdf, ..."
```

### Step 9 — Stream terminates
After all tokens are sent, `stream_query` yields the sentinel:
```
data: [DONE]\n\n
```
The React frontend receives `[DONE]`, stops the streaming display, and renders the final
answer with source citation links.

### Step 10 — Final answer shown
```
"Based on the uploaded contracts, the Service Agreement with DataSystems Ltd (2022) does
not contain a GDPR data processing clause. The other three contracts — TechCorp NDA (2023),
GlobalTech Software Agreement (2021), and the Riverty MSA (2023) — all include explicit
data protection provisions referencing GDPR Article 28.

**Sources:** contract_service_datasystems_2022.pdf, contract_nda_techcorp_2023.pdf,
contract_software_globaltech_2021.pdf, contract_msa_riverty_2023.pdf"
```
