"""Exercise current source against configured live models and real catalog."""
import asyncio
import json
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database.session import SessionLocal
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.ollama_service import OllamaService

results = {'verification': 'Current Python source, live PostgreSQL and configured model services; no browser'}
with SessionLocal() as db:
    for message in ['hi', 'Show me Sony earphones under ₹1000']:
        service = ChatService(db)
        timings = {}
        try:
            answer = asyncio.run(service.generate_response(ChatRequest(message=message), timings))
            results[message] = {'passed': True, 'response': answer.response, 'timings': timings}
            if message == 'hi':
                assert timings['resolved_action'] == 'general_query'
                assert 'no matching catalog' not in answer.response.lower()
            else:
                assert timings['resolved_action'] == 'product_search'
        except Exception as exc:
            results[message] = {'passed': False, 'reason': str(exc), 'timings': timings}
        print(message, results[message]['passed'], flush=True)
    product = service.search_tool.get_product_by_id('apple-iphone-13-blue-128gb')
    if product:
        supplied = {key: product[key] for key in ['name', 'brand', 'category', 'price']}
        results['suggestion_context'] = supplied
        try:
            output = OllamaService().generate_suggestions(supplied).model_dump()
            results['actual_product_suggestions'] = {'passed': True, 'output': output}
        except Exception as exc:
            results['actual_product_suggestions'] = {'passed': False, 'reason': str(exc)}
Path('../documentation/welcome-pipeline-live-results.json').write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
