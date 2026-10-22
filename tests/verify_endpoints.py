import glob
import requests
import json

URL = "http://127.0.0.1:8000/parse-document"
files = sorted(glob.glob("data/eval/*.*"))
files = [f for f in files if not f.endswith(".json")]

print(f"Testing POST /parse-document on {len(files)} files...")

for filepath in files:
    filename = filepath.split("/")[-1]
    is_pdf = filename.endswith(".pdf")
    
    # 1. Test mode=auto
    with open(filepath, "rb") as fp:
        resp = requests.post(f"{URL}?mode=auto", files={"file": (filename, fp)})
    assert resp.status_code == 200, f"auto failed on {filename}: {resp.status_code} {resp.text}"
    data_auto = resp.json()
    assert "vendor_name" in data_auto and "total_amount" in data_auto and "latency_seconds" in data_auto
    print(f"  [AUTO]   {filename:<32} -> Engine: {data_auto.get('engine'):<6} | Vendor: {data_auto.get('vendor_name', '')[:20]:<20} | Total: {data_auto.get('total_amount', ''):<10} | Latency: {data_auto.get('latency_seconds')}s")

    # 2. Test mode=donut
    with open(filepath, "rb") as fp:
        resp = requests.post(f"{URL}?mode=donut", files={"file": (filename, fp)})
    assert resp.status_code == 200, f"donut failed on {filename}: {resp.status_code} {resp.text}"
    data_donut = resp.json()
    assert data_donut.get("engine") == "donut"
    print(f"  [DONUT]  {filename:<32} -> Engine: donut  | Confidence: {data_donut.get('confidence')} | Latency: {data_donut.get('latency_seconds')}s")

    # 3. Test mode=layout (for PDFs)
    if is_pdf:
        with open(filepath, "rb") as fp:
            resp = requests.post(f"{URL}?mode=layout", files={"file": (filename, fp)})
        assert resp.status_code == 200, f"layout failed on {filename}: {resp.status_code} {resp.text}"
        data_layout = resp.json()
        assert data_layout.get("engine") == "layout"
        assert "boxes" in data_layout
        box_keys = list(data_layout.get("boxes", {}).keys())
        print(f"  [LAYOUT] {filename:<32} -> Engine: layout | Boxes: {box_keys} | Latency: {data_layout.get('latency_seconds')}s")

print("\nALL POST /parse-document ENDPOINT TESTS PASSED WITH VALID JSON!")
