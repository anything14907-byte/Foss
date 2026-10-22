"""
Layout-Aware Document Extraction Engine for Digital PDFs
Uses text coordinates, line clustering, and 2D bounding boxes via PyMuPDF (fitz)
to extract key-value pairs and multi-page tabular data without OCR.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Union

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

from backend.postprocessor import clean_amount

logger = logging.getLogger("stackdoc.layout_extractor")

# Standard Key-Value patterns (case-insensitive)
KV_PATTERNS = {
    "date": [r"\bdate\b", r"\binvoice\s*date\b", r"\bissued\s*date\b", r"\bbill\s*date\b"],
    "invoice_number": [r"\binvoice\s*(?:no|number|#)\b", r"\binv\s*(?:no|#)\b", r"\bbill\s*no\b"],
    "due_date": [r"\bdue\s*date\b", r"\bpayment\s*due\b"],
    "subtotal": [r"\bsub[\s\-]*total\b", r"\bnet\s*amount\b"],
    "tax": [r"\btax\s*\([^)]*\)", r"\btax\b", r"\bgst\b", r"\bvat\b", r"\bsales\s*tax\b"],
    "total": [
        r"\btotal\s*amount\s*due\b",
        r"\bamount\s*due\b",
        r"\bgrand\s*total\b",
        r"\btotal\s*amount\b",
        r"\btotal\s*due\b",
        r"\btotal\b"
    ],
    "bill_to": [r"\bbill\s*to\b", r"\binvoice\s*to\b", r"\bcustomer\b", r"\bclient\b"],
    "vendor": [r"\bfrom\b", r"\bvendor\b", r"\bcompany\b", r"\bpayee\b"]
}

TABLE_HEADER_KEYWORDS = [
    "description", "item", "particulars", "details",
    "qty", "quantity", "count",
    "price", "rate", "unit", "cost",
    "amount", "total", "line total"
]

def count_pdf_words(pdf_bytes: bytes) -> int:
    """Returns the total number of extractable digital words across all pages."""
    if not fitz:
        return 0
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_words = sum(len(page.get_text("words")) for page in doc)
        doc.close()
        return total_words
    except Exception:
        return 0

class LayoutAwarePdfExtractor:
    """
    Extracts structured key-value pairs and multi-page tables from digital PDF documents
    using word bounding boxes and geometric alignment.
    """
    def __init__(self, y_tolerance: float = 3.5):
        self.y_tolerance = y_tolerance

    def extract_document(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Parses a digital PDF and extracts metadata, key-values, and tabular items.
        """
        if not fitz:
            raise RuntimeError("PyMuPDF (fitz) is not installed.")

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        num_pages = len(doc)
        if num_pages == 0:
            doc.close()
            raise ValueError("The PDF document contains 0 pages.")

        all_page_lines: List[List[Dict[str, Any]]] = []
        for page_idx in range(num_pages):
            page = doc[page_idx]
            raw_words = page.get_text("words")
            lines = self._cluster_words_into_lines(raw_words, page_idx + 1)
            all_page_lines.append(lines)

        # 1. Extract Vendor (Heuristic: top-most prominent header line)
        vendor_info = self._extract_vendor(all_page_lines)

        # 2. Extract Key-Value Pairs with Bounding Boxes
        kv_data = self._extract_key_values(all_page_lines)

        # 3. Extract Tables (with multi-page continuation and header skipping)
        table_items, table_boxes = self._extract_tables(all_page_lines)

        doc.close()

        # Extract field values
        vendor_name = vendor_info.get("value") or "Unknown Vendor"
        date_val = kv_data.get("date", {}).get("value") or "N/A"
        total_val = kv_data.get("total", {}).get("value") or "0.00"
        subtotal_val = kv_data.get("subtotal", {}).get("value") or "-"
        tax_val = kv_data.get("tax", {}).get("value") or "-"
        invoice_no = kv_data.get("invoice_number", {}).get("value") or "-"
        due_date = kv_data.get("due_date", {}).get("value") or "-"

        # Clean numeric total
        num_total = clean_amount(total_val)
        if (num_total is None or num_total == 0) and table_items:
            computed = sum(item["numeric_price"] for item in table_items if item["numeric_price"] is not None)
            if computed > 0:
                num_total = round(computed, 2)
                total_val = f"{computed:.2f}"

        # Mathematical Reconciliation Check (sum(items) + tax == total)
        num_subtotal = clean_amount(subtotal_val)
        num_tax = clean_amount(tax_val)
        items_sum = sum(item.get("numeric_price") or 0.0 for item in table_items)
        expected_total = round((num_subtotal if num_subtotal is not None else items_sum) + (num_tax or 0.0), 2)
        reconciled = False
        if num_total is not None and num_total > 0:
            reconciled = abs(expected_total - num_total) <= 0.05 or abs(items_sum - num_total) <= 0.05

        math_reconciliation = {
            "reconciled": reconciled,
            "items_sum": round(items_sum, 2),
            "expected_total": expected_total,
            "actual_total": num_total,
            "formula": "subtotal + tax == total"
        }

        # Consolidate bounding boxes for UI canvas overlay
        boxes = {
            "vendor": vendor_info,
            "date": kv_data.get("date"),
            "total": kv_data.get("total"),
            "subtotal": kv_data.get("subtotal"),
            "tax": kv_data.get("tax"),
            "invoice_number": kv_data.get("invoice_number"),
            "line_items": table_boxes
        }

        return {
            "status": "success",
            "engine": "layout",
            "model": "PyMuPDF-LayoutAwareCoordinateExtractor",
            "method": "Coordinate-based 2D Layout & Table Extraction (Digital PDF)",
            "sponsor": "Build with Stack",
            "vendor_name": str(vendor_name).strip(),
            "date": str(date_val).strip(),
            "total_amount": str(total_val).strip(),
            "numeric_total": num_total,
            "subtotal": str(subtotal_val).strip(),
            "tax_amount": str(tax_val).strip(),
            "invoice_number": str(invoice_no).strip(),
            "due_date": str(due_date).strip(),
            "payment_method": "Invoice / Net Terms",
            "line_items": table_items,
            "line_items_count": len(table_items),
            "boxes": boxes,
            "confidence": 1.0,
            "confidence_score": 1.0,
            "math_reconciliation": math_reconciliation
        }

    def _cluster_words_into_lines(self, raw_words: List[Tuple], page_num: int) -> List[Dict[str, Any]]:
        """Groups words into horizontal lines based on y-center proximity."""
        if not raw_words:
            return []

        sorted_words = sorted(raw_words, key=lambda w: ((w[1] + w[3]) / 2.0, w[0]))
        
        lines: List[List[Tuple]] = []
        for w in sorted_words:
            w_y_center = (w[1] + w[3]) / 2.0
            matched_line = None
            for line in lines:
                line_y_center = sum((item[1] + item[3]) / 2.0 for item in line) / len(line)
                if abs(w_y_center - line_y_center) <= self.y_tolerance:
                    matched_line = line
                    break
            if matched_line is not None:
                matched_line.append(w)
            else:
                lines.append([w])

        structured_lines = []
        for line_words in lines:
            line_words.sort(key=lambda w: w[0])  # Sort left-to-right
            x0 = min(w[0] for w in line_words)
            y0 = min(w[1] for w in line_words)
            x1 = max(w[2] for w in line_words)
            y1 = max(w[3] for w in line_words)
            text = " ".join(w[4] for w in line_words).strip()
            is_divider = bool(re.match(r"^[\-\=\_\.\s]{4,}$", text))
            
            # Check if this line is genuinely a table header (requires both item/qty descriptor and price/total)
            lower_text = text.lower()
            if any(k in lower_text for k in ["total amount due", "amount due:", "due:", "$", "subtotal", "tax (", "tax:"]):
                is_header = False
            else:
                words_lower = [w[4].lower().strip(":.,") for w in line_words]
                primary_kw = ["description", "desc", "item", "particulars", "details", "qty", "quantity", "unit"]
                secondary_kw = ["price", "rate", "cost", "amount", "total", "line total"]
                has_primary = any(any(kw in wt for wt in words_lower) for kw in primary_kw)
                has_secondary = any(any(kw in wt for wt in words_lower) for kw in secondary_kw)
                is_header = has_primary and has_secondary

            structured_lines.append({
                "page": page_num,
                "text": text,
                "bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                "words": line_words,
                "is_divider": is_divider,
                "is_header": is_header,
                "y_center": (y0 + y1) / 2.0
            })

        structured_lines.sort(key=lambda l: l["y_center"])
        return structured_lines

    def _extract_vendor(self, all_page_lines: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Detects the company/vendor name from the top header of the first page."""
        if not all_page_lines or not all_page_lines[0]:
            return {"value": "Unknown Vendor", "bbox": None, "page": 1}

        page_lines = all_page_lines[0]
        for line in page_lines[:5]:
            text = line["text"]
            if line["is_divider"] or line["is_header"]:
                continue
            lower = text.lower()
            if any(k in lower for k in ["invoice", "date:", "bill to", "due date", "page"]):
                continue
            if len(text.strip()) >= 3:
                return {
                    "value": text.strip(),
                    "bbox": line["bbox"],
                    "page": line["page"]
                }
        return {"value": "Unknown Vendor", "bbox": None, "page": 1}

    def _extract_key_values(self, all_page_lines: List[List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
        """
        Detects key-value pairs using case-insensitive label matches and geometric proximity.
        Excludes table header rows.
        """
        extracted = {}

        for page_lines in all_page_lines:
            for idx, line in enumerate(page_lines):
                # Never extract key-values from table header lines or dividers
                if line["is_header"] or line["is_divider"]:
                    continue

                line_text = line["text"]
                line_words = line["words"]

                for field_key, patterns in KV_PATTERNS.items():
                    if field_key in extracted:
                        continue

                    for pattern in patterns:
                        match = re.search(pattern, line_text, re.IGNORECASE)
                        if not match:
                            continue

                        # Extract string after label
                        val_str = line_text[match.end():].strip().lstrip(":- ")
                        
                        if val_str and not val_str.startswith("----"):
                            # Determine bounding box of value words
                            val_words = [w for w in line_words if w[4] in val_str]
                            if val_words:
                                vx0 = min(w[0] for w in val_words)
                                vy0 = min(w[1] for w in val_words)
                                vx1 = max(w[2] for w in val_words)
                                vy1 = max(w[3] for w in val_words)
                                bbox = [round(vx0, 2), round(vy0, 2), round(vx1, 2), round(vy1, 2)]
                            else:
                                bbox = line["bbox"]

                            extracted[field_key] = {
                                "value": val_str,
                                "bbox": bbox,
                                "page": line["page"]
                            }
                            break
                        else:
                            # Value is directly below on the next line
                            next_idx = idx + 1
                            while next_idx < len(page_lines) and page_lines[next_idx]["is_divider"]:
                                next_idx += 1
                                
                            if next_idx < len(page_lines):
                                next_line = page_lines[next_idx]
                                if not next_line["is_header"] and (next_line["y_center"] - line["y_center"] < 35):
                                    below_val = next_line["text"].strip()
                                    if below_val and not any(re.search(p, below_val, re.I) for p_list in KV_PATTERNS.values() for p in p_list):
                                        extracted[field_key] = {
                                            "value": below_val,
                                            "bbox": next_line["bbox"],
                                            "page": next_line["page"]
                                        }
                                        break
        return extracted

    def _extract_tables(self, all_page_lines: List[List[Dict[str, Any]]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Detects tables, extracts column ranges, and handles multi-page continuation
        with repeated header skipping and hierarchical nested modifier extraction.
        """
        all_items: List[Dict[str, Any]] = []
        all_boxes: List[Dict[str, Any]] = []
        active_column_ranges: Optional[Dict[str, Tuple[float, float]]] = None
        modifier_prefixes = ("+", "-", "*", "discount:", "add-on:", "addon:", "option:", "includes:", "with ")

        for page_idx, page_lines in enumerate(all_page_lines):
            page_num = page_idx + 1
            start_line_idx = 0

            # Step A: Look for table header on this page
            header_idx = None
            for idx, line in enumerate(page_lines):
                if line["is_header"]:
                    header_idx = idx
                    break

            if header_idx is not None:
                header_line = page_lines[header_idx]
                active_column_ranges = self._derive_column_ranges(header_line)
                start_line_idx = header_idx + 1
            elif active_column_ranges is not None:
                start_line_idx = 0
            else:
                continue

            # Step B: Parse rows following header
            line_idx = start_line_idx
            while line_idx < len(page_lines):
                line = page_lines[line_idx]
                line_idx += 1

                if line["is_divider"] or line["is_header"]:
                    continue

                text = line["text"]
                lower = text.lower().strip()

                # Stop conditions: totals, tax, footer, notes
                if any(k in lower for k in ["subtotal", "sub-total", "tax", "gst", "vat", "total amount", "amount due", "thank you", "terms", "notes:"]):
                    break

                # Check if this line is an indented child or modifier of the previous item
                is_modifier = False
                if all_items:
                    parent_bbox = all_items[-1].get("bbox")
                    has_mod_prefix = any(lower.startswith(p) for p in modifier_prefixes)
                    is_indented = bool(parent_bbox and line["bbox"][0] > parent_bbox[0] + 12)
                    if has_mod_prefix or is_indented:
                        is_modifier = True

                if is_modifier:
                    mod_item = self._parse_line_to_item(line, active_column_ranges, 0)
                    mod_name = text.lstrip("+-* ").strip()
                    mod_price = None
                    mod_num = None
                    if mod_item:
                        mod_name = mod_item["name"].lstrip("+-* ").strip()
                        mod_price = mod_item["line_total"]
                        mod_num = mod_item["numeric_price"]
                    else:
                        words = line["words"]
                        if words:
                            last_token = words[-1][4]
                            c = clean_amount(last_token)
                            if c is not None:
                                mod_num = c
                                mod_price = last_token
                                mod_name = " ".join(w[4] for w in words[:-1]).lstrip("+-* ").strip()

                    all_items[-1]["modifiers"].append({
                        "name": mod_name,
                        "price": mod_price,
                        "numeric_price": mod_num,
                        "bbox": line["bbox"]
                    })
                    all_boxes.append({
                        "name": f"Modifier: {mod_name}",
                        "bbox": line["bbox"],
                        "page": page_num
                    })
                    continue

                item = self._parse_line_to_item(line, active_column_ranges, len(all_items) + 1)
                if item:
                    all_items.append(item)
                    all_boxes.append({
                        "name": item["name"],
                        "bbox": line["bbox"],
                        "page": page_num
                    })

        return all_items, all_boxes

    def _derive_column_ranges(self, header_line: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
        """Determines the horizontal spans of description, quantity, price, and total columns."""
        words = header_line["words"]
        col_positions = []
        for w in words:
            wt = w[4].lower().strip(":.,")
            col_type = None
            if any(k in wt for k in ["desc", "item", "particular"]):
                col_type = "description"
            elif any(k in wt for k in ["qty", "quant", "cnt"]):
                col_type = "quantity"
            elif any(k in wt for k in ["unit", "price", "rate"]):
                col_type = "unit_price"
            elif any(k in wt for k in ["total", "amount"]):
                col_type = "line_total"
            
            if col_type:
                col_positions.append((col_type, w[0], w[2]))

        col_positions.sort(key=lambda c: c[1])
        ranges: Dict[str, Tuple[float, float]] = {}
        for i, (col_name, x0, x1) in enumerate(col_positions):
            end_x = col_positions[i+1][1] - 5 if i + 1 < len(col_positions) else 1000.0
            ranges[col_name] = (x0 - 15.0, end_x)

        return ranges

    def _parse_line_to_item(
        self,
        line: Dict[str, Any],
        col_ranges: Optional[Dict[str, Tuple[float, float]]],
        line_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parses a table row line into description, quantity, unit price, and total.
        Uses right-to-left numeric classification combined with coordinate bounding boxes.
        """
        words = line["words"]
        if not words or len(words) < 2:
            return None

        # Check numeric tokens from right to left
        tokens = [w[4] for w in words]
        
        # Helper to test if a token is a price or number
        def is_numeric_token(t: str) -> bool:
            c = re.sub(r"[\$,€£]", "", t).strip()
            try:
                float(c.replace(",", ""))
                return True
            except ValueError:
                return False

        # Find price/quantity positions from the right
        price_indices = []
        for i in range(len(tokens) - 1, -1, -1):
            if is_numeric_token(tokens[i]):
                price_indices.append(i)

        if not price_indices:
            return None

        price_indices.reverse()  # now in left-to-right order

        if len(price_indices) >= 3:
            # e.g., [2, $450.00, $900.00] -> qty, unit, total
            qty_idx = price_indices[-3]
            unit_idx = price_indices[-2]
            total_idx = price_indices[-1]
            desc = " ".join(tokens[:qty_idx]).strip()
            qty = tokens[qty_idx].strip()
            unit = tokens[unit_idx].strip()
            total = tokens[total_idx].strip()
        elif len(price_indices) == 2:
            # e.g., [1, $120.00] -> qty, total
            qty_idx = price_indices[0]
            total_idx = price_indices[1]
            desc = " ".join(tokens[:qty_idx]).strip()
            qty = tokens[qty_idx].strip()
            unit = tokens[total_idx].strip()
            total = tokens[total_idx].strip()
        else:
            # 1 numeric token: treat as total with qty 1
            total_idx = price_indices[0]
            desc = " ".join(tokens[:total_idx]).strip()
            qty = "1"
            unit = tokens[total_idx].strip()
            total = tokens[total_idx].strip()

        if not desc:
            return None

        num_price = clean_amount(total)

        return {
            "line_number": line_number,
            "name": desc,
            "description": desc,
            "quantity": qty,
            "unit_price": unit,
            "line_total": total,
            "total_price": total,
            "numeric_price": num_price,
            "modifiers": [],
            "page": line["page"],
            "bbox": line["bbox"]
        }

# Singleton instance
layout_extractor = LayoutAwarePdfExtractor()
