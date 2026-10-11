"""Explicit independent live inference checks; no service configuration changes."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from app.config import settings
from app.services.laya_client import LayaClient
from app.services.ollama_service import OllamaService

results = {
    'configured_decision_provider': settings.DECISION_PROVIDER,
    'configured_ollama_enabled': settings.OLLAMA_ENABLED,
    'laya_url': settings.LAYA_DECIDE_URL,
    'ollama_url': settings.OLLAMA_API_URL,
    'ollama_model': settings.OLLAMA_MODEL,
    'browser_verification': 'Not executed',
}
try:
    results['running_backend_health'] = requests.get('http://127.0.0.1:8000/api/health', timeout=5).json()
except Exception as exc:
    results['running_backend_health'] = {'error': str(exc)}
for name, call in [
    ('laya_inference', lambda: LayaClient().decide('Show me Sony earphones under ₹1000')),
    ('ollama_greeting_inference', lambda: OllamaService().generate('hi', {'greeting': True})),
    ('ollama_suggestions_inference', lambda: OllamaService().generate_suggestions({
        'name': 'Phone shopping search', 'category': 'Mobiles',
    }).model_dump()),
]:
    try:
        results[name] = {'passed': True, 'output': call()}
    except Exception as exc:
        results[name] = {'passed': False, 'error_type': type(exc).__name__, 'reason': str(exc)}
    print(name, results[name]['passed'], flush=True)
target = Path(__file__).resolve().parents[2] / 'documentation/welcome-model-live-results.json'
target.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
