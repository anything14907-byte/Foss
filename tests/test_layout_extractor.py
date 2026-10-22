"""
Tests for Layout-Aware Digital PDF Extractor (backend.layout_extractor)
Tests multi-page table continuation, repeated header skipping, and bounding boxes.
"""

import os
import io
import pytest
import pymupdf as fitz

from backend.layout_extractor import layout_extractor, count_pdf_words

def create_synthetic_multipage_pdf() -> bytes:
    """
    Generates a 2-page invoice PDF where a table starts on page 1
    and continues on page 2 with a repeated table header.
    """
    doc = fitz.open()

    # Page 1: Metadata, Header, Table Items 1 & 2
    page1 = doc.new_page(width=612, height=792)
    p1_text = (
        "Acme Enterprise Cloud Services\n"
        "Date: 2026-11-01\n"
        "Invoice Number: INV-9901\n"
        "Bill To: Widget Corp\n"
        "----------------------------------------------------\n"
        "Item Description                Qty   Unit Price   Total\n"
        "Dedicated Kubernetes Master Node 1     $800.00     $800.00\n"
        "High-Memory Worker Node          4     $300.00     $1200.00\n"
    )
    page1.insert_text((50, 60), p1_text, fontsize=11)

    # Page 2: Repeated Table Header, Table Items 3 & 4, Subtotal & Total
    page2 = doc.new_page(width=612, height=792)
    p2_text = (
        "Item Description                Qty   Unit Price   Total\n"
        "Persistent Block Storage SSD    10    $50.00      $500.00\n"
        "Global CDN & TLS Gateway        1     $150.00     $150.00\n"
        "----------------------------------------------------\n"
        "Subtotal: $2,650.00\n"
        "Tax (VAT 10%): $265.00\n"
        "TOTAL AMOUNT DUE: $2,915.00\n"
    )
    page2.insert_text((50, 60), p2_text, fontsize=11)

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

def test_multipage_table_extraction():
    """Asserts table continuing across pages with repeated header on page 2 is parsed completely."""
    pdf_bytes = create_synthetic_multipage_pdf()
    assert count_pdf_words(pdf_bytes) > 20

    res = layout_extractor.extract_document(pdf_bytes)

    assert res["status"] == "success"
    assert res["engine"] == "layout"
    assert "Acme Enterprise" in res["vendor_name"]
    assert res["date"] == "2026-11-01"
    assert res["numeric_total"] == 2915.00

    # Ensure all 4 line items across both pages were captured
    assert res["line_items_count"] == 4, f"Expected 4 line items, got {res['line_items_count']}"
    
    item_names = [it["name"] for it in res["line_items"]]
    assert any("Kubernetes Master" in name for name in item_names)
    assert any("High-Memory Worker" in name for name in item_names)
    assert any("Persistent Block Storage" in name for name in item_names)
    assert any("Global CDN" in name for name in item_names)

    # Check pages for items
    pages = [it["page"] for it in res["line_items"]]
    assert 1 in pages and 2 in pages

    # Verify bounding boxes are within page bounds (0..612, 0..792)
    for it in res["line_items"]:
        bbox = it["bbox"]
        assert bbox is not None
        assert 0 <= bbox[0] < bbox[2] <= 612
        assert 0 <= bbox[1] < bbox[3] <= 792

def test_enterprise_stack_pdf():
    """Tests extraction on data/eval/invoice_enterprise_stack.pdf."""
    path = "data/eval/invoice_enterprise_stack.pdf"
    assert os.path.exists(path)
    with open(path, "rb") as f:
        pdf_bytes = f.read()

    res = layout_extractor.extract_document(pdf_bytes)
    assert res["status"] == "success"
    assert "Build with Stack" in res["vendor_name"]
    assert res["date"] == "2026-10-21"
    assert res["numeric_total"] == 1182.60
    assert res["line_items_count"] == 3
    assert res["confidence"] == 1.0
    assert res["math_reconciliation"]["reconciled"] is True

def test_consulting_services_pdf():
    """Tests extraction on data/eval/invoice_consulting_services.pdf (Adversarial mismatch test)."""
    path = "data/eval/invoice_consulting_services.pdf"
    assert os.path.exists(path)
    with open(path, "rb") as f:
        pdf_bytes = f.read()

    res = layout_extractor.extract_document(pdf_bytes)
    assert res["status"] == "success"
    assert "Global Systems Consulting" in res["vendor_name"]
    assert res["date"] == "2026-10-14"
    assert res["numeric_total"] == 2450.00
    assert res["line_items_count"] == 3
    assert res["confidence"] == 1.0
    # Consulting services PDF tests adversarial math mismatch: printed total 2450 != 1095 + 87.60
    assert res["math_reconciliation"]["reconciled"] is False

def test_nested_modifiers_and_math_reconciliation():
    """Verifies that indented child rows or modifier prefixes (+, -) are attached as modifiers."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    p_text = (
        "Apex Cloud Infrastructure\n"
        "Date: 2026-10-22\n"
        "Invoice Number: INV-7711\n"
        "----------------------------------------------------\n"
        "Item Description                Qty   Unit Price   Total\n"
        "Enterprise Dedicated Cluster     1     $1000.00    $1000.00\n"
        "  + 24/7 Priority Support SLA    1     $200.00     $200.00\n"
        "  - Automated Disaster Recovery  1     $100.00     $100.00\n"
        "Database Sharding Cluster       2     $300.00     $600.00\n"
        "----------------------------------------------------\n"
        "Subtotal: $1,900.00\n"
        "Tax: $190.00\n"
        "TOTAL AMOUNT DUE: $2,090.00\n"
    )
    page.insert_text((50, 60), p_text, fontsize=11)
    pdf_bytes = doc.write()
    doc.close()

    res = layout_extractor.extract_document(pdf_bytes)
    assert res["status"] == "success"
    assert res["line_items_count"] == 2  # 2 main items, modifiers attached
    assert len(res["line_items"][0]["modifiers"]) == 2
    assert "Priority Support" in res["line_items"][0]["modifiers"][0]["name"]
    assert res["math_reconciliation"]["reconciled"] is True
    assert res["math_reconciliation"]["actual_total"] == 2090.00

