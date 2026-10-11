"""Cart summaries use each request's client snapshot, never search or generation."""
import asyncio
import json
import unittest
from unittest.mock import Mock, patch
from app.config import settings
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService, SESSIONS
from app.services.decision_provider import RuleDecisionProvider
from app.services.cart_queries import is_cart_total_query
import test_chat_followups as fixtures

QUERIES = ['What is my current total?', 'What is the total price of all items?',
           'How much is my cart?', 'What is my updated total?', 'How much do I owe?']


class CartTotalTests(unittest.TestCase):
    def setUp(self):
        SESSIONS.clear()
        self.provider = patch.object(settings, 'DECISION_PROVIDER', 'rules')
        self.generation = patch.object(settings, 'OLLAMA_ENABLED', False)
        self.provider.start()
        self.generation.start()
        self.addCleanup(self.provider.stop)
        self.addCleanup(self.generation.stop)

    def ask(self, query, cart, sid='total-session-00001'):
        db = Mock()
        service = ChatService(db)
        service.search_tool.search_products = Mock(side_effect=AssertionError('Unexpected product search'))
        service.search_tool.get_product_by_id = Mock(side_effect=AssertionError('Unexpected catalog lookup'))
        service._ollama_answer = Mock(side_effect=AssertionError('Unexpected generation path'))
        service.ollama.generate = Mock(side_effect=AssertionError('Unexpected LLM call'))
        timings = {}
        response = asyncio.run(service.generate_response(ChatRequest(message=query +
            '\n\n<shopai_client_context>' + json.dumps({'session_id': sid, 'cart': cart}) + '</shopai_client_context>'), timings)).response
        db.query.assert_not_called()
        service.search_tool.search_products.assert_not_called()
        service.search_tool.get_product_by_id.assert_not_called()
        service._ollama_answer.assert_not_called()
        service.ollama.generate.assert_not_called()
        self.assertEqual(timings['decision_provider'], 'rule-based')
        self.assertEqual(timings['resolved_action'], 'cart_action')
        self.assertEqual(timings['laya_call_count'], 0)
        self.assertNotIn('disabled', response)
        return response

    def test_all_total_phrases(self):
        cart = [{'id': 'a', 'name': 'A', 'price': 23456, 'quantity': 3},
                {'id': 'b', 'name': 'B', 'price': 13579, 'quantity': 1}]
        # Deliberately different from the user's observed total.
        for query in QUERIES:
            with self.subTest(query=query):
                self.assertEqual(RuleDecisionProvider().decide(query)['choice'], 'cart_action')
                self.assertEqual(self.ask(query, cart), 'Your current cart total is ₹83,947 for 4 items.')

    def test_empty_cart_total(self):
        for query in QUERIES:
            self.assertEqual(self.ask(query, []), 'Your current cart total is ₹0 for 0 items. Your cart is empty.')

    def test_latest_snapshot_after_add_quantity_and_remove(self):
        self.assertIn('₹0 for 0 items', self.ask(QUERIES[0], []))
        cart = [{'id': 'a', 'name': 'A', 'price': 12000, 'quantity': 1}]
        self.assertEqual(self.ask(QUERIES[0], cart), 'Your current cart total is ₹12,000 for 1 item.')
        cart[0]['quantity'] = 3
        self.assertEqual(self.ask(QUERIES[1], cart), 'Your current cart total is ₹36,000 for 3 items.')
        cart[0]['quantity'] = 2
        self.assertEqual(self.ask(QUERIES[3], cart), 'Your current cart total is ₹24,000 for 2 items.')
        self.assertIn('₹0 for 0 items', self.ask(QUERIES[4], []))

    def test_indian_grouping_and_no_invented_charges(self):
        self.assertEqual(self.ask(QUERIES[0], [{'id': 'x', 'price': 61728, 'quantity': 2}]),
                         'Your current cart total is ₹1,23,456 for 2 items.')
        self.assertEqual(self.ask(QUERIES[0], [{'id': 'x', 'price': 10.25, 'quantity': 3}]),
                         'Your current cart total is ₹30.75 for 3 items.')

    def test_session_isolation_and_missing_snapshot(self):
        self.ask(QUERIES[0], [{'id': 'x', 'price': 500, 'quantity': 2}])
        self.assertIn('₹0 for 0 items', self.ask(QUERIES[0], [], 'other-total-session01'))
        self.assertIn('₹0 for 0 items', self.ask(QUERIES[0], []))

    def test_product_price_questions_remain_product_questions(self):
        for query in ['What is its price?', 'What is the price of this laptop?', 'Show phones under 20000', 'Compare the first two products']:
            self.assertFalse(is_cart_total_query(query))

    def test_absent_client_snapshot_is_not_claimed_to_be_empty(self):
        service = ChatService(Mock())
        with patch.object(service.search_tool, 'search_products', side_effect=AssertionError('Search called')), patch.object(service, '_ollama_answer', side_effect=AssertionError('LLM path')):
            response = asyncio.run(service.generate_response(ChatRequest(message=QUERIES[0]))).response
        self.assertIn("couldn't read your current cart", response)
        self.assertNotIn('₹0', response)


class CartOperationTotalTests(unittest.TestCase):
    setUp = fixtures.FollowupTests.setUp
    tearDown = fixtures.FollowupTests.tearDown

    def ask(self, query, cart):
        with patch.object(settings, 'DECISION_PROVIDER', 'rules'), patch.object(settings, 'OLLAMA_ENABLED', False):
            service = ChatService(self.db)
            with patch.object(service.ollama, 'generate', side_effect=AssertionError('LLM called')):
                return asyncio.run(service.generate_response(ChatRequest(message=query +
                    '\n\n<shopai_client_context>' + json.dumps({'session_id': 'operation-totals-0001', 'cart': cart}) + '</shopai_client_context>'))).response

    def test_actual_supported_commands_then_summary(self):
        self.assertIn('SHOPAI_ADD_TO_CART:s1', self.ask('Add Samsung Phone A to my cart', []))
        cart = [{'id': 's1', 'name': 'Samsung Phone A', 'price': 20000, 'quantity': 1}]
        self.assertIn('₹20,000 for 1 item', self.ask(QUERIES[0], cart))
        for message, expected in [('Increase the quantity to two', 2), ('Decrease the quantity', 1), ('Remove that product from my cart', 0)]:
            answer = self.ask(message, cart)
            import re
            command = json.loads(re.search(r'\[\[SHOPAI_CART_ACTION:(\{.*?\})\]\]', answer).group(1))
            self.assertEqual(command['quantity'], expected)
            cart = [{**cart[0], 'quantity': expected}] if expected else []
            self.assertIn(f"₹{20000 * expected:,} for {expected} item", self.ask(QUERIES[1], cart))
