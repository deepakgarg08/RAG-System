# sample_contracts/ — Synthetic Test Contracts

## Important
All files in this folder are **entirely fictional** — generated for testing purposes only.
They use made-up company names and do not represent any real legal agreements.

## Important Note on File Types

The ETL pipeline (`IngestionPipeline`) processes `.pdf`, `.jpg`, `.jpeg`, and `.png` files
only. The `.txt` contracts here are **reference content** — they contain realistic contract
language used to generate test PDFs or for manual review.

For automated pipeline tests, the `sample_pdf_path` fixture in `conftest.py` generates a
minimal valid PDF in a temp directory. To test with richer text, write a `.txt` contract
here, then convert it to PDF for the `sample_contracts/` folder.

### Text files (`.txt`) — reference content
Realistic contract text in English and German. Used as the source material when
generating test PDF fixtures or verifying language detection logic.

### JPEG scans (`.jpg`) — OCR tests
Simulate scanned contracts. To be added when OCR extractor tests are implemented.

## Contract Index

| Filename | Type | Language | Has GDPR | Has Termination | Purpose |
|---|---|---|---|---|---|
| contract_nda_techcorp_2023.txt | NDA | English | Yes (Art. 28) | Yes (30 days notice) | Base happy path test |
| contract_service_datasystems_2022.txt | Service Agreement | English | **NO** | Yes (60 days notice) | Test "find missing GDPR clause" |
| vertrag_dienstleistung_mueller_2024.txt | Dienstleistungsvertrag | **German** | Yes (DSGVO Art. 28) | Yes (3 Monate Frist) | Test German language detection |
| contract_vendor_2023_no_termination.txt | Vendor Agreement | English | Yes (Art. 28) | **NO** | Test "find missing termination clause" |

## Adding a New Test Contract
Follow the steps in `.claude/skills/generate-test-contract.md`, then add a row
to the table above.

## File Naming Convention
```
<contract_type>_<company_short>_<year>_<notable_feature>.txt
```
Examples:
- `nda_techcorp_2023_has_gdpr.txt`
- `service_agreement_mueller_2022_no_gdpr.txt`
