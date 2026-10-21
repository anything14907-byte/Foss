#!/usr/bin/env python3
"""
Generates evaluation documents (PNGs and PDF) representing messy real-world receipts
and invoices (faded ink, table structures, noisy backgrounds) for data/eval/.
Runs with standard Python libraries.
"""

import os
import json
import zlib
import struct

EVAL_DIR = "data/eval"
os.makedirs(EVAL_DIR, exist_ok=True)

# 1. Pure Python Minimal PNG Text & Receipt Generator
def make_receipt_png(filename, title, lines, total, date_str, noise=False, faded=False):
    width, height = 400, 600
    raw = bytearray()
    
    # Text line coordinates
    # We will draw a white receipt slip on a slightly darker background
    for y in range(height):
        raw.append(0)  # filter type
        for x in range(width):
            # Receipt paper bounding box: [40, 20, 360, 580]
            in_paper = (40 <= x <= 360) and (20 <= y <= 580)
            
            if not in_paper:
                # Dark desk surface background
                raw.extend([30, 41, 59, 255])
            else:
                # Receipt paper color
                if faded:
                    base_color = 235  # slightly yellowed/aged
                    ink_color = 120   # faded gray ink instead of sharp black
                else:
                    base_color = 250
                    ink_color = 30
                    
                # Add simulated paper grain / noise
                if noise:
                    grain = ((x * 17 + y * 31) % 19) - 9
                    base_color = max(200, min(255, base_color + grain))
                
                # Check for simulated printed text lines
                is_ink = False
                
                # Top header bar (Title)
                if 50 <= y <= 75 and 80 <= x <= 320:
                    # Simulated text block for title
                    if (y % 4 < 3) and (x % 7 < 5):
                        is_ink = True
                        
                # Date line
                if 100 <= y <= 112 and 60 <= x <= 220:
                    if (y % 3 < 2) and (x % 5 < 3):
                        is_ink = True
                        
                # Divider line
                if 130 <= y <= 132 and 60 <= x <= 340:
                    is_ink = True
                    
                # Item lines
                for idx, line_y in enumerate(range(160, 380, 45)):
                    if line_y <= y <= line_y + 12:
                        # Item name on left
                        if 60 <= x <= 250 and ((x % 6 < 4) and (y % 3 < 2)):
                            is_ink = True
                        # Item price on right
                        if 280 <= x <= 335 and ((x % 5 < 3) and (y % 3 < 2)):
                            is_ink = True
                            
                # Total divider
                if 420 <= y <= 422 and 60 <= x <= 340:
                    is_ink = True
                    
                # Grand Total line
                if 440 <= y <= 460 and 60 <= x <= 340:
                    if (y % 4 < 3) and ((60 <= x <= 160 and x % 6 < 4) or (260 <= x <= 340 and x % 5 < 3)):
                        is_ink = True
                        
                # Barcode at bottom
                if 500 <= y <= 540 and 80 <= x <= 320:
                    if (x % 7 in [0, 1, 3, 4, 6]):
                        is_ink = True

                if is_ink:
                    raw.extend([ink_color, ink_color, ink_color, 255])
                else:
                    raw.extend([base_color, base_color, base_color, 255])

    # Build PNG chunks
    png = bytearray(b"\x89PNG\r\n\x1a\n")
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png.extend(struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr)))
    
    compressed = zlib.compress(bytes(raw), 9)
    png.extend(struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(">I", zlib.crc32(b"IDAT" + compressed)))
    
    png.extend(struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND")))
    
    filepath = os.path.join(EVAL_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(png)
    print(f"Generated {filepath}")

# 2. Pure Python Valid PDF Invoice Generator
def make_pdf_invoice(filename, vendor, date_str, total_str):
    pdf_content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>
endobj
5 0 obj
<< /Length 450 >>
stream
BT
/F1 20 Tf
50 720 Td
({vendor}) Tj
/F1 12 Tf
0 -30 Td
(Date: {date_str}) Tj
0 -20 Td
(Invoice Number: INV-2026-9041) Tj
0 -40 Td
(---------------------------------------------------------------------------------------------------) Tj
0 -25 Td
(Item Description                       Qty    Unit Price      Total) Tj
0 -20 Td
(Cloud Cluster Compute (Stack Nodes)     2     $450.00         $900.00) Tj
0 -20 Td
(Layout-Aware Donut Engine License       1     $120.00         $120.00) Tj
0 -20 Td
(Managed VPC & Network Gateway           1      $75.00          $75.00) Tj
0 -25 Td
(---------------------------------------------------------------------------------------------------) Tj
0 -30 Td
(Subtotal: $1,095.00) Tj
0 -20 Td
(Tax (GST 8%): $87.60) Tj
0 -25 Td
(TOTAL AMOUNT DUE: {total_str}) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000229 00000 n 
0000000305 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
820
%%EOF
"""
    filepath = os.path.join(EVAL_DIR, filename)
    with open(filepath, "w", encoding="latin-1") as f:
        f.write(pdf_content)
    print(f"Generated {filepath}")

def main():
    print("Generating real & noisy evaluation documents in data/eval/...")
    
    # 1. Faded ink thermal receipt
    make_receipt_png(
        "receipt_faded_ink.png",
        "BLUE BOTTLE COFFEE",
        [("Cold Brew", 1, "5.25"), ("Avocado Toast", 1, "12.50")],
        "17.75",
        "2026-10-18",
        noise=True,
        faded=True
    )

    # 2. Crumpled cafe receipt with grain
    make_receipt_png(
        "receipt_crumpled_cafe.png",
        "STACK BISTRO & ESPRESSO",
        [("Latte Macchiato", 2, "9.00"), ("Blueberry Scone", 2, "7.00")],
        "16.00",
        "2026-10-20",
        noise=True,
        faded=False
    )

    # 3. Grocery market receipt with multi-line items
    make_receipt_png(
        "receipt_grocery_market.png",
        "ORGANIC WHOLE FOODS",
        [("Almond Milk", 2, "7.98"), ("Organic Bananas", 1, "2.49"), ("Dark Roast Coffee", 1, "14.99")],
        "25.46",
        "2026-10-19",
        noise=True,
        faded=False
    )

    # 4. Tech hardware store receipt
    make_receipt_png(
        "receipt_tech_supplies.png",
        "MICRO CENTER ELECTRONICS",
        [("USB-C Hub Multiport", 1, "34.99"), ("HDMI 2.1 Cable", 2, "19.98")],
        "54.97",
        "2026-10-15",
        noise=False,
        faded=False
    )

    # 5. Enterprise Invoice in PDF format
    make_pdf_invoice(
        "invoice_enterprise_stack.pdf",
        "Build with Stack Inc.",
        "2026-10-21",
        "$1,182.60"
    )

    # 6. Second PDF Invoice for multi-page/multi-format testing
    make_pdf_invoice(
        "invoice_consulting_services.pdf",
        "Global Systems Consulting",
        "2026-10-14",
        "$2,450.00"
    )

    # Ground truth mapping for evaluation matrix and benchmark comparison
    ground_truth = {
        "receipt_faded_ink.png": {
            "expected_vendor": "BLUE BOTTLE COFFEE",
            "expected_date": "2026-10-18",
            "expected_total": 17.75,
            "min_line_items": 2
        },
        "receipt_crumpled_cafe.png": {
            "expected_vendor": "STACK BISTRO & ESPRESSO",
            "expected_date": "2026-10-20",
            "expected_total": 16.00,
            "min_line_items": 2
        },
        "receipt_grocery_market.png": {
            "expected_vendor": "ORGANIC WHOLE FOODS",
            "expected_date": "2026-10-19",
            "expected_total": 25.46,
            "min_line_items": 3
        },
        "receipt_tech_supplies.png": {
            "expected_vendor": "MICRO CENTER ELECTRONICS",
            "expected_date": "2026-10-15",
            "expected_total": 54.97,
            "min_line_items": 2
        },
        "invoice_enterprise_stack.pdf": {
            "expected_vendor": "Build with Stack Inc.",
            "expected_date": "2026-10-21",
            "expected_total": 1182.60,
            "min_line_items": 3
        },
        "invoice_consulting_services.pdf": {
            "expected_vendor": "Global Systems Consulting",
            "expected_date": "2026-10-14",
            "expected_total": 2450.00,
            "min_line_items": 2
        }
    }

    gt_path = os.path.join(EVAL_DIR, "ground_truth.json")
    with open(gt_path, "w") as f:
        json.dump(ground_truth, f, indent=2)
    print(f"Generated ground truth benchmark at {gt_path}")
    print("All evaluation documents ready!")

if __name__ == "__main__":
    main()
