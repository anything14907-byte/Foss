#!/usr/bin/env python3
"""
Exports evaluation outputs, downsized previews, and benchmark metrics
to assets/samples/, assets/results.json, and embeds them into index.html
so the static GitHub Pages showcase works fully offline and via file://.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from PIL import Image

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pymupdf as fitz

EVAL_DIR = Path("data/eval")
ASSETS_DIR = Path("assets")
SAMPLES_DIR = ASSETS_DIR / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_JSON = ASSETS_DIR / "results.json"
INDEX_HTML = Path("index.html")

def generate_preview_image(doc_path: Path, out_path: Path, max_dim: int = 500):
    """Renders or downsizes the first page of a document to a clean preview PNG."""
    filename_lower = doc_path.name.lower()
    
    if filename_lower.endswith(".pdf"):
        doc = fitz.open(doc_path)
        page = doc[0]
        # Render at decent scale
        zoom = 150.0 / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()
    else:
        img = Image.open(doc_path).convert("RGB")

    # Downscale while preserving aspect ratio
    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    img.save(out_path, "PNG", optimize=True)

def main():
    print("Exporting site data and generating preview thumbnails...")

    # Load cached real outputs
    cached_file = EVAL_DIR / "cached_outputs.json"
    cached_data = {}
    if cached_file.exists():
        with open(cached_file, "r", encoding="utf-8") as f:
            cached_data = json.load(f)

    # Load evaluation scorecard
    eval_benchmark_file = Path("evaluation/results.json")
    eval_benchmark = {}
    if eval_benchmark_file.exists():
        with open(eval_benchmark_file, "r", encoding="utf-8") as f:
            eval_benchmark = json.load(f)

    valid_exts = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
    doc_files = [f for f in sorted(EVAL_DIR.iterdir()) if f.suffix.lower() in valid_exts]

    samples_data = []

    for doc_file in doc_files:
        filename = doc_file.name
        preview_filename = f"{Path(filename).stem}_preview.png"
        preview_path = SAMPLES_DIR / preview_filename
        
        try:
            generate_preview_image(doc_file, preview_path)
            print(f"  Generated thumbnail: {preview_path}")
        except Exception as e:
            print(f"  Failed to generate preview for {filename}: {e}")

        extracted = cached_data.get(filename, {})
        
        # Match with benchmark item if available
        benchmark_items = eval_benchmark.get("eval", {}).get("items", [])
        matched_eval = next((it for it in benchmark_items if it.get("filename") == filename), {})

        samples_data.append({
            "filename": filename,
            "preview_url": f"assets/samples/{preview_filename}",
            "engine": extracted.get("engine", matched_eval.get("engine", "donut")),
            "vendor_name": extracted.get("vendor_name", "Unknown Vendor"),
            "date": extracted.get("date", "N/A"),
            "total_amount": extracted.get("total_amount", "0.00"),
            "numeric_total": extracted.get("numeric_total"),
            "subtotal": extracted.get("subtotal", "-"),
            "tax_amount": extracted.get("tax_amount", "-"),
            "line_items": extracted.get("line_items", []),
            "line_items_count": extracted.get("line_items_count", 0),
            "confidence": extracted.get("confidence", matched_eval.get("confidence")),
            "latency_seconds": extracted.get("latency_seconds", matched_eval.get("latency_seconds")),
            "status": matched_eval.get("status", "PASS" if extracted.get("numeric_total") else "FAIL"),
            "raw_output": extracted
        })

    site_data = {
        "timestamp": eval_benchmark.get("timestamp", ""),
        "summary": eval_benchmark.get("eval", {}),
        "real_summary": eval_benchmark.get("eval_real", {}),
        "samples": samples_data
    }

    # Write assets/results.json
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(site_data, f, indent=2)
    print(f"Saved {RESULTS_JSON}")

    # Embed data into index.html if file exists
    if INDEX_HTML.exists():
        with open(INDEX_HTML, "r", encoding="utf-8") as f:
            html = f.read()

        start_marker = "<!-- EMBEDDED_DATA_START -->"
        end_marker = "<!-- EMBEDDED_DATA_END -->"
        
        if start_marker in html and end_marker in html:
            embedded_block = (
                f"{start_marker}\n"
                f'  <script id="siteData" type="application/json">\n'
                f"{json.dumps(site_data, indent=2)}\n"
                f"  </script>\n"
                f"  {end_marker}"
            )
            prefix = html[:html.find(start_marker)]
            suffix = html[html.find(end_marker) + len(end_marker):]
            new_html = prefix + embedded_block + suffix
            with open(INDEX_HTML, "w", encoding="utf-8") as f:
                f.write(new_html)
            print(f"Embedded results data into {INDEX_HTML}")

    print("Site data export completed successfully.")

if __name__ == "__main__":
    main()
