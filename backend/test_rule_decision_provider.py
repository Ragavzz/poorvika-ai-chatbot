"""Isolated regression tests; live PostgreSQL verification is recorded separately."""
import asyncio
import json
import unittest
from unittest.mock import patch

from app.config import settings
from fastapi import HTTPException
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.decision_provider import RuleDecisionProvider, create_decision_provider
from test_chat_followups import FollowupTests


class ProviderSelectionTests(unittest.TestCase):
    def test_explicit_rules_never_constructs_laya(self):
        with patch.object(settings, 'DECISION_PROVIDER', 'rules'), patch(
                'app.services.laya_client.LayaClient', side_effect=AssertionError('Laya constructed')):
            self.assertIsInstance(create_decision_provider(), RuleDecisionProvider)

    def test_default_model_provider_is_retained(self):
        from app.services.laya_client import LayaClient
        with patch.object(settings, 'DECISION_PROVIDER', 'laya'):
            self.assertIsInstance(create_decision_provider(), LayaClient)

    def test_six_intents(self):
        provider = RuleDecisionProvider()
        for message, intent in [('show phones', 'product_search'),
                                ('tell me about it', 'product_details'),
                                ('recommend a phone', 'recommendation'),
                                ('add it to my cart', 'add_to_cart'),
                                ('remove it from my cart', 'cart_action'),
                                ('hello', 'general_query')]:
            self.assertEqual(provider.decide(message)['choice'], intent)


class RuleFollowupTests(FollowupTests):
    # Reuse every existing context/stock/ambiguity scenario with the real resolver.
    def ask(self, text, choice='general_query', sid='session-0000000001'):
        with patch.object(settings, 'DECISION_PROVIDER', 'rules'), patch.object(settings, 'OLLAMA_ENABLED', False):
            service = ChatService(self.db)
            timings = {}
            response = asyncio.run(service.generate_response(ChatRequest(message=text +
                '\n\n<shopai_client_context>' + json.dumps({'session_id': sid}) + '</shopai_client_context>'), timings)).response
            self.assertEqual(timings['decision_provider'], 'rule-based')
            self.assertEqual(timings['laya_call_count'], 0)
            self.assertNotIn('laya_start', timings)
            self.assertEqual(timings.get('ollama_call_count', 0), 0)
            return response

    def test_disabled_generation(self):
        with patch.object(settings, 'OLLAMA_ENABLED', False):
            service = ChatService(self.db)
            with patch.object(service.ollama, 'generate', side_effect=AssertionError('Ollama called')):
                with self.assertRaises(HTTPException) as failure:
                    service._ollama_answer('help', {}, {})
                self.assertEqual(failure.exception.status_code, 503)

    def test_unsupported_cart_action_does_not_mutate(self):
        response = self.ask('checkout my cart')
        self.assertNotIn('SHOPAI_ADD_TO_CART', response)
        self.assertNotIn('SHOPAI_CART_ACTION', response)
