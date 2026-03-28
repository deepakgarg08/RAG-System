# extractors/ — Document Text Extractors

## Pattern
All extractors extend `BaseExtractor` defined in `base.py`.
They all implement one method: `extract(file_path: str) -> str`.
The pipeline selects the correct extractor based on file extension via `EXTRACTOR_REGISTRY`
in `pipeline.py`.

## Extractors

### `pdf_extractor.py` — Text-based PDFs
- Library: PyMuPDF (`fitz`)
- Reads all pages, concatenates text
- **Auto-fallback to OCR:** if extracted text is fewer than 50 characters, the file is
  likely a scanned PDF (image-only). Automatically delegates to `OCRExtractor`.
- Returns: raw text string

### `ocr_extractor.py` — Scanned images (JPEG, PNG) and scanned PDFs
- Library: Tesseract via `pytesseract` + `Pillow`
- Pre-processing pipeline: convert to grayscale → enhance contrast → run OCR
- Language support: `lang='eng+deu'` handles English and German contracts
- Returns: raw text string

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
