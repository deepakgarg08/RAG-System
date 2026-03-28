"""
create_scanned_jpeg.py — Creates a synthetic JPEG simulating a scanned contract.
Used to test the OCR extractor (ocr_extractor.py) without needing real scanned documents.

Creates a realistic-looking scanned document:
  - Off-white background (simulating paper)
  - Slight Gaussian blur (simulating real scanner output)
  - Multiple paragraphs of contract text in a monospace-like layout

Usage:
    python tests/create_scanned_jpeg.py

Output:
    tests/sample_contracts/scanned_vendor_agreement_2023.jpg
"""
import os

from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------------------
# Contract text embedded in the image
# ---------------------------------------------------------------------------

_CONTRACT_TEXT = """\
VENDOR AGREEMENT

This Agreement is entered into as of January 2023
between Scanned Vendor GmbH (hereinafter "Vendor")
and Riverty GmbH (hereinafter "Client").

1. SERVICES
The Vendor agrees to provide software development
services as detailed in Schedule A attached hereto.
Scope includes backend API development, integration
testing, and deployment support for twelve months.

2. PAYMENT
Client shall pay Vendor EUR 8,000 per month,
invoiced on the first of each month, net 30 days.
Late payments incur 2% monthly interest after 30 days.

3. GDPR COMPLIANCE
Both parties agree to comply with GDPR Article 28.
Vendor acts as Data Processor for Client.
Vendor shall implement appropriate technical and
organisational measures to protect personal data.
Data breach notification within 72 hours is required.

4. INTELLECTUAL PROPERTY
All work product created under this Agreement shall
be the exclusive property of Client upon full payment.
Vendor retains rights to pre-existing tooling only.

5. LIABILITY
Vendor liability is capped at EUR 100,000 total.
Neither party is liable for indirect or consequential
damages arising from this Agreement.

6. CONFIDENTIALITY
Both parties agree to keep all business information
confidential for a period of three (3) years.

SIGNATURES:

Vendor: _____________________  Date: ___________
Name:   Dr. Karl Weber
Title:  Managing Director, Scanned Vendor GmbH

Client: _____________________  Date: ___________
Name:   Anna Bergstrom
Title:  Head of Legal Affairs, Riverty GmbH
"""

# ============================================================
# DEMO MODE: PIL/Pillow — local JPEG generation, no API needed
# PRODUCTION SWAP → Azure Document Intelligence (AWS: Textract):
#   Replace Tesseract OCR in ocr_extractor.py with Azure DI client.
#   Azure DI handles real scanned documents, handwriting, and tables
#   with far higher accuracy than local Tesseract.
# ============================================================


def create_scanned_contract_image() -> str:
    """Create a synthetic JPEG image simulating a scanned vendor agreement.

    Renders contract text onto an off-white background at A4 proportions,
    then applies a slight Gaussian blur to simulate scanner output.

    Returns:
        Absolute path to the saved JPEG file.
    """
    # A4-like dimensions at ~150 DPI
    width, height = 1240, 1754
    img = Image.new("RGB", (width, height), color=(252, 250, 245))  # off-white paper

    draw = ImageDraw.Draw(img)

    # Render each line of the contract text
    y_position = 80
    line_height = 28
    left_margin = 80

    for line in _CONTRACT_TEXT.strip().split("\n"):
        # Section headers rendered slightly larger (simulated via spacing)
        draw.text((left_margin, y_position), line.strip(), fill=(20, 20, 20))
        y_position += line_height

        # Extra space after blank lines (paragraph breaks)
        if line.strip() == "":
            y_position += 8

    # Simulate scanner noise: slight Gaussian blur
    img = img.filter(ImageFilter.GaussianBlur(radius=0.4))

    output_path = os.path.join(
        os.path.dirname(__file__),
        "sample_contracts",
        "scanned_vendor_agreement_2023.jpg",
    )
    img.save(output_path, "JPEG", quality=85)
    print(f"✓ Scanned contract image created: {output_path}")
    print(f"  Size: {width}x{height}px  |  Characters in text: {len(_CONTRACT_TEXT)}")
    return output_path


if __name__ == "__main__":
    saved = create_scanned_contract_image()
    print(f"\nRemember to update backend/tests/sample_contracts/README.md")
    print(f"with this entry:")
    print(
        "| scanned_vendor_agreement_2023.jpg | Vendor Agreement | EN "
        "| Yes (Art. 28) | No | Simulated scan for OCR tests |"
    )
