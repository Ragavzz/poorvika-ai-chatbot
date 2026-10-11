"""Regressions for defects reproduced through live API during the E2E audit."""
import asyncio
import json
import unittest
from unittest.mock import Mock, patch
import test_chat_followups as fixtures
from app.config import settings
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService, SESSIONS
from app.services.ollama_service import OllamaService
from app.services.ollama_service import validate_suggestion_claims


class E2EFindingsTests(unittest.TestCase):
    setUp = fixtures.FollowupTests.setUp
    tearDown = fixtures.FollowupTests.tearDown

    def ask(self, text, choice='general_query', extra=None):
        service = ChatService(self.db)
        service.laya.decide = Mock(return_value={'choice': choice, 'confidence': .9})
        service.ollama.generate = Mock(return_value='Controlled generated answer')
        context = {'session_id': 'e2e-regression-session', **(extra or {})}
        self.last_timings = {}
        result = asyncio.run(service.generate_response(ChatRequest(message=text +
            '\n\n<shopai_client_context>' + json.dumps(context) + '</shopai_client_context>'), self.last_timings))
        service.laya.decide.assert_called_once_with(text)
        self.last_ollama_calls = service.ollama.generate.call_count
        return result.response

    def test_ambiguous_two_product_comparison_does_not_compare_all_results(self):
        self.ask('Show Samsung phones', 'product_search')
        response = self.ask('Compare these two phones', 'recommendation')
        self.assertIn('Which two', response)
        self.assertNotIn('| Price |', response)
        explicit = self.ask('Compare the first two phones')
        self.assertIn('Samsung Phone A', explicit)
        self.assertIn('Samsung Phone B', explicit)
        self.assertNotIn('Samsung Phone C', explicit)

    def test_cheaper_alternative_uses_selected_product_and_strict_budget(self):
        self.ask('Show Samsung phones', 'product_search')
        self.ask('Tell me about the second product', 'product_details')
        response = self.ask('Is there a cheaper alternative?', 'general_query')
        self.assertEqual(self.last_timings['resolved_action'], 'product_search')
        self.assertIn('SHOPAI_PRODUCTS:s1', response)
        self.assertNotIn('SHOPAI_PRODUCTS:s2', response)
        self.assertNotIn('Samsung Phone C', response)

    def test_no_cheaper_alternative_preserves_selection_for_price_followup(self):
        self.ask('Show Samsung phones', 'product_search')
        self.ask('Tell me about the first product', 'product_details')
        response = self.ask('Is there a cheaper alternative?')
        self.assertNotIn('SHOPAI_PRODUCTS', response)
        self.assertIn("couldn't find", response)
        self.assertIn('20,000', self.ask('What is its price?', 'product_details'))

    def test_cheaper_alternative_without_selection_requests_clarification(self):
        response = self.ask('Is there a cheaper alternative?')
        self.assertIn('Which product', response)
        self.assertNotIn('SHOPAI_PRODUCTS', response)

    def test_popup_selection_survives_generated_answer_and_manual_price(self):
        self.ask('Is this phone suitable for gaming?', 'recommendation', {
            'suggestion_product_id': 's1', 'recent_product_ids': ['s1'],
        })
        self.assertEqual(SESSIONS['e2e-regression-session']['context'].get('selected_product_id'), 's1')
        response = self.ask('What is its price?', 'product_details')
        self.assertIn('Samsung Phone A', response)
        self.assertIn('20,000', response)

    def test_processor_question_keeps_chipset_and_cpu_evidence(self):
        response = Mock()
        response.json.return_value = {'message': {'content': 'Controlled answer'}}
        with patch('app.services.ollama_service.HTTP.post', return_value=response) as post:
            OllamaService().generate('Is its display and processor suitable for gaming?', {
                'suggestion_information': True,
                'products': [{'name': 'Phone', 'price': 100, 'flattened_specs': {
                    'Display Type': 'OLED', 'Chipset': 'A16 Bionic chip', 'CPU': '6-core CPU', 'GPU': '5-core GPU',
                }}],
            })
        prompt = post.call_args.kwargs['json']['messages'][1]['content']
        self.assertIn('Chipset: A16 Bionic chip', prompt)
        self.assertIn('CPU: 6-core CPU', prompt)
        self.assertIn('GPU: 5-core GPU', prompt)

    def test_cart_total_after_popup_selection_does_not_become_product_question(self):
        self.ask('Is this phone suitable for gaming?', 'recommendation', {
            'suggestion_product_id': 's1', 'recent_product_ids': ['s1'],
        })
        response = self.ask('What is my current total?', 'general_query', {
            'cart': [{'id': 's1', 'name': 'Samsung Phone A', 'price': 20000, 'quantity': 2}],
        })
        self.assertIn('40,000', response)
        self.assertIn('2 items', response)
        self.assertEqual(self.last_timings['resolved_action'], 'cart_action')
        self.assertEqual(self.last_ollama_calls, 0)

    def test_suggestion_does_not_assert_unlisted_office_suite(self):
        question = 'Can this phone be used for work due to its Android operating system and office suite?'
        with self.assertRaises(ValueError):
            validate_suggestion_claims([question], {'name': 'Phone', 'specifications': {'Operating System': 'Android'}})
        validate_suggestion_claims([question], {'name': 'Phone', 'specifications': {
            'Operating System': 'Android', 'Office Suite': 'Supplied office suite',
        }})

    def test_neutral_question_about_unlisted_feature_does_not_assert_it_exists(self):
        validate_suggestion_claims(['Does this phone support an office suite?'], {'name': 'Phone'})
