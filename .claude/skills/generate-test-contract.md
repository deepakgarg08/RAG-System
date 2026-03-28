# Skill: Generate a Synthetic Test Contract

## When to use this skill
Use when you need a new test contract for a specific scenario — a missing clause,
a specific language, a specific contract type, or a file format variant.

## Step-by-step process

### 1. Determine what the contract needs to demonstrate
Before generating, define clearly:
- Contract type: NDA / Service Agreement / Vendor Agreement / Employment / Other
- Language: English / German / Both sections
- Key feature: what clause MUST be present or MUST be absent
- Company names: use fictional but realistic German/UK company names
- Date: realistic date (2021-2024)

### 2. Generate the contract text
Use the OpenAI API with this system prompt:
```
You are a legal document generator. Generate a realistic but entirely fictional
legal contract. Use realistic legal language and structure. The contract must be
clearly fictional — use made-up company names. Include proper sections, clauses,
and signatures block. Length: 400-800 words.
```

### 3. File naming convention
`<contract_type>_<company_short>_<year>_<notable_feature>.txt`

Examples:
- `nda_techcorp_2023_has_gdpr.txt`
- `service_agreement_mueller_2022_no_gdpr.txt`
- `vendor_agreement_datasys_2023_no_termination.txt`
- `dienstleistung_schmidt_2024_german.txt`

### 4. Save location
Always save to: `backend/tests/sample_contracts/`

### 5. Update the test contracts index
Append an entry to `backend/tests/sample_contracts/README.md`:
| Filename | Type | Language | Has GDPR | Has Termination | Notes |
