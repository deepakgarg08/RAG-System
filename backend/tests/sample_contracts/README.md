# sample_contracts/ — Synthetic Test Contracts

## Important
All files in this folder are **entirely fictional** — generated for testing purposes only.
They use made-up company names and do not represent any real legal agreements.

## Two Categories

### Text files (`.txt`)
Simulate typed/digital contracts. Used for ETL pipeline tests.

### JPEG scans (`.jpg`)
Simulate scanned contracts. Used for OCR extractor tests.
These will be added in a future prompt.

## Contract Index

| Filename | Type | Language | Has GDPR | Has Termination | Purpose |
|---|---|---|---|---|---|
| contract_nda_techcorp_2023.txt | NDA | English | Yes | Yes | Base happy path test |
| contract_service_datasystems_2022.txt | Service | English | NO | Yes | Test "find missing GDPR" |
| vertrag_dienstleistung_mueller_2024.txt | Service | German | Yes (DSGVO) | Yes | Test German language |
| contract_vendor_2023_no_termination.txt | Vendor | English | Yes | NO | Test "find missing termination" |

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
