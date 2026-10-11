"""HTTP measurements only; does not claim browser paint or a cold model unload."""
import json
import sys
import time
from pathlib import Path
import requests

sys.stdout.reconfigure(encoding='utf-8')
http = requests.Session()
results = {'kind': 'HTTP only; browser unavailable; first request is not proven cold', 'runs': []}
for product_id in ['apple-iphone-15-black-256gb', 'samsung-galaxy-watch5-pro-lte-45-mm-gray-titanium-sm-r925fztainu']:
    start = time.perf_counter()
    response = http.get('http://localhost:8000/api/products/' + product_id, timeout=10)
    if response.status_code != 200:
        # Record this exact failing ID rather than silently substituting a product.
        results['runs'].append({'product_id': product_id, 'product_status': response.status_code})
        continue
    product = response.json()
    payload = {key: product[key] for key in ['id', 'name', 'brand', 'category', 'price', 'description', 'specifications'] if product.get(key) is not None}
    if 'description' in payload:
        payload['description'] = payload['description'][:4000]
    context_ms = (time.perf_counter() - start) * 1000
    for run in range(3):
        started = time.perf_counter()
        try:
            answer = http.post('http://localhost:8000/api/chat/suggestions', json={'product': payload}, timeout=130,
                               headers={'X-ShopAI-Request-ID': f'popup-{sys.argv[1]}-{product_id}-{run}'})
            record = {'product_id': product_id, 'run': run, 'context_fetch_ms': context_ms,
                      'elapsed_ms': (time.perf_counter() - started) * 1000,
                      'status': answer.status_code, 'output': answer.json(),
                      'timing': answer.headers.get('X-ShopAI-Suggestion-Timing'), 'context': payload}
        except Exception as exc:
            record = {'product_id': product_id, 'run': run, 'elapsed_ms': (time.perf_counter() - started) * 1000, 'error': str(exc)}
        results['runs'].append(record)
        print(product_id, run, record.get('status'), round(record['elapsed_ms']), flush=True)
        Path('../documentation/popup-latency-' + sys.argv[1] + '.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
Path('../documentation/popup-latency-' + sys.argv[1] + '.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
