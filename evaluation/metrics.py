"""
Standardized Evaluation Metrics for Layout-Aware Document Extraction
Computes field correctness (vendor, date, total) and line-item precision/recall/F1
using string normalization, difflib fuzzy matching, and numeric equality tolerances.
"""

import re
import difflib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union

from backend.postprocessor import clean_amount

def normalize_text(text: Optional[Union[str, Any]]) -> str:
    """Normalizes text by lowercasing, stripping currency symbols, and collapsing whitespace."""
    if text is None:
        return ""
    s = str(text).lower()
    # Remove currency symbols and formatting punctuation
    s = re.sub(r"[\$,€£¥]", "", s)
    # Collapse multiple whitespaces and trim
    s = re.sub(r"\s+", " ", s).strip()
    return s

def parse_date_to_tuple(date_str: Optional[str]) -> Optional[Tuple[int, int, int]]:
    """Attempts to parse varied date string formats into (year, month, day)."""
    if not date_str:
        return None
    cleaned = normalize_text(date_str)
    
    formats = [
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%m/%d/%Y", "%m-%d-%Y",
        "%d/%m/%Y", "%d-%m-%Y",
        "%B %d, %Y", "%b %d, %Y",
        "%d %B %Y", "%d %b %Y"
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return (dt.year, dt.month, dt.day)
        except ValueError:
            continue
            
    # Try regex match for YYYY-MM-DD
    m = re.search(r"(\d{4})[\-\/\.](\d{1,2})[\-\/\.](\d{1,2})", cleaned)
    if m:
        try:
            return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    return None

def is_vendor_match(pred: Optional[str], expected: Optional[str], threshold: float = 0.85) -> bool:
    """Computes vendor match using difflib SequenceMatcher ratio >= threshold."""
    if not expected:
        return True  # If not specified in ground truth, cannot fail
    if not pred or pred in ["Unknown Vendor", "Unknown", "-", "N/A"]:
        return False
        
    norm_p = normalize_text(pred)
    norm_e = normalize_text(expected)
    if norm_p == norm_e:
        return True
        
    ratio = difflib.SequenceMatcher(None, norm_p, norm_e).ratio()
    return ratio >= threshold

def is_date_match(pred: Optional[str], expected: Optional[str]) -> bool:
    """Evaluates date equality using structured datetime parsing."""
    if not expected:
        return True
    if not pred or pred in ["N/A", "-", ""]:
        return False
        
    p_tuple = parse_date_to_tuple(pred)
    e_tuple = parse_date_to_tuple(expected)
    if p_tuple and e_tuple:
        return p_tuple == e_tuple
        
    return normalize_text(pred) == normalize_text(expected)

def is_total_match(pred_val: Any, expected_val: Any, tolerance: float = 0.01) -> bool:
    """Checks numeric equality within specified tolerance (default 0.01)."""
    if expected_val is None:
        return True
        
    p_num = clean_amount(pred_val)
    e_num = clean_amount(expected_val)
    if p_num is None or e_num is None:
        return False
        
    return abs(p_num - e_num) <= tolerance

def compute_line_items_f1(
    pred_items: List[Dict[str, Any]],
    expected_items: Optional[List[Dict[str, Any]]]
) -> Dict[str, float]:
    """
    Computes precision, recall, and F1 score for extracted table line items.
    Matches items based on fuzzy description similarity and price proximity.
    """
    if expected_items is None:
        # Ground truth did not define individual line items
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "matched_count": 0}

    if not pred_items and not expected_items:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "matched_count": 0}
    if not pred_items or not expected_items:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "matched_count": 0}

    matched_expected = set()
    true_positives = 0

    for p in pred_items:
        p_name = normalize_text(p.get("name") or p.get("description") or "")
        p_price = clean_amount(p.get("total_price") or p.get("line_total") or p.get("unit_price"))

        best_match_idx = None
        best_ratio = 0.0

        for idx, e in enumerate(expected_items):
            if idx in matched_expected:
                continue
            e_name = normalize_text(e.get("name") or e.get("description") or "")
            e_price = clean_amount(e.get("total_price") or e.get("line_total") or e.get("price"))

            ratio = difflib.SequenceMatcher(None, p_name, e_name).ratio()
            
            # Check price agreement if present in both
            price_agrees = True
            if p_price is not None and e_price is not None:
                price_agrees = abs(p_price - e_price) <= 0.05

            if ratio >= 0.70 and price_agrees and ratio > best_ratio:
                best_ratio = ratio
                best_match_idx = idx

        if best_match_idx is not None:
            matched_expected.add(best_match_idx)
            true_positives += 1

    precision = round(true_positives / len(pred_items), 4) if pred_items else 0.0
    recall = round(true_positives / len(expected_items), 4) if expected_items else 0.0
    f1 = round((2 * precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "matched_count": true_positives
    }

def evaluate_document_result(pred: Dict[str, Any], ground_truth: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluates extraction results against ground truth.
    Returns boolean correctness per field, table F1, and status.
    """
    if not ground_truth:
        return {
            "vendor_correct": bool(pred.get("vendor_name") and pred.get("vendor_name") != "Unknown Vendor"),
            "date_correct": bool(pred.get("date") and pred.get("date") != "N/A"),
            "total_correct": bool(pred.get("numeric_total") and pred.get("numeric_total") > 0),
            "line_items_f1": 1.0 if pred.get("line_items") else 0.0,
            "status": "PASS" if pred.get("numeric_total") else "WARN"
        }

    exp_vendor = ground_truth.get("expected_vendor")
    exp_date = ground_truth.get("expected_date")
    exp_total = ground_truth.get("expected_total")
    exp_items = ground_truth.get("expected_items")

    v_correct = is_vendor_match(pred.get("vendor_name"), exp_vendor)
    d_correct = is_date_match(pred.get("date"), exp_date)
    t_correct = is_total_match(pred.get("numeric_total") or pred.get("total_amount"), exp_total)
    
    table_metrics = compute_line_items_f1(pred.get("line_items", []), exp_items)

    # Determine status honestly
    if v_correct and d_correct and t_correct:
        status = "PASS"
    elif t_correct or (v_correct and d_correct):
        status = "PARTIAL"
    else:
        status = "FAIL"

    return {
        "vendor_correct": v_correct,
        "date_correct": d_correct,
        "total_correct": t_correct,
        "line_items_precision": table_metrics["precision"],
        "line_items_recall": table_metrics["recall"],
        "line_items_f1": table_metrics["f1"],
        "status": status
    }
