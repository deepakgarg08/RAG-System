# Data Flow — End-to-End Trace

This document traces a real contract from upload through to a query answer,
with concrete data at each step.

---

## Path 1: Contract Ingestion

**Input:** User uploads `contract_nda_techcorp_2023.pdf` (47KB, 4 pages, typed PDF)

```
1. Frontend
   User drops file onto FileUpload component
   → POST /api/ingest  (multipart/form-data, file field = "file")

2. Route: ingest.py
   Receives UploadFile, validates extension is in allowed list
   → Calls etl.pipeline.run(file_path, filename)

3. ETL Pipeline: Extractor
   pdf_extractor.py opens file with PyMuPDF
   Reads 4 pages → 3,412 raw characters
   Text length > 50 chars → no OCR fallback needed
   → Returns: raw_text (str, 3412 chars)

4. ETL Pipeline: Cleaner
   cleaner.py removes 3 OCR artifacts, collapses whitespace
   → Returns: clean_text (str, 3,289 chars), language="en"

5. ETL Pipeline: Chunker
   RecursiveCharacterTextSplitter (chunk=1000, overlap=200)
   → Returns: 4 chunks
   chunk[0]: chars 0–1000    metadata: {source="techcorp_nda.pdf", chunk_index=0, total=4, lang="en"}
   chunk[1]: chars 801–1800  metadata: {source="techcorp_nda.pdf", chunk_index=1, total=4, lang="en"}
   chunk[2]: chars 1601–2601 metadata: {source="techcorp_nda.pdf", chunk_index=2, total=4, lang="en"}
   chunk[3]: chars 2401–3289 metadata: {source="techcorp_nda.pdf", chunk_index=3, total=4, lang="en"}

6. Embedder: embeddings.py
   4 × API call to OpenAI text-embedding-3-small
   → Returns: 4 vectors, each 1536 dimensions

7. Loader: chroma_loader.py
   Stores 4 vectors + 4 metadata dicts + 4 text documents in ChromaDB collection
   → ChromaDB persists to ./chroma_db/

8. Storage: local_storage.py
   Saves original file to ./uploads/contract_nda_techcorp_2023.pdf

9. Route returns:
   {"filename": "contract_nda_techcorp_2023.pdf", "chunks": 4, "status": "ingested"}
```

---

## Path 2: Legal Query

**Input:** User types: "Does the TechCorp NDA have a GDPR data protection clause?"

```
1. Frontend
   User submits QueryInput
   → POST /api/query  {"question": "Does the TechCorp NDA have a GDPR data protection clause?"}
   Opens EventSource to receive SSE stream

2. Route: query.py
   Receives QueryRequest, validates question is non-empty
   → Returns StreamingResponse, calls rag.agent.stream_query(question)

3. LangGraph Agent — Node 1: query_router
   Classifies question intent
   → intent = "find_clause"

4. LangGraph Agent — Node 2: retriever
   Embeds question: "Does the TechCorp NDA have a GDPR data protection clause?"
   → 1536-dim query vector
   Queries ChromaDB for top-5 most similar chunks
   → Returns 5 chunks:
      [0] techcorp_nda.pdf / chunk_2  score=0.91  (Section 7: Data Protection)
      [1] techcorp_nda.pdf / chunk_1  score=0.74  (Section 4: Confidentiality)
      [2] techcorp_nda.pdf / chunk_3  score=0.61  (Section 9: Governing Law)
      [3] techcorp_nda.pdf / chunk_0  score=0.42  (Recitals)
      [4] datasys_service.pdf / chunk_1  score=0.38  (unrelated contract)

5. LangGraph Agent — Node 3: reasoner
   Builds prompt:
     System: "Answer using ONLY the provided contract chunks. If not found, say so."
     Context: [5 retrieved chunks with metadata]
     Question: "Does the TechCorp NDA have a GDPR data protection clause?"
   Calls GPT-4o (streaming)
   → Generates answer token by token

6. LangGraph Agent — Node 4: formatter
   Attaches source references to answer:
   {
     "answer": "Yes, the TechCorp NDA contains a GDPR data protection clause...",
     "sources": [
       {"file": "techcorp_nda.pdf", "chunk": 2, "section": "Section 7: Data Protection", "score": 0.91}
     ]
   }

7. SSE Stream to Frontend
   data: {"token": "Yes"}\n\n
   data: {"token": ","}\n\n
   data: {"token": " the"}\n\n
   ... (token by token as GPT-4o generates)
   data: [DONE]\n\n

8. Frontend
   StreamingResponse component appends each token
   Source references rendered below the answer
```
