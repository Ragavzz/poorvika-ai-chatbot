import threading
import unittest
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.config import settings
from app.routes.suggestions import suggestions_router
from app.schemas.suggestions import SuggestionResponse
from app.services import suggestion_service as service
from app.schemas.suggestions import SuggestionRequest

QUESTIONS = SuggestionResponse(suggestions=['Is this product suitable for travel?', 'How does this compare for battery life?', 'What alternatives suit my daily needs?'])


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        service.CACHE.clear()
        service.IN_FLIGHT.clear()
        app = FastAPI()
        app.include_router(suggestions_router)
        self.client = TestClient(app)

    def test_success_cache_is_bound_to_context_and_model(self):
        with patch.object(service.OllamaService, 'generate_suggestions', return_value=QUESTIONS) as generate:
            first_timings = {}
            service.generate_suggestions({'name': 'iPhone 15', 'price': 69900}, first_timings)
            self.assertEqual(first_timings['cache'], 'miss')
            self.assertGreaterEqual(first_timings['cache_lookup_ms'], 0)
            timings = {}
            service.generate_suggestions({'name': 'iPhone 15', 'price': 69900}, timings)
            self.assertEqual(timings['cache'], 'hit')
            self.assertGreaterEqual(timings['cache_lookup_ms'], 0)
            service.generate_suggestions({'name': 'Samsung Watch', 'price': 20000}, {})
            with patch.object(settings, 'OLLAMA_MODEL', 'different-config'):
                service.generate_suggestions({'name': 'iPhone 15', 'price': 69900}, {})
            self.assertEqual(generate.call_count, 3)

    def test_product_and_category_contexts_are_passed_to_ollama_and_cached_separately(self):
        product = {'id': 'p1', 'name': 'iPhone 15', 'category': 'Mobiles', 'price': 69900, 'specifications': {'Chip': 'A16'}}
        listing = {'name': 'Mobiles', 'category': 'Mobiles', 'products': [{'id': 'p1', 'name': 'iPhone 15', 'price': 69900}]}
        with patch.object(service.OllamaService, 'generate_suggestions', return_value=QUESTIONS) as generate:
            service.generate_suggestions(product, {})
            service.generate_suggestions(listing, {})
            self.assertEqual(generate.call_count, 2)
            self.assertEqual(generate.call_args_list[0].args[0], product)
            self.assertEqual(generate.call_args_list[1].args[0], listing)

    def test_model_prompt_distinguishes_listing_and_product_context_without_static_fallback(self):
        from app.services.ollama_service import OllamaService
        with patch('app.services.ollama_service.HTTP.post') as post:
            response = post.return_value
            response.raise_for_status.return_value = None
            listing_questions = SuggestionResponse(suggestions=['What should shoppers consider when choosing a mobile?', 'How do the listed mobile options compare for everyday use?', 'Which features matter most when selecting among these mobiles?', 'Which option suits different daily needs?'])
            response.json.return_value = {'message': {'content': json.dumps(listing_questions.suggestions)}, 'load_duration': 0, 'eval_duration': 5, 'prompt_eval_duration': 2, 'total_duration': 7}
            service_instance = OllamaService()
            service_instance.generate_suggestions({'name': 'Mobiles', 'category': 'Mobiles', 'products': [{'name': 'iPhone 15'}]})
            listing_prompt = post.call_args.kwargs['json']['messages'][0]['content']
            self.assertIn('Never write', listing_prompt)
            self.assertNotIn('fallback question', listing_prompt.lower())

    def test_listing_output_referencing_single_product_is_rejected(self):
        from app.services.ollama_service import OllamaService
        bad = SuggestionResponse(suggestions=['Is this product useful for travel?', 'How does this phone compare with others?', 'What makes this item appealing?', 'Which option fits daily use?'])
        with patch('app.services.ollama_service.HTTP.post') as post:
            post.return_value.raise_for_status.return_value = None
            post.return_value.json.return_value = {'message': {'content': json.dumps(bad.suggestions)}}
            with self.assertRaisesRegex(ValueError, 'one selected product'):
                OllamaService().generate_suggestions({'name': 'Mobiles', 'category': 'Mobiles', 'products': [{'name': 'iPhone'}]})
            self.assertEqual(post.call_count, 2)

    def test_listing_output_asserting_unprovided_feature_as_fact_is_rejected(self):
        from app.services.ollama_service import OllamaService
        bad = SuggestionResponse(suggestions=['Could Mobiles rank highly due to its wireless charging?', 'How do these options compare for daily use?', 'Which mobile options fit a shopper budget?', 'What should buyers consider when choosing?'])
        with patch('app.services.ollama_service.HTTP.post') as post:
            post.return_value.raise_for_status.return_value = None
            post.return_value.json.return_value = {'message': {'content': json.dumps(bad.suggestions)}}
            with self.assertRaisesRegex(ValueError, 'unsupported feature'):
                OllamaService().generate_suggestions({'name': 'Mobiles', 'category': 'Mobiles', 'products': [{'name': 'iPhone 15'}]})

    def test_concurrent_identical_context_runs_one_generation(self):
        entered, release = threading.Event(), threading.Event()
        def slow(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(3))
            return QUESTIONS
        with patch.object(service.OllamaService, 'generate_suggestions', side_effect=slow) as generate, ThreadPoolExecutor(2) as pool:
            first = pool.submit(service.generate_suggestions, {'name': 'iPhone 15'}, {})
            self.assertTrue(entered.wait(3))
            second = pool.submit(service.generate_suggestions, {'name': 'iPhone 15'}, {})
            release.set()
            self.assertEqual(first.result().suggestions, second.result().suggestions)
            self.assertEqual(generate.call_count, 1)

    def test_expired_cache_generates_again(self):
        with patch.object(service.OllamaService, 'generate_suggestions', return_value=QUESTIONS) as generate:
            service.generate_suggestions({'name': 'iPhone 15'}, {})
            for key, (_, result) in list(service.CACHE.items()):
                service.CACHE[key] = (0, result)
            service.generate_suggestions({'name': 'iPhone 15'}, {})
            self.assertEqual(generate.call_count, 2)

    def test_timeout_and_connection_failure_have_correlated_reasons(self):
        for error, status, reason in [(requests.Timeout(), 504, 'timeout'), (requests.ConnectionError(), 503, 'model_connection_or_service_failure')]:
            with patch.object(settings, 'OLLAMA_ENABLED', True), patch.object(service.OllamaService, 'generate_suggestions', side_effect=error):
                result = self.client.post('/api/chat/suggestions', json={'product': {'name': 'iPhone 15'}}, headers={'X-ShopAI-Request-ID': 'lifecycle-test'})
            self.assertEqual(result.status_code, status)
            self.assertIn(reason, result.json()['detail'])
            self.assertEqual(result.headers['X-ShopAI-Request-ID'], 'lifecycle-test')
            self.assertFalse(service.CACHE)
            self.assertFalse(service.IN_FLIGHT)

    def test_real_mobiles_listing_context_reports_ollama_oom_without_fallback(self):
        snapshot_path = Path(__file__).resolve().parents[1] / 'documentation' / 'e2e-catalog-snapshot.json'
        catalog = json.loads(snapshot_path.read_text(encoding='utf-8'))
        rows = [row for row in catalog if row.get('category') == 'Mobiles' and float(row.get('price') or 0) <= 150000]
        rows.sort(key=lambda row: (not bool(row.get('in_stock')), row.get('rating') is None,
                                   -(row.get('rating') or 0), float(row.get('price') or 0), str(row.get('id', ''))))
        products = []
        for row in rows[:8]:
            item = {key: row.get(source) for key, source in (
                ('id', 'id'), ('name', 'name'), ('brand', 'brand'), ('category', 'category'), ('price', 'price'))}
            specs = row.get('flattened_specs') or row.get('specifications') or {}
            if specs:
                item['specifications'] = dict(list(specs.items())[:2])
            products.append(item)
        listing = {'name': 'Mobiles', 'category': 'Mobiles',
                   'filters': {'maxPrice': 150000, 'inStockOnly': False, 'minRating': 0,
                               'minDiscount': 0, 'brands': [], 'page': 1},
                   'products': products}
        SuggestionRequest.model_validate({'product': listing})
        service.CACHE.clear()
        service.IN_FLIGHT.clear()
        response = requests.Response()
        response.status_code = 500
        response.reason = 'Internal Server Error'
        response.url = 'http://localhost:11434/api/chat'
        response._content = b'{"error":"llama-server reported out-of-memory during startup: cudaMalloc failed: out of memory"}'

        with patch.object(settings, 'OLLAMA_ENABLED', True), \
             patch('app.services.ollama_service.HTTP.post', return_value=response), \
             self.assertLogs('shopai.services.ollama', level='ERROR') as diagnostics:
            result = self.client.post('/api/chat/suggestions', json={'product': listing},
                                      headers={'X-ShopAI-Request-ID': 'mobiles-listing-oom'})

        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.json(), {'detail': 'Suggestions are unavailable (model_connection_or_service_failure).'})
        self.assertEqual(result.headers['X-ShopAI-Request-ID'], 'mobiles-listing-oom')
        timing = json.loads(result.headers['X-ShopAI-Suggestion-Timing'])
        self.assertEqual(timing['failure_reason'], 'model_connection_or_service_failure')
        self.assertEqual(timing['ollama_http_status'], 500)
        self.assertEqual(timing['ollama_failure_type'], 'HTTPError')
        self.assertEqual(timing['ollama_call_count'], 1)
        self.assertGreaterEqual(timing['ollama_ms'], 0)
        self.assertNotIn('validation_ms', timing)
        self.assertIn('cudaMalloc failed', '\n'.join(diagnostics.output))
        self.assertNotIn('cudaMalloc', result.text)

    def test_capabilities_does_not_query_database_or_laya(self):
        result = self.client.get('/api/chat/suggestion-capabilities')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['model_configuration'], service.configuration_key())

    def test_disabled_service_does_not_serve_cached_suggestions(self):
        with patch.object(service.OllamaService, 'generate_suggestions', return_value=QUESTIONS):
            service.generate_suggestions({'name': 'iPhone 15'}, {})
        with patch.object(settings, 'OLLAMA_ENABLED', False), patch.object(service.OllamaService, 'generate_suggestions') as generate:
            result = self.client.post('/api/chat/suggestions', json={'product': {'name': 'iPhone 15'}})
        self.assertEqual(result.status_code, 503)
        self.assertNotIn('suggestions', result.json())
        generate.assert_not_called()
