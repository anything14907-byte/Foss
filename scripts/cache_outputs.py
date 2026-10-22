#!/usr/bin/env python3
"""
Runs genuine inferences over data/eval/ documents and saves real outputs
into data/eval/cached_outputs.json for optional offline demo mode (STACKDOC_DEMO_MODE=1).
Never fabricates data.
"""

import os
import sys
import json
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.utils import prepare_document_images
from backend.model import donut_engine
from backend.layout_extractor import layout_extractor, count_pdf_words

EVAL_DIR = Path("data/eval")
OUTPUT_FILE = EVAL_DIR / "cached_outputs.json"

def main():
    print("="*70)
    print(" Caching Real Inference Outputs for STACKDOC_DEMO_MODE")
    print(f" Source Directory: {EVAL_DIR}")
    print(f" Target File:      {OUTPUT_FILE}")
    print("="*70)

    if not EVAL_DIR.exists():
        print(f"Error: {EVAL_DIR} does not exist.")
        sys.exit(1)

    # Pre-load Donut model
    print("\nInitializing Donut model...")
    donut_engine.load_model()
    if not donut_engine.is_loaded:
        print("Warning: Donut model could not be loaded. Ensure model weights are cached.")

    valid_exts = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
    doc_files = [f for f in sorted(EVAL_DIR.iterdir()) if f.suffix.lower() in valid_exts]

    cached_results = {}

    for doc_file in doc_files:
        filename = doc_file.name
        print(f"\nProcessing: {filename} ...")
        t0 = time.perf_counter()

        with open(doc_file, "rb") as f:
            file_bytes = f.read()

        is_pdf = filename.lower().endswith(".pdf") or file_bytes.startswith(b"%PDF")
        parsed = None

        # If digital PDF with >20 words, use layout extractor
        if is_pdf and count_pdf_words(file_bytes) > 20:
            print(f"  -> Using Layout Engine for digital PDF '{filename}'")
            try:
                parsed = layout_extractor.extract_document(file_bytes)
            except Exception as e:
                print(f"  -> Layout engine failed ({e}), falling back to Donut")

        # Otherwise use Donut VLM
        if parsed is None and donut_engine.is_loaded:
            print(f"  -> Using Donut VLM for '{filename}'")
            images = prepare_document_images(file_bytes, filename)
            first_page = images[0]
            parsed = donut_engine.parse_image(first_page)

        latency = round(time.perf_counter() - t0, 4)

        if parsed:
            parsed["latency_seconds"] = latency
            parsed["execution_time_seconds"] = latency
            cached_results[filename] = parsed
            print(f"  [SUCCESS] Vendor: {parsed.get('vendor_name')} | Total: {parsed.get('total_amount')} | Confidence: {parsed.get('confidence')} | Latency: {latency}s")
        else:
            print(f"  [SKIPPED] Could not parse {filename}")

    # Save to JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(cached_results, f, indent=2)

    print("\n" + "="*70)
    print(f" Cached {len(cached_results)} real outputs to {OUTPUT_FILE}")
    print("="*70)

if __name__ == "__main__":
    main()
