"""Live HTTP + PostgreSQL checks, without mocks or database writes."""
import ctypes
import json
from pathlib import Path
import re
import struct
import uuid

import requests
from sqlalchemy.orm import Session
from app.database.session import engine
from app.models.product import Product

API = 'http://127.0.0.1:8000'
health = requests.get(API + '/api/health', timeout=10).json()
assert health['database']['type'] == 'PostgreSQL' and health['database']['connected']
assert health['decision_provider'] == 'rules' and not health['ollama_enabled']
page = requests.get('http://127.0.0.1:8080', timeout=30)
assert page.status_code == 200 and '<html' in page.text.lower()
results = []
sid = 'lowram-' + uuid.uuid4().hex


def ask(message, context=None):
    context = {'session_id': sid, **(context or {})}
    response = requests.post(API + '/api/chat', json={'message': message +
        '\n\n<shopai_client_context>' + json.dumps(context) + '</shopai_client_context>'}, timeout=20)
    response.raise_for_status()
    answer = response.json()['response']
    match = re.search(r'\[\[SHOPAI_PRODUCTS:([^\]]+)\]\]', answer)
    ids = match.group(1).split(',') if match else []
    results.append({'message': message, 'response': answer, 'product_ids': ids})
    return answer, ids


with Session(engine) as db:
    answer, ids = ask('Show me phones under 25000')
    assert ids
    assert all(db.get(Product, pid).price <= 25000 for pid in ids)
    answer, ids = ask('Only show Samsung phones')
    assert ids
    assert all(db.get(Product, pid).brand.lower() == 'samsung' and db.get(Product, pid).price <= 25000 for pid in ids)
    answer, selected = ask('Tell me about the first product')
    assert len(selected) == 1 and db.get(Product, selected[0]).name in answer
    answer, alternatives = ask('Show me similar phones')
    assert alternatives and selected[0] not in alternatives
    assert all(db.get(Product, pid).in_stock and db.get(Product, pid).brand.lower() == 'samsung'
               and db.get(Product, pid).price <= 25000 for pid in alternatives)
    dead = db.query(Product).filter(Product.in_stock == False).first()
    assert dead is not None
    answer, _ = ask('Add it to my cart', {'session_id': 'stock-' + uuid.uuid4().hex,
                        'suggestion_product_id': dead.id, 'recent_product_ids': [dead.id]})
    assert 'out of stock' in answer.lower() and 'SHOPAI_ADD_TO_CART' not in answer
    answer, ids = ask('Recommend phones under 25000', {'session_id': 'recommend-' + uuid.uuid4().hex})
    assert ids and all(db.get(Product, pid).in_stock and db.get(Product, pid).price <= 25000 for pid in ids)
    answer, _ = ask('Show my cart')
    assert 'SHOPAI_ADD_TO_CART' not in answer
    answer, _ = ask('hello')
    assert 'looking for' in answer
    answer, _ = ask('checkout my cart')
    assert 'SHOPAI_ADD_TO_CART' not in answer and 'SHOPAI_CART_ACTION' not in answer

buffer = ctypes.create_string_buffer(64)
ctypes.c_ulong.from_buffer(buffer).value = 64
assert ctypes.windll.kernel32.GlobalMemoryStatusEx(buffer)
memory = struct.unpack('II7Q', buffer.raw)
report = {'health': health, 'frontend_http_status': page.status_code,
          'rendered_browser_check': 'Unavailable: no connected browser surfaces',
          'memory': {'total_GiB': round(memory[2] / 2**30, 3), 'available_GiB': round(memory[3] / 2**30, 3), 'used_percent': memory[1]},
          'checks': results, 'result': 'PASS', 'database_writes': 0}
root = Path(__file__).resolve().parents[2]
log = max(root.glob('lowram-backend-*.stderr.log'), key=lambda path: path.stat().st_mtime)
timings = [json.loads(line.split('[TIMING] ', 1)[1]) for line in log.read_text(encoding='utf-8').splitlines() if '[TIMING] ' in line][-len(results):]
assert len(timings) == len(results)
for result, timing in zip(results, timings):
    assert timing['decision_provider'] == 'rule-based'
    assert timing['laya_call_count'] == timing['ollama_call_count'] == 0
    result['decision_provider'] = timing['decision_provider']
    result['timings'] = timing
report['backend_log'] = str(log)
output = Path(__file__).resolve().parents[2] / 'documentation' / 'lowram-demo-live-results.json'
output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'result': 'PASS', 'checks': len(results), 'health': health, 'memory': report['memory'], 'report': str(output)}, indent=2))
