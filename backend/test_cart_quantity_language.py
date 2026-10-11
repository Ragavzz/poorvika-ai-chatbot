"""Real rule/parser/cart resolution with isolated SQL fixtures; no inference."""
import asyncio
import json
import re
import unittest
from unittest.mock import patch
import test_chat_followups as fixtures
from app.config import settings
from app.models.product import Product
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.cart_operations import parse_cart_operation
from app.services.decision_provider import RuleDecisionProvider

IPHONE = 'apple-iphone-13-blue-128gb'


class QuantityLanguageTests(unittest.TestCase):
    def setUp(self):
        fixtures.FollowupTests.setUp(self)
        for pid, name in [(IPHONE, 'Apple iPhone 13 (Blue, 128GB)'),
                          ('apple-iphone-13-red-128gb', 'Apple iPhone 13 (Red, 128GB)')]:
            self.db.add(Product(id=pid, name=name, brand='Apple', category='Mobiles',
                price=49900, online_price=49900, stock=5, in_stock=True, availability='True'))
        self.db.commit()
        self.cart = [{'id': IPHONE, 'name': 'Apple iPhone 13 (Blue, 128GB)', 'price': 49900, 'quantity': 2},
                     {'id': 's1', 'name': 'Samsung Phone A', 'price': 20000, 'quantity': 1}]

    tearDown = fixtures.FollowupTests.tearDown

    def ask(self, message, cart=None, selected='s1'):
        with patch.object(settings, 'DECISION_PROVIDER', 'rules'), patch.object(settings, 'OLLAMA_ENABLED', False):
            service = ChatService(self.db)
            timings = {}
            context = {'cart': self.cart if cart is None else cart,
                       'recent_product_ids': ['s1'], 'selected_product_id': selected}
            with patch.object(service.search_tool, 'search_products', side_effect=AssertionError('Unexpected search')), patch.object(service, '_ollama_answer', side_effect=AssertionError('Unexpected LLM path')):
                answer = asyncio.run(service.generate_response(ChatRequest(message=message +
                    '\n\n<shopai_client_context>' + json.dumps(context) + '</shopai_client_context>'), timings)).response
            self.assertEqual(timings['decision_provider'], 'rule-based')
            self.assertEqual(timings['resolved_action'], 'cart_action')
            self.assertEqual(timings['laya_call_count'], 0)
            self.assertNotIn('Use the cart', answer)
            return answer

    def command(self, message, cart=None):
        return json.loads(re.search(r'\[\[SHOPAI_CART_ACTION:(\{.*?\})\]\]', self.ask(message, cart)).group(1))

    def test_exact_reduce_product_first_absolute_target(self):
        query = 'Reduce the iPhone 13 quantity to one'
        self.assertEqual(RuleDecisionProvider().decide(query)['choice'], 'cart_action')
        self.assertEqual(parse_cart_operation(query), {'operation': 'decrease', 'reference': 'iPhone 13'})
        self.assertEqual(self.command(query), {'action': 'set_quantity', 'product_id': IPHONE, 'expected_quantity': 2, 'quantity': 1})

    def test_all_requested_absolute_forms(self):
        for query in ['decrease quantity to 1', 'set iPhone 13 quantity to 1', 'change the quantity to one',
                      'Please reduce the IPHONE 13 quantity to one.', 'set apple-iphone-13-blue-128gb quantity to 1']:
            with self.subTest(query=query):
                command = self.command(query, self.cart[:1])
                self.assertEqual(command['product_id'], IPHONE)
                self.assertEqual(command['quantity'], 1)

    def test_increase_decrease_relative_and_absolute(self):
        for query, expected in [('Increase the iPhone 13 quantity to four', 4),
                                ('reduce the iPhone 13 quantity by one', 1),
                                ('set iPhone 13 quantity to two', 2),
                                ('Decrease quantity of iPhone 13 to 1', 1)]:
            self.assertEqual(self.command(query)['quantity'], expected)
        larger = [{**self.cart[0], 'quantity': 4}]
        self.assertEqual(self.command('Reduce the iPhone 13 quantity to one', larger)['quantity'], 1)

    def test_ambiguous_name_does_not_use_previous_selection(self):
        cart = [*self.cart, {**self.cart[0], 'id': 'apple-iphone-13-red-128gb', 'name': 'Apple iPhone 13 (Red, 128GB)'}]
        answer = self.ask('Reduce the iPhone 13 quantity to one', cart, selected=IPHONE)
        self.assertIn('Which cart item', answer)
        self.assertIn('Blue', answer)
        self.assertIn('Red', answer)
        self.assertNotIn('SHOPAI_CART_ACTION', answer)
        self.assertEqual(self.command('set iPhone 13 Blue 128GB quantity to 1', cart)['product_id'], IPHONE)

    def test_missing_named_item_never_updates_only_other_item(self):
        answer = self.ask('Reduce the iPhone 13 quantity to one', self.cart[1:], selected=IPHONE)
        self.assertIn("isn't in your cart", answer)
        self.assertNotIn('SHOPAI_CART_ACTION', answer)

    def test_sony_plural_name_resolves_to_exact_cart_product_id(self):
        sony_id = 'sony-mdr-ex15ap-earphone-black'
        sony_name = 'Sony MDR-EX15AP Earphone ( Black )'
        self.db.add(Product(id=sony_id, name=sony_name, brand='Sony', category='Headphones',
            price=829, online_price=829, stock=10, in_stock=True, availability='True'))
        self.db.commit()
        cart = [{'id': sony_id, 'name': sony_name, 'price': 829, 'quantity': 1},
                {'id': 'other', 'name': 'Other Product', 'price': 74226, 'quantity': 5}]
        answer = self.ask('Remove the Sony MDR-EX15AP earphones from my cart.', cart)
        match = re.search(r'\[\[SHOPAI_CART_ACTION:(\{.*?\})\]\]', answer)
        self.assertIsNotNone(match)
        command = json.loads(match.group(1))
        self.assertEqual(command, {'action': 'remove', 'product_id': sony_id,
            'expected_quantity': 1, 'quantity': 0})

    def test_nonexistent_named_item_lists_actual_cart_without_mutation(self):
        cart = [{'id': 's1', 'name': 'Samsung Phone A', 'price': 20000, 'quantity': 2},
                {'id': 's2', 'name': 'Samsung Phone B', 'price': 24000, 'quantity': 1}]
        answer = self.ask('Remove Sony MDR-EX15AP earphones from my cart.', cart)
        self.assertIn("isn't in your cart", answer)
        self.assertIn('Samsung Phone A', answer)
        self.assertIn('Samsung Phone B', answer)
        self.assertIn('Qty: 2', answer)
        self.assertNotIn('SHOPAI_CART_ACTION', answer)

    def test_stock_minimum_and_invalid_quantities(self):
        for query in ['set iPhone 13 quantity to 6', 'set iPhone 13 quantity to -1', 'change the quantity', 'set iPhone 13 quantity to 1.5']:
            self.assertNotIn('SHOPAI_CART_ACTION', self.ask(query, self.cart[:1]))
        command = self.command('set iPhone 13 quantity to zero')
        self.assertEqual(command['quantity'], 0) # Existing minimum rule: zero removes.

    def test_updated_totals_follow_actual_command_target(self):
        command = self.command('Reduce the iPhone 13 quantity to one')
        updated = [{**item, 'quantity': command['quantity']} if item['id'] == command['product_id'] else item for item in self.cart]
        answer = self.ask('What is my current total?', updated)
        self.assertEqual(answer, 'Your current cart total is ₹69,900 for 2 items.')
        self.assertEqual(self.cart[0]['quantity'], 2) # Backend never mutates a client snapshot.

    def test_updated_cart_total_and_subsequent_cart_view_use_new_client_snapshot(self):
        command = self.command('Reduce the iPhone 13 quantity to one')
        updated = [{**item, 'quantity': command['quantity']} if item['id'] == command['product_id'] else item for item in self.cart]
        self.assertEqual(self.ask('What is my current total?', updated), 'Your current cart total is ₹69,900 for 2 items.')
        listing = self.ask('Show me my cart.', updated)
        self.assertIn('Apple iPhone 13 (Blue, 128GB)', listing)
        self.assertIn('Qty: 1', listing)
        self.assertIn('Samsung Phone A', listing)
        self.assertIn('Total: ₹69,900', listing)

    def test_session_cart_is_replaced_by_each_current_frontend_snapshot(self):
        service = ChatService(self.db)
        cart = [dict(item) for item in self.cart]
        session_id = 'cart-current-snapshot-0001'

        async def send(message, current_cart):
            context = {'session_id': session_id, 'cart': current_cart}
            request = ChatRequest(message=message + '\n\n<shopai_client_context>' +
                json.dumps(context) + '</shopai_client_context>')
            return (await service.generate_response(request)).response

        with patch.object(settings, 'DECISION_PROVIDER', 'rules'), patch.object(settings, 'OLLAMA_ENABLED', False):
            removal = asyncio.run(send('Remove the iPhone 13 from my cart.', cart))
            command = json.loads(re.search(r'\[\[SHOPAI_CART_ACTION:(\{.*?\})\]\]', removal).group(1))
            self.assertEqual(command['product_id'], IPHONE)
            cart = [item for item in cart if item['id'] != command['product_id']]
            total = asyncio.run(send('What is my current total?', cart))
            self.assertEqual(total, 'Your current cart total is ₹20,000 for 1 item.')
            listing = asyncio.run(send('Show me my cart.', cart))
            self.assertIn('Samsung Phone A', listing)
            self.assertNotIn('Apple iPhone 13', listing)
            self.assertIn('Total: ₹20,000', listing)
