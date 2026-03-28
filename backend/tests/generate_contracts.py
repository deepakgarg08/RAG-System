"""
generate_contracts.py — Synthetic contract generator for testing.

Uses the generate-test-contract skill pattern (.claude/skills/generate-test-contract.md).
Generates realistic but entirely fictional legal contracts using GPT-4o.
Requires a valid OPENAI_API_KEY in .env or environment.

Usage:
    python tests/generate_contracts.py --type nda --language english
    python tests/generate_contracts.py --type service --language german
    python tests/generate_contracts.py --type vendor --has-gdpr false --has-termination false
    python tests/generate_contracts.py --type employment --company-a "Bergmann Solutions GmbH"

Arguments:
    --type          : nda | service | vendor | employment
    --language      : english | german
    --has-gdpr      : true | false  (default: true)
    --has-termination: true | false (default: true)
    --company-a     : company name (auto-selected from fictional list if omitted)
    --company-b     : always "Riverty GmbH" (hardcoded, overridable)
"""
import argparse
import os
import random
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

# ============================================================
# DEMO MODE: OpenAI API — direct key, runs locally
# PRODUCTION SWAP → Azure OpenAI (AWS: Bedrock):
#   Replace client = OpenAI(...) with:
#   client = AzureOpenAI(
#       api_key=os.getenv("AZURE_OPENAI_API_KEY"),
#       azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
#       api_version="2024-02-01",
#   )
#   Model name stays "gpt-4o"
# ============================================================

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CONTRACT_TEMPLATES: dict[str, str] = {
    "nda": "Non-Disclosure Agreement (NDA)",
    "service": "Service Agreement",
    "vendor": "Vendor Agreement",
    "employment": "Employment Agreement",
}

FICTIONAL_COMPANIES: list[str] = [
    "Bergmann Solutions GmbH",
    "Alpine Tech AG",
    "Rhine Data Systems GmbH",
    "Nordstadt Consulting Ltd",
    "Bavarian Software GmbH",
    "Hamburg Digital AG",
]


def build_prompt(
    contract_type: str,
    language: str,
    has_gdpr: bool,
    has_termination: bool,
    company_a: str,
    company_b: str = "Riverty GmbH",
) -> str:
    """Build the GPT-4o prompt for a specific contract configuration.

    Args:
        contract_type: One of nda | service | vendor | employment.
        language: One of english | german.
        has_gdpr: Whether to include a GDPR / DSGVO clause.
        has_termination: Whether to include a termination clause.
        company_a: Name of the first contracting party.
        company_b: Name of the second contracting party (default Riverty GmbH).

    Returns:
        Prompt string to send to GPT-4o.
    """
    lang_instruction = (
        "Write in German using proper legal German terminology."
        if language == "german"
        else "Write in English using proper legal terminology."
    )

    gdpr_instruction = (
        "MUST include a GDPR/DSGVO compliance section (Article 28 processor agreement)."
        if has_gdpr
        else "Do NOT include any GDPR, DSGVO, data protection, or privacy clause. This is intentional."
    )

    term_instruction = (
        "MUST include a termination clause specifying notice period."
        if has_termination
        else "Do NOT include any termination clause. This is intentional."
    )

    return f"""Generate a realistic but entirely fictional {CONTRACT_TEMPLATES[contract_type]}.

Parties: {company_a} and {company_b}
{lang_instruction}
{gdpr_instruction}
{term_instruction}
Date: {datetime.now().strftime('%B %Y')}

Requirements:
- Use realistic legal language and proper section structure
- Include signature blocks at the end
- Length: 500-700 words
- All company names, people, and details must be completely fictional

Output ONLY the contract text, no preamble or explanation."""


def generate_contract(args: argparse.Namespace) -> None:
    """Generate a synthetic contract and save it to sample_contracts/.

    Args:
        args: Parsed command-line arguments.
    """
    company_a = args.company_a or random.choice(FICTIONAL_COMPANIES)
    company_b = getattr(args, "company_b", "Riverty GmbH") or "Riverty GmbH"
    has_gdpr = args.has_gdpr.lower() == "true"
    has_termination = args.has_termination.lower() == "true"

    print(f"\nGenerating {args.type} contract...")
    print(f"  Language     : {args.language}")
    print(f"  Company A    : {company_a}")
    print(f"  Company B    : {company_b}")
    print(f"  Has GDPR     : {has_gdpr}")
    print(f"  Has Termination: {has_termination}")

    prompt = build_prompt(
        args.type, args.language, has_gdpr, has_termination, company_a, company_b
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1500,
    )

    contract_text = response.choices[0].message.content

    # Build filename following generate-test-contract skill convention
    gdpr_tag = "has_gdpr" if has_gdpr else "no_gdpr"
    term_tag = "has_term" if has_termination else "no_term"
    company_short = company_a.split()[0].lower()
    year = datetime.now().year
    lang_tag = "de" if args.language == "german" else "en"
    filename = f"{args.type}_{company_short}_{year}_{gdpr_tag}_{term_tag}_{lang_tag}.txt"

    output_path = os.path.join(
        os.path.dirname(__file__),
        "sample_contracts",
        filename,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(contract_text)

    print(f"\n✓ Contract saved: {output_path}")
    print(f"  Characters: {len(contract_text)}")
    print(f"\nRemember to update backend/tests/sample_contracts/README.md")
    print(f"with this entry:")
    print(
        f"| {filename} | {args.type.upper()} | {lang_tag.upper()} "
        f"| {has_gdpr} | {has_termination} | Generated |"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic test contracts using GPT-4o"
    )
    parser.add_argument(
        "--type",
        choices=["nda", "service", "vendor", "employment"],
        default="nda",
        help="Contract type (default: nda)",
    )
    parser.add_argument(
        "--language",
        choices=["english", "german"],
        default="english",
        help="Contract language (default: english)",
    )
    parser.add_argument(
        "--has-gdpr",
        default="true",
        dest="has_gdpr",
        help="Include GDPR clause? true|false (default: true)",
    )
    parser.add_argument(
        "--has-termination",
        default="true",
        dest="has_termination",
        help="Include termination clause? true|false (default: true)",
    )
    parser.add_argument(
        "--company-a",
        default=None,
        dest="company_a",
        help="Company A name (auto-generated if omitted)",
    )
    parser.add_argument(
        "--company-b",
        default="Riverty GmbH",
        dest="company_b",
        help="Company B name (default: Riverty GmbH)",
    )
    parsed_args = parser.parse_args()
    generate_contract(parsed_args)
