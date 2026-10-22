#!/usr/bin/env python3
"""
StackDoc - Layout-Aware Document Evaluation Suite
Runs honest evaluation against benchmark datasets, measuring real latency,
token confidence, field correctness, and table line-item F1 scores.
Never fabricates metrics.
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.utils import prepare_document_images
from backend.model import donut_engine
from backend.layout_extractor import layout_extractor, count_pdf_words
from evaluation.metrics import evaluate_document_result

# ANSI colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"

def print_header(title: str, dir_path: str):
    print("\n" + "=" * 90)
    print(f" {title.upper()}")
    print(f" Target Directory: {dir_path}")
    print(f" Device: {settings.DEVICE} | Model: {settings.MODEL_NAME}")
    print("=" * 90)

def warm_up_model():
    """Runs a warm-up inference so first-run initialization is excluded from benchmark latency."""
    print("Running model warm-up inference (excluded from timing)...")
    try:
        from PIL import Image
        dummy_img = Image.new("RGB", (200, 200), color=(255, 255, 255))
        donut_engine.load_model()
        if donut_engine.is_loaded:
            _ = donut_engine.parse_image(dummy_img)
            print("Warm-up complete.\n")
        else:
            print("Notice: Donut model is not loaded. Warm-up skipped.\n")
    except Exception as e:
        print(f"Warm-up notice: {e}\n")

def evaluate_directory(eval_dir: str) -> Dict[str, Any]:
    eval_path = Path(eval_dir)
    if not eval_path.exists():
        print(f"Directory '{eval_dir}' does not exist.")
        return {}

    gt_file = eval_path / "ground_truth.json"
    ground_truth = {}
    if gt_file.exists():
        try:
            with open(gt_file, "r", encoding="utf-8") as f:
                ground_truth = json.load(f)
        except Exception as e:
            print(f"Warning: Could not read ground truth file {gt_file}: {e}")

    valid_exts = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
    doc_files = [f for f in sorted(eval_path.iterdir()) if f.suffix.lower() in valid_exts]

    if not doc_files:
        print(f"No document files found in '{eval_dir}'.")
        return {}

    header = (
        f"{'DOCUMENT':<30} "
        f"{'ENGINE':<8} "
        f"{'VENDOR':<8} "
        f"{'DATE':<6} "
        f"{'TOTAL':<7} "
        f"{'F1':<6} "
        f"{'CONF':<7} "
        f"{'LATENCY':<9} "
        f"{'STATUS':<8}"
    )
    print(header)
    print("-" * 92)

    results = []
    latencies = []
    f1_scores = []
    confidences = []
    vendor_hits = 0
    date_hits = 0
    total_hits = 0
    pass_count = 0

    for doc_file in doc_files:
        filename = doc_file.name
        is_pdf = filename.lower().endswith(".pdf")

        with open(doc_file, "rb") as f:
            file_bytes = f.read()

        t0 = time.perf_counter()
        parsed = None
        engine_used = "donut"

        # Determine engine: layout engine for digital PDFs (>20 words), Donut for images
        if is_pdf and count_pdf_words(file_bytes) > 20:
            engine_used = "layout"
            try:
                parsed = layout_extractor.extract_document(file_bytes)
            except Exception as e:
                engine_used = "donut"

        if parsed is None:
            engine_used = "donut"
            try:
                images = prepare_document_images(file_bytes, filename)
                first_page = images[0]
                parsed = donut_engine.parse_image(first_page)
            except Exception as e:
                latency = round(time.perf_counter() - t0, 4)
                print(f"{filename:<30} {RED}ERROR: {str(e)[:45]}{RESET}")
                results.append({
                    "filename": filename,
                    "error": str(e),
                    "status": "FAIL",
                    "latency_seconds": latency
                })
                continue

        latency = round(time.perf_counter() - t0, 4)
        latencies.append(latency)

        gt = ground_truth.get(filename)
        eval_metrics = evaluate_document_result(parsed, ground_truth=gt)

        v_ok = eval_metrics["vendor_correct"]
        d_ok = eval_metrics["date_correct"]
        t_ok = eval_metrics["total_correct"]
        f1_val = eval_metrics["line_items_f1"]
        conf_val = parsed.get("confidence")
        status = eval_metrics["status"]

        if v_ok: vendor_hits += 1
        if d_ok: date_hits += 1
        if t_ok: total_hits += 1
        if status == "PASS": pass_count += 1
        if f1_val is not None: f1_scores.append(f1_val)
        if conf_val is not None: confidences.append(conf_val)

        v_str = f"{GREEN}YES{RESET}" if v_ok else f"{RED}NO{RESET}"
        d_str = f"{GREEN}YES{RESET}" if d_ok else f"{RED}NO{RESET}"
        t_str = f"{GREEN}YES{RESET}" if t_ok else f"{RED}NO{RESET}"
        f1_str = f"{f1_val:.2f}" if f1_val is not None else "-"
        conf_str = f"{int(conf_val * 100)}%" if conf_val is not None else "null"
        status_colored = f"{GREEN}PASS{RESET}" if status == "PASS" else (f"{YELLOW}PARTIAL{RESET}" if status == "PARTIAL" else f"{RED}FAIL{RESET}")

        print(
            f"{filename:<30} "
            f"{engine_used:<8} "
            f"{v_str:<17} "
            f"{d_str:<15} "
            f"{t_str:<16} "
            f"{f1_str:<6} "
            f"{conf_str:<7} "
            f"{latency:<9.4f} "
            f"{status_colored}"
        )

        results.append({
            "filename": filename,
            "engine": engine_used,
            "vendor_correct": v_ok,
            "date_correct": d_ok,
            "total_correct": t_ok,
            "line_items_f1": f1_val,
            "confidence": conf_val,
            "latency_seconds": latency,
            "status": status,
            "extracted": {
                "vendor_name": parsed.get("vendor_name"),
                "date": parsed.get("date"),
                "total_amount": parsed.get("total_amount"),
                "numeric_total": parsed.get("numeric_total"),
                "line_items_count": parsed.get("line_items_count")
            }
        })

    print("-" * 92)

    total_docs = len(doc_files)
    avg_latency = round(sum(latencies) / len(latencies), 4) if latencies else 0.0
    avg_f1 = round(sum(f1_scores) / len(f1_scores), 4) if f1_scores else 0.0
    avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else None
    vendor_acc = round((vendor_hits / total_docs) * 100, 1) if total_docs else 0.0
    date_acc = round((date_hits / total_docs) * 100, 1) if total_docs else 0.0
    total_acc = round((total_hits / total_docs) * 100, 1) if total_docs else 0.0

    print(f"\n{BOLD}AGGREGATE BENCHMARK RESULTS ({eval_dir}):{RESET}")
    print(f"  • Documents Evaluated : {total_docs}")
    print(f"  • Overall Pass Rate   : {pass_count}/{total_docs} ({round(pass_count / total_docs * 100, 1) if total_docs else 0}%)")
    print(f"  • Vendor Accuracy     : {vendor_hits}/{total_docs} ({vendor_acc}%)")
    print(f"  • Date Accuracy       : {date_hits}/{total_docs} ({date_acc}%)")
    print(f"  • Total Accuracy      : {total_hits}/{total_docs} ({total_acc}%)")
    print(f"  • Mean Table F1 Score : {avg_f1}")
    print(f"  • Mean Confidence     : {f'{int(avg_conf * 100)}%' if avg_conf is not None else 'null'}")
    print(f"  • Mean Latency        : {avg_latency}s\n")

    summary = {
        "directory": eval_dir,
        "total_documents": total_docs,
        "pass_count": pass_count,
        "vendor_accuracy": vendor_acc,
        "date_accuracy": date_acc,
        "total_accuracy": total_acc,
        "mean_f1": avg_f1,
        "mean_confidence": avg_conf,
        "mean_latency_seconds": avg_latency,
        "items": results
    }

    return summary

def save_results(primary_summary: Dict[str, Any], real_summary: Optional[Dict[str, Any]] = None):
    """Saves evaluation results into evaluation/results.json and evaluation/results.md."""
    output_dir = Path("evaluation")
    output_dir.mkdir(parents=True, exist_ok=True)

    json_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "eval": primary_summary,
        "eval_real": real_summary
    }

    json_path = output_dir / "results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)

    # Generate Markdown Report
    md_lines = [
        "# StackDoc Evaluation Benchmark Report",
        "",
        f"- **Generated:** `{json_data['timestamp']}`",
        f"- **Primary Test Set:** `{primary_summary.get('directory', 'data/eval')}`",
        f"- **Total Documents:** `{primary_summary.get('total_documents', 0)}`",
        f"- **Pass Rate:** `{primary_summary.get('pass_count', 0)}/{primary_summary.get('total_documents', 0)}`",
        f"- **Vendor Accuracy:** `{primary_summary.get('vendor_accuracy', 0.0)}%`",
        f"- **Date Accuracy:** `{primary_summary.get('date_accuracy', 0.0)}%`",
        f"- **Total Accuracy:** `{primary_summary.get('total_accuracy', 0.0)}%`",
        f"- **Mean Line-Item F1:** `{primary_summary.get('mean_f1', 0.0)}`",
        f"- **Mean Latency:** `{primary_summary.get('mean_latency_seconds', 0.0)}s`",
        "",
        "## Detailed Results",
        "",
        "| Document | Engine | Vendor Correct | Date Correct | Total Correct | Line Items F1 | Confidence | Latency (s) | Status |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]

    for item in primary_summary.get("items", []):
        v = "YES" if item.get("vendor_correct") else "NO"
        d = "YES" if item.get("date_correct") else "NO"
        t = "YES" if item.get("total_correct") else "NO"
        f1 = f"{item.get('line_items_f1', 0.0):.2f}" if item.get("line_items_f1") is not None else "-"
        conf = f"{int(item['confidence'] * 100)}%" if item.get("confidence") is not None else "null"
        lat = f"{item.get('latency_seconds', 0.0):.4f}"
        st = item.get("status", "FAIL")
        md_lines.append(f"| `{item['filename']}` | `{item.get('engine', '-')}` | {v} | {d} | {t} | {f1} | {conf} | {lat} | `{st}` |")

    if real_summary and real_summary.get("total_documents", 0) > 0:
        md_lines.extend([
            "",
            "## Real Documents Evaluation (`data/eval_real/`)",
            "",
            f"- **Documents Evaluated:** `{real_summary.get('total_documents')}`",
            f"- **Pass Rate:** `{real_summary.get('pass_count')}/{real_summary.get('total_documents')}`",
            f"- **Mean Latency:** `{real_summary.get('mean_latency_seconds')}s`",
            "",
            "| Document | Engine | Vendor Correct | Date Correct | Total Correct | Line Items F1 | Confidence | Latency (s) | Status |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        ])
        for item in real_summary.get("items", []):
            v = "YES" if item.get("vendor_correct") else "NO"
            d = "YES" if item.get("date_correct") else "NO"
            t = "YES" if item.get("total_correct") else "NO"
            f1 = f"{item.get('line_items_f1', 0.0):.2f}" if item.get("line_items_f1") is not None else "-"
            conf = f"{int(item['confidence'] * 100)}%" if item.get("confidence") is not None else "null"
            lat = f"{item.get('latency_seconds', 0.0):.4f}"
            st = item.get("status", "FAIL")
            md_lines.append(f"| `{item['filename']}` | `{item.get('engine', '-')}` | {v} | {d} | {t} | {f1} | {conf} | {lat} | `{st}` |")

    md_path = output_dir / "results.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"Saved evaluation benchmark artifacts:")
    print(f"  • JSON: {json_path}")
    print(f"  • Markdown: {md_path}\n")

def main():
    parser = argparse.ArgumentParser(description="StackDoc Layout-Aware Evaluation Framework")
    parser.add_argument("--dir", default="data/eval", help="Evaluation directory (default: data/eval)")
    parser.add_argument("--skip-warmup", action="store_true", help="Skip model warm-up inference")
    args = parser.parse_args()

    if not args.skip_warmup:
        warm_up_model()

    print_header("Evaluation Benchmark", args.dir)
    primary_summary = evaluate_directory(args.dir)

    # Optional real documents evaluation if data/eval_real exists
    real_summary = None
    real_dir = Path("data/eval_real")
    if real_dir.exists() and any(real_dir.iterdir()):
        print_header("Real Documents Evaluation", str(real_dir))
        real_summary = evaluate_directory(str(real_dir))

    if primary_summary:
        save_results(primary_summary, real_summary)

if __name__ == "__main__":
    main()
