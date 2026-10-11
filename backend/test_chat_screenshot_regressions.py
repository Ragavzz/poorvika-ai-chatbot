"""Screenshot scenarios with the real rule resolver and an isolated SQL catalog."""
import asyncio
import json
import re
from fastapi import HTTPException
from unittest.mock import patch
import test_chat_followups as fixtures
from app.config import settings
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService


class ScreenshotTests(fixtures.FollowupTests):
    def ask(self, text, choice='general_query', sid='session-0000000001', cart=None):
        with patch.object(settings, 'DECISION_PROVIDER', 'rules'), patch.object(settings, 'OLLAMA_ENABLED', False):
            service = ChatService(self.db)
            self.timings = {}
            with patch.object(service.search_tool, 'search_products', wraps=service.search_tool.search_products) as search:
                result = asyncio.run(service.generate_response(ChatRequest(message=text +
                    '\n\n<shopai_client_context>' + json.dumps({'session_id': sid, 'cart': cart or []}) + '</shopai_client_context>'), self.timings)).response
                self.search_calls = search.call_count
            self.assertEqual(self.timings['decision_provider'], 'rule-based')
            self.assertEqual(self.timings['laya_call_count'], 0)
            return result

    def command(self, answer):
        return json.loads(re.search(r'\[\[SHOPAI_CART_ACTION:(\{.*?\})\]\]', answer).group(1))

    def test_hp_filter_compare(self):
        self.ask('Show laptops under 70000')
        self.ask('Only HP laptops')
        answer = self.ask('Compare the first two products')
        self.assertIn('HP Laptop', answer)
        self.assertIn('HP Premium Laptop', answer)
        self.assertNotIn('Dell Laptop', answer)
        self.assertIn('Connector', answer)
        self.assertEqual(self.search_calls, 0)
        self.assertEqual(self.state()['search_filters']['max_price'], 70000)

    def test_best_specs_uses_previous_results(self):
        self.ask('Show products')
        answer = self.ask('Which one has the best specifications?')
        self.assertIn('| Field |', answer)
        self.assertIn('Which specification', answer)
        self.assertEqual(self.search_calls, 0)
        self.assertNotIn('couldn\'t find', answer)

    def test_compare_first_two_and_retains_result_set(self):
        self.ask('Show Samsung phones under 25000')
        answer = self.ask('Compare the first two products')
        self.assertIn('Samsung Phone A', answer)
        self.assertIn('Samsung Phone B', answer)
        self.assertNotIn('Samsung Phone C', answer)
        self.assertEqual(self.search_calls, 0)
        self.ask('Tell me about the first product')
        self.assertIn('Samsung Phone B', self.ask('Compare the first two products'))

    def test_reference_cheaper_more_and_price(self):
        self.ask('Show Samsung phones')
        self.assertEqual(self.ids(self.ask('Which one is cheaper?')), ['s1'])
        self.assertIn('Samsung Phone A', self.ask('Tell me more about that product.'))
        self.assertIn('20,000', self.ask('What is its price?'))

    def test_reference_ambiguity_is_focused(self):
        self.ask('Show Samsung phones')
        answer = self.ask('What is its price?')
        self.assertIn('Samsung Phone A', answer)
        self.assertIn('Samsung Phone B', answer)
        self.assertIn('choose', answer)

    def test_tied_cheaper_lists_only_cheapest_choices(self):
        from app.models.product import Product
        self.db.query(Product).filter_by(id='s2').update({'price': 20000})
        self.db.commit()
        self.ask('Show Samsung phones')
        answer = self.ask('Which one is cheaper?')
        self.assertIn('Samsung Phone A', answer)
        self.assertIn('Samsung Phone B', answer)
        self.assertNotIn('Samsung Phone C', answer)
        self.assertIn('choose', answer)

    def test_add_increase_show_remove(self):
        self.ask('Show Samsung phones')
        answer = self.ask('Add the first product to my cart')
        self.assertIn('SHOPAI_ADD_TO_CART:s1', answer)
        cart = [{'id': 's1', 'name': 'Samsung Phone A', 'price': 20000, 'quantity': 1}]
        command = self.command(self.ask('Increase the quantity to two', cart=cart))
        self.assertEqual(command, {'action': 'set_quantity', 'product_id': 's1', 'expected_quantity': 1, 'quantity': 2})
        self.assertEqual(self.search_calls, 0)
        cart[0]['quantity'] = command['quantity'] # Client applies the supported command.
        answer = self.ask('Show me my cart.', cart=cart)
        self.assertIn('Qty: 2', answer)
        self.assertIn('40,000', answer)
        self.assertEqual(self.search_calls, 0)
        self.assertEqual(self.command(self.ask('Remove that product from my cart.', cart=cart))['quantity'], 0)
        self.assertEqual(self.search_calls, 0)

    def test_quantity_stock_and_ambiguous_cart(self):
        cart = [{'id': 's1', 'name': 'Samsung Phone A', 'price': 20000, 'quantity': 1}]
        self.assertNotIn('SHOPAI_CART_ACTION', self.ask('Increase the quantity to 6', cart=cart))
        self.assertEqual(self.search_calls, 0)
        cart.append({'id': 's2', 'name': 'Samsung Phone B', 'price': 24000, 'quantity': 1})
        answer = self.ask('Increase the quantity to two', sid='other-session-00001', cart=cart)
        self.assertIn('Which cart item', answer)
        self.assertNotIn('SHOPAI_CART_ACTION', answer)

    def test_cart_never_searches(self):
        for message in ['Show me my cart.', 'Remove that product from my cart.', 'Increase the quantity to two.', 'How do I add a product to my cart?', 'checkout my cart']:
            self.ask(message)
            self.assertEqual(self.search_calls, 0, message)

    def test_multiple_categories_filters_and_dedup(self):
        answer = self.ask('Show me mobiles and laptops under 50000')
        ids = self.ids(answer)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn('hp', ids)
        self.assertIn('s1', ids)
        self.assertNotIn('hp-high', ids)
        self.assertEqual(self.state()['search_filters']['category'], ['Mobiles', 'laptops'])
        self.assertEqual(self.ids(self.ask('Only HP')), ['hp'])

    def test_genuine_zero_and_general_question(self):
        answer = self.ask('Show Samsung phones under 1')
        self.assertIn("couldn't find", answer)
        self.assertNotIn('Active filters', answer)
        self.assertIn('Samsung', answer)
        self.assertIn('under ₹1', answer)
        with self.assertRaises(HTTPException) as failure:
            self.ask('Why should I shop here?')
        self.assertEqual(failure.exception.status_code, 503)

    def test_fewer_than_two_comparison(self):
        self.ask('Show USB cables')
        self.assertIn('at least two', self.ask('Compare the first two products'))
        self.assertEqual(self.search_calls, 0)
