"""Measure fresh generation over HTTP; no browser-visible timings are inferred."""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
output = Path(__file__).resolve().parents[1] / "suggestion-performance-results.json"
rows = []
for query in ("Tecno Spark Go 1", "Samsung Galaxy A16 5G", "Apple iPhone 15"):
    products = requests.get(base + "/api/products/search", params={"q": query, "limit": 100}, timeout=10).json()
    product = next(p for p in products if query.lower() in p["name"].lower() and p.get("category") == "Mobiles")
    detail = requests.get(base + "/api/products/" + product["id"], timeout=10).json()
    context = {key: detail[key] for key in ("name", "brand", "category", "price", "specifications", "description") if key in detail}
    for run in range(1, 4):
        started_at = datetime.now(timezone.utc).isoformat()
        started = time.perf_counter()
        response = requests.post(base + "/api/chat/suggestions", json={"product": context}, timeout=130)
        received_at = datetime.now(timezone.utc).isoformat()
        elapsed = (time.perf_counter() - started) * 1000
        timings = json.loads(response.headers["X-ShopAI-Suggestion-Timing"])
        row = {"product": detail["name"], "product_id": detail["id"], "run": run, "status": response.status_code, "client_started": started_at, "client_received": received_at, "http_round_trip_ms": round(elapsed, 3), **timings, "suggestions": response.json().get("suggestions", []), "error": response.json().get("detail")}
        rows.append(row)
        output.write_text(json.dumps({"method": "Fresh uncached generation, sequential real HTTP requests. Browser timings are not measured.", "runs": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(row, ensure_ascii=False), flush=True)
