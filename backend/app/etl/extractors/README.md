# extractors/ — Document Text Extractors

## Pattern
All extractors extend `BaseExtractor` defined in `base.py`.
They all implement one method: `extract(file_path: str) -> list[dict]`.
Each dict has the form `{"page_number": int, "text": str}` — one entry per page.
The pipeline selects the correct extractor based on file extension via `EXTRACTOR_REGISTRY`
in `pipeline.py`.

**Why page dicts instead of a plain string?**
Page numbers travel with the text through cleaning, chunking, and into ChromaDB metadata.
At query time every retrieved chunk reports exactly which page it came from — critical for
legal document review where a lawyer needs to find the source passage in the original file.

## Extractors

### `pdf_extractor.py` — Text-based PDFs
- Library: PyMuPDF (`fitz`)
- Reads each page individually, preserving page boundaries
- **Auto-fallback to OCR:** if total extracted text is fewer than 50 characters, the file is
  likely a scanned PDF (image-only). Automatically delegates each page to OCR.
- Returns: `[{"page_number": 1, "text": "..."}, {"page_number": 2, "text": "..."}, ...]`

### `ocr_extractor.py` — Scanned images (JPEG, PNG) and scanned PDFs
- Library: Tesseract via `pytesseract` + `Pillow`
- Pre-processing pipeline: convert to grayscale → enhance contrast → run OCR
- Language support: `lang='eng+deu'` handles English and German contracts
- Images are single-page by definition — always returns a one-element list
- Returns: `[{"page_number": 1, "text": "..."}]`

## Production Swap Note
```
# ============================================================
# DEMO MODE: PyMuPDF + Tesseract — zero config, runs locally
# PRODUCTION SWAP → Azure Document Intelligence (AWS: Textract):
#   Replace both extractors with azure_doc_extractor.py
#   One API call handles typed PDFs, scanned PDFs, handwritten JPEGs,
#   tables, and form fields — simpler pipeline, better accuracy
# ============================================================
```

## Adding a New File Type
Follow the steps in `.claude/skills/add-new-extractor.md`.

## Supported Extensions

| Extension | Extractor | Notes |
|---|---|---|
| `.pdf` | PDFExtractor | Auto-falls back to OCR if scanned |
| `.jpg` / `.jpeg` | OCRExtractor | Pre-processed before OCR |
| `.png` | OCRExtractor | Pre-processed before OCR |
