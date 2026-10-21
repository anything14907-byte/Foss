from typing import Dict, Any, Tuple

def evaluate_document_result(result: Dict[str, Any], ground_truth: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Evaluates extraction quality for a document.
    Returns status (PASS/WARN/FAIL), field scores, and aggregated confidence.
    """
    vendor = result.get("vendor_name", "")
    date_val = result.get("date", "")
    total = result.get("total_amount", "")
    num_total = result.get("numeric_total")
    items = result.get("line_items", [])
    confidence = result.get("confidence_score", 0.85)

    vendor_valid = bool(vendor and vendor not in ["Unknown Vendor", "Unknown", "-", "N/A"])
    date_valid = bool(date_val and date_val not in ["N/A", "-", ""])
    total_valid = bool(total and total not in ["0.00", "$0.00", "-", ""]) or (num_total is not None and num_total > 0)
    items_valid = len(items) > 0

    score = 0
    if vendor_valid: score += 1
    if date_valid: score += 1
    if total_valid: score += 1
    if items_valid: score += 1

    # Check against ground truth if present
    gt_matched = True
    if ground_truth:
        if ground_truth.get("expected_total") and num_total:
            # Allow minor delta
            if abs(ground_truth["expected_total"] - num_total) > 2.0:
                gt_matched = False

    if score >= 3 and total_valid:
        status = "PASS"
    elif score >= 2:
        status = "WARN"
    else:
        status = "FAIL"

    return {
        "status": status,
        "score_out_of_4": score,
        "vendor_valid": vendor_valid,
        "date_valid": date_valid,
        "total_valid": total_valid,
        "items_valid": items_valid,
        "line_items_count": len(items),
        "confidence": confidence,
        "gt_matched": gt_matched
    }
