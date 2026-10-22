import re
import json
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("stackdoc.postprocessor")

def parse_donut_xml_tokens(text: str) -> Dict[str, Any]:
    """
    Fallback parser for Donut XML tags if token2json encounters an issue.
    Parses <s_tag>content</s_tag> hierarchical tokens into a nested Python dict.
    """
    # Remove task prompt prefix if present
    text = re.sub(r"^<s_[a-zA-Z0-9_\-]+>", "", text.strip())
    # Remove end task tokens
    text = re.sub(r"</s>$", "", text)
    
    # Recursive tag extractor
    def _extract_tags(fragment: str) -> Union[Dict[str, Any], List[Any], str]:
        pattern = re.compile(r"<s_([^>]+)>(.*?)</s_\1>", re.DOTALL)
        matches = list(pattern.finditer(fragment))
        
        if not matches:
            # Check if self-closing or leftover text
            clean = re.sub(r"</?s_[^>]+>", "", fragment).strip()
            return clean
            
        result: Dict[str, Any] = {}
        for match in matches:
            tag, inner = match.group(1), match.group(2)
            parsed_child = _extract_tags(inner)
            
            if tag in result:
                if isinstance(result[tag], list):
                    result[tag].append(parsed_child)
                else:
                    result[tag] = [result[tag], parsed_child]
            else:
                result[tag] = parsed_child
                
        return result

    try:
        parsed = _extract_tags(text)
        return parsed if isinstance(parsed, dict) else {"raw_content": parsed}
    except Exception as e:
        logger.warning(f"XML token fallback parser failed: {e}")
        return {"raw_content": text}

def clean_amount(val: Any) -> Optional[float]:
    """
    Extracts a numeric float from strings like '$12.99', '12,99', '1,250.00'.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str):
        val = str(val)
        
    val = val.strip()
    # Match currency patterns
    clean = re.sub(r"[^\d.,\-]", "", val)
    if not clean:
        return None
    
    # If comma used as decimal separator (e.g. 12,50)
    if "," in clean and "." not in clean:
        clean = clean.replace(",", ".")
    elif "," in clean and "." in clean:
        # e.g., 1,234.56 -> remove thousands separator
        if clean.rfind(",") < clean.rfind("."):
            clean = clean.replace(",", "")
        else:
            clean = clean.replace(".", "").replace(",", ".")
            
    try:
        return float(clean)
    except ValueError:
        return None

def find_deep_value(data: Any, target_keys: List[str]) -> Optional[Any]:
    """
    Recursively searches dictionary/list for the first occurrence of any target key.
    Prioritizes exact matches and prevents 'sub_total' from falsely matching 'total'.
    """
    if isinstance(data, dict):
        # 1. Exact key match
        for target in target_keys:
            target_lower = target.lower()
            for k, v in data.items():
                k_lower = k.lower()
                if k_lower == target_lower and v is not None and not isinstance(v, (dict, list)):
                    return v

        # 2. Substring matches with sub-total exclusion
        for target in target_keys:
            target_lower = target.lower()
            for k, v in data.items():
                k_lower = k.lower()
                if "sub" not in target_lower and "sub" in k_lower:
                    continue
                if target_lower in k_lower:
                    if v is not None and not isinstance(v, (dict, list)):
                        return v
                    elif isinstance(v, dict):
                        res = find_deep_value(v, [target])
                        if res is not None:
                            return res

        # 3. Recursive traversal of child dicts and lists
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                # If searching for total, skip subtotal blocks
                if any("total" in t.lower() and "sub" not in t.lower() for t in target_keys) and "sub" in k.lower():
                    continue
                res = find_deep_value(v, target_keys)
                if res is not None:
                    return res

    elif isinstance(data, list):
        for item in data:
            res = find_deep_value(item, target_keys)
            if res is not None:
                return res
    return None

def normalize_line_items(raw_data: Any) -> List[Dict[str, Any]]:
    """
    Extracts line items from CORD menu structures or generic tables.
    """
    items = []
    
    # Check for 'menu' in CORD format
    menu_data = None
    if isinstance(raw_data, dict):
        for key in ["menu", "items", "line_items", "order"]:
            if key in raw_data:
                menu_data = raw_data[key]
                break
                
    if menu_data is None:
        # Look for sub-menus
        for k, v in (raw_data.items() if isinstance(raw_data, dict) else []):
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                menu_data = v
                break
                
    if menu_data:
        if isinstance(menu_data, dict):
            menu_data = [menu_data]
            
        for idx, entry in enumerate(menu_data):
            if not isinstance(entry, dict):
                continue
                
            name = (
                entry.get("nm") or entry.get("name") or 
                entry.get("description") or entry.get("item") or f"Item {idx + 1}"
            )
            cnt = entry.get("cnt") or entry.get("quantity") or entry.get("qty") or "1"
            price = entry.get("price") or entry.get("unit_price") or entry.get("item_price") or entry.get("total")
            
            # Sub-price check if nested
            sub_val = entry.get("sub") or {}
            if isinstance(sub_val, dict):
                if not price:
                    price = sub_val.get("price")
                if not name and "nm" in sub_val:
                    name = sub_val.get("nm")
            
            items.append({
                "line_number": idx + 1,
                "name": str(name).strip() if name else "Unknown Item",
                "quantity": str(cnt).strip() if cnt else "1",
                "unit_price": str(price).strip() if price else "-",
                "total_price": str(price).strip() if price else "-",
                "numeric_price": clean_amount(price)
            })
            
    return items

def postprocess_donut_output(
    donut_output: Union[Dict[str, Any], str],
    raw_sequence: str = "",
    confidence: Optional[float] = None
) -> Dict[str, Any]:
    """
    Transforms raw Donut token/JSON output into the standardized invoice/receipt schema:
    - Vendor Name
    - Date
    - Total Amount
    - Line Items
    - Subtotal, Tax, Payment Method
    - Layout & Model Metadata
    - Honest token probability confidence (float 0-1, or None)
    """
    if isinstance(donut_output, str):
        parsed_data = parse_donut_xml_tokens(donut_output)
    else:
        parsed_data = donut_output or {}

    # Extract vendor / store name
    vendor_name = (
        find_deep_value(parsed_data, ["store_name", "vendor", "merchant", "nm", "seller", "company", "brand_name"])
        or "Unknown Vendor"
    )
    
    # Extract date
    date_val = (
        find_deep_value(parsed_data, ["date", "trans_date", "issued_date", "time", "date_time"])
        or "N/A"
    )
    
    # Extract total
    total_val = (
        find_deep_value(parsed_data, ["total_price", "grand_total", "total", "amount_due", "cash"])
        or "0.00"
    )
    
    # Extract subtotal
    subtotal_val = (
        find_deep_value(parsed_data, ["subtotal_price", "sub_total", "subtotal", "net_amount"])
        or "-"
    )
    
    # Extract tax
    tax_val = (
        find_deep_value(parsed_data, ["tax_price", "vat", "tax", "gst"])
        or "-"
    )
    
    # Extract payment method
    payment_method = (
        find_deep_value(parsed_data, ["pay_method", "payment", "card", "cash", "tender"])
        or "Standard"
    )
    
    # Extract line items
    line_items = normalize_line_items(parsed_data)
    
    # Numeric clean
    num_total = clean_amount(total_val)
    
    # If line items exist but total is 0, estimate total from items
    if (num_total is None or num_total == 0) and line_items:
        computed = sum(item["numeric_price"] for item in line_items if item["numeric_price"] is not None)
        if computed > 0:
            num_total = round(computed, 2)
            total_val = f"{computed:.2f}"
            
    return {
        "status": "success",
        "model": "naver-clova-ix/donut-base-finetuned-cord-v2",
        "method": "Layout-Aware Vision-Language Transformer (No Plain-Text OCR)",
        "sponsor": "Build with Stack",
        "vendor_name": str(vendor_name).strip(),
        "date": str(date_val).strip(),
        "total_amount": str(total_val).strip(),
        "numeric_total": num_total,
        "subtotal": str(subtotal_val).strip(),
        "tax_amount": str(tax_val).strip(),
        "payment_method": str(payment_method).strip(),
        "line_items": line_items,
        "line_items_count": len(line_items),
        "confidence": confidence,
        "confidence_score": confidence,
        "raw_donut_json": parsed_data,
        "raw_tokens": raw_sequence[:500] if raw_sequence else ""
    }
