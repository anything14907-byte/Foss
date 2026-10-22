# StackDoc: Layout-Aware Document Understanding

> A dual-engine, layout-aware document understanding system that extracts key-value pairs (Vendor, Date, Subtotal, Tax, Total) and hierarchical line items with nested modifiers from digital invoices and scanned receipts.

[![GitHub Repository](https://img.shields.io/badge/GitHub-anything14907--byte-10b981.svg)](https://github.com/anything14907-byte/Foss)
[![GitHub Pages](https://img.shields.io/badge/Showcase-Static_GitHub_Pages-b8381e.svg)](https://anything14907-byte.github.io/Foss/)
[![Manifest V3](https://img.shields.io/badge/Extension-Chrome_Manifest_V3-38bdf8.svg)](#chrome-browser-extension-manifest-v3)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 1. What StackDoc Does

Traditional document extractors treat documents as flat token streams, stripping away 2D spatial relationships. When tables span columns, items have indented sub-options, or key-values are arranged in multi-column grids, flat OCR loses the structural context.

StackDoc solves this by preserving 2D spatial geometry `[x0, y0, x1, y1]` and using layout awareness across two environments:

### In-Browser Static Showcase (`index.html`)
Runs **100% client-side** on GitHub Pages or local static server without requiring an active backend:
- **Digital Vector PDFs**: Text tokens and exact 2D bounding boxes `[x0, y0, x1, y1]` are read directly from PDF content streams via pinned `pdf.js` (v3.11.174).
- **Scans & Photos (PNG, JPG, WEBP)**: In-browser optical character recognition via pinned `Tesseract.js` (v5.1.1) WebAssembly engine, extracting word-level bounding boxes and confidence scores.
- **Layout Reconstruction**: Spatial clustering groups words into lines, detects table boundaries, and identifies hierarchical modifiers via horizontal indentation analysis (`Δx0 > 14px`).
- **Multi-Currency Math Reconciliation**: Parses `$`, `€`, `£`, `¥`, `₹`, `Rs.`, `INR`, thousand separators, and comma decimals. Verifies whether `Subtotal + Tax == Total`, flagging exact discrepancies.

### Python Backend Pipeline (`backend/`)
For local production processing and high-throughput evaluation:
- **Vector Layout Engine (`backend/layout_extractor.py`)**: Uses `PyMuPDF` (`fitz`) for sub-30ms deterministic table chaining and key-value extraction across multi-page digital PDFs.
- **Vision-Language Transformer (`backend/model.py`)**: Uses Clova AI Donut (`naver-clova-ix/donut-base-finetuned-cord-v2`), combining a Swin Transformer visual encoder and mBART sequence decoder to read document image tensors directly into structured JSON tokens with true token transition probabilities.
- **Dynamic Mode Routing**: Endpoint `/parse-document?mode=auto|donut|layout` automatically routes digital PDFs to the layout engine and raster scans to the vision model.

---

## 2. Real vs. Precomputed Behavior

To ensure complete transparency regarding how data is presented across the showcase:

| Component | Source & Execution | Transparency Guarantee |
| :--- | :--- | :--- |
| **Preset Samples** (`#studio`) | Precomputed outputs from the Python pipeline (`PyMuPDF` & `Donut`) cached in `assets/results.json`. | Labeled explicitly as `"Sample (precomputed with the Python pipeline)"`. Guarantees instant interactive inspection of benchmark documents. |
| **Live File Upload** (`#studio`) | **100% Real Live In-Browser Execution**. Lazy-loads `pdf.js` or `Tesseract.js` upon file selection. | Labeled `"Live in-browser"`. Never invents fallback values. Unreadable scans report low confidence and missing fields as `— (Not detected)`. |
| **Benchmark Metrics** (`#results`) | Measured on a small sanity-check dataset (6 synthetic documents in `data/eval/`). | Labeled as `"Small sanity check: 6 synthetic documents, not a general accuracy claim"`. Loaded dynamically from `evaluation/results.json`. |
| **Architectural Comparison** (`#compare`) | Compares PyMuPDF Vector Layout, Donut VLM, and LayoutLMv3. | Latency ranges for Donut and LayoutLMv3 are clearly marked as typical published literature ranges, not measured in-house. |

---

## 3. Benchmark Scorecard

Results generated directly by running `python evaluate.py` on the benchmark evaluation set:

- **Total Documents:** `6` (2 Digital Invoices, 4 Scanned Receipts)
- **Digital Vector PDF F1:** `1.00` (100% precision and recall on consulting & enterprise invoices)
- **Vector Engine Latency:** `< 0.03s`
- **Mean Table Line-Item F1:** `0.3333` (computed as `2 × (Precision × Recall) / (Precision + Recall)` at row-level match threshold 0.8)
- **Mean Latency:** `2.11s` (dominated by Donut CPU inference on scanned receipts)

| Document | Engine | Vendor Match | Date Match | Total Match | Line Items F1 | Real Latency | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `invoice_consulting_services.pdf` | `layout` (PyMuPDF) | YES | YES | YES | 1.00 | 0.0268s | `PASS` |
| `invoice_enterprise_stack.pdf` | `layout` (PyMuPDF) | YES | YES | YES | 1.00 | 0.0041s | `PASS` |
| `receipt_crumpled_cafe.png` | `donut` (VLM) | NO | NO | NO | 0.00 | 3.2963s | `FAIL` |
| `receipt_faded_ink.png` | `donut` (VLM) | NO | NO | NO | 0.00 | 3.4568s | `FAIL` |
| `receipt_grocery_market.png` | `donut` (VLM) | NO | NO | NO | 0.00 | 2.8718s | `FAIL` |
| `receipt_tech_supplies.png` | `donut` (VLM) | NO | NO | NO | 0.00 | 2.9998s | `FAIL` |

*Note on Failures:* The 4 synthetic receipts feature plain geometric shapes that fall outside Donut's CORD-v2 training distribution. Rather than hallucinating incorrect characters, the model reports low confidence. On real typography (`data/eval_real/real_cafe_receipt.png`), Donut achieves 98% confidence on vendor and total extraction.

---

## 4. How to Run Locally

### Option A: Static Web Showcase (No Python Needed)
You can view the showcase offline or on a local HTTP server:
```bash
# Serve statically with Python HTTP server
python3 -m http.server 8080

# Open in your browser:
# http://localhost:8080
```
Or simply open `index.html` directly in any modern browser (`file:///.../index.html`).

### Option B: Python Backend & Evaluation Suite
```bash
# 1. Clone repository
git clone https://github.com/anything14907-byte/Foss.git
cd Foss

# 2. Set up virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run Pytest unit tests (verifies table continuation, headers & bounding boxes)
pytest tests/

# 5. Run evaluation benchmark
python evaluate.py

# 6. Start FastAPI server
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```
Interactive API documentation will be available at `http://localhost:8000/docs`.

---

## 5. Chrome Browser Extension (Manifest V3)

The repository includes a Chrome Extension for capturing browser tabs and inspecting document bounding boxes.

### Architecture & Capabilities
- **Manifest V3 Compliant**: Uses background service worker and standard popup architecture.
- **Tab Capture**: Uses `chrome.tabs.captureVisibleTab` to snapshot invoices or receipts open in the browser.
- **Canvas 2D Overlay**: Draws interactive bounding boxes directly over captured document previews.
- **Backend Connection**: Sends captured documents to `http://localhost:8000/parse-document`.
- **Icons**: Includes custom crisp PNG icons in 16x16, 32x32, 48x48, and 128x128 px formats.

### Installation Instructions
1. Download or locate the extension archive:
   - Built ZIP archive: [`assets/stackdoc-extension.zip`](assets/stackdoc-extension.zip)
   - Or direct folder: [`extension/`](extension/)
2. Open Google Chrome and navigate to `chrome://extensions/`.
3. Toggle **Developer mode** on (top-right corner).
4. Click **Load unpacked**.
5. Select the `extension/` directory (or the extracted ZIP directory containing `manifest.json` at root).
6. Click the StackDoc icon in your browser toolbar to launch the popup.

---

## 6. Known Limitations

1. **In-Browser OCR Latency**: `Tesseract.js` executes inside WebAssembly on CPU. Initial initialization and worker recognition require 2 to 6 seconds depending on client CPU speed and image resolution.
2. **Scanned PDF Text Layers**: In the browser showcase, PDF documents without embedded vector text layers are converted to canvas images and processed through Tesseract OCR rather than direct vector extraction.
3. **Donut Domain Boundaries**: The Donut checkpoint (`naver-clova-ix/donut-base-finetuned-cord-v2`) is pre-trained on receipts and retail tickets. Multi-column scientific papers or dense government forms require routing to the vector layout engine.
4. **Nested Indentation Heuristics**: Sub-item modifier detection uses spatial indentation clustering (`Δx0 > 14px`). Documents with heavily staggered or right-aligned modifier text may require custom indentation thresholding.

---

## 7. Repository Structure

```
├── index.html                 # Single-file static showcase with in-browser layout pipeline
├── README.md                  # System documentation
├── evaluate.py                # Root evaluation entrypoint
├── requirements.txt           # Python dependencies
├── backend/
│   ├── app.py                 # FastAPI application & route definitions
│   ├── layout_extractor.py    # PyMuPDF coordinate layout engine (digital PDFs)
│   ├── model.py               # Donut vision-language transformer loader
│   ├── postprocessor.py       # Standardized schema normalization & math audits
│   └── utils.py               # PDF and image loading utilities
├── extension/
│   ├── manifest.json          # Chrome Extension Manifest V3 configuration
│   ├── popup.html             # Extension popup UI
│   ├── popup.css              # Editorial light/dark extension styling
│   ├── popup.js               # Tab capture, file upload, and canvas box renderer
│   ├── background.js          # Service worker
│   └── icons/                 # Pinned PNG icons (16px, 32px, 48px, 128px)
├── assets/
│   ├── stackdoc-extension.zip # Rebuilt extension distribution ZIP
│   ├── results.json           # Exported benchmark metrics fallback
│   └── samples/               # Preview thumbnails for preset documents
├── evaluation/
│   ├── evaluate.py            # Benchmark evaluation runner
│   ├── metrics.py             # Accuracy, precision, recall & line-item F1
│   ├── results.json           # Raw benchmark metrics
│   └── results.md             # Markdown scorecard
├── data/
│   ├── eval/                  # 6 synthetic benchmark documents & ground truth
│   └── eval_real/             # Real typography evaluation documents
└── tests/
    └── test_layout_extractor.py # Pytest test suite for table continuation & bboxes
```

---

## License

MIT License. Designed and maintained for layout-aware document understanding research and demonstrations.
