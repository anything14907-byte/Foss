# StackDoc Evaluation Benchmark Report

- **Generated:** `2026-10-22T02:53:54Z`
- **Primary Test Set:** `data/eval`
- **Total Documents:** `6`
- **Pass Rate:** `2/6`
- **Vendor Accuracy:** `33.3%`
- **Date Accuracy:** `33.3%`
- **Total Accuracy:** `33.3%`
- **Mean Line-Item F1:** `0.3333`
- **Mean Latency:** `3.2171s`

## Detailed Results

| Document | Engine | Vendor Correct | Date Correct | Total Correct | Line Items F1 | Confidence | Latency (s) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `invoice_consulting_services.pdf` | `layout` | YES | YES | YES | 1.00 | 100% | 0.0230 | `PASS` |
| `invoice_enterprise_stack.pdf` | `layout` | YES | YES | YES | 1.00 | 100% | 0.0038 | `PASS` |
| `receipt_crumpled_cafe.png` | `donut` | NO | NO | NO | 0.00 | 82% | 10.5086 | `FAIL` |
| `receipt_faded_ink.png` | `donut` | NO | NO | NO | 0.00 | 83% | 2.8111 | `FAIL` |
| `receipt_grocery_market.png` | `donut` | NO | NO | NO | 0.00 | 82% | 3.1875 | `FAIL` |
| `receipt_tech_supplies.png` | `donut` | NO | NO | NO | 0.00 | 82% | 2.7687 | `FAIL` |

## Real Documents Evaluation (`data/eval_real/`)

- **Documents Evaluated:** `2`
- **Pass Rate:** `1/2`
- **Mean Latency:** `2.2283s`

| Document | Engine | Vendor Correct | Date Correct | Total Correct | Line Items F1 | Confidence | Latency (s) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `real_cafe_receipt.png` | `donut` | YES | NO | YES | 0.00 | 98% | 4.4395 | `PARTIAL` |
| `real_cloud_invoice.pdf` | `layout` | YES | YES | YES | 1.00 | 100% | 0.0171 | `PASS` |
