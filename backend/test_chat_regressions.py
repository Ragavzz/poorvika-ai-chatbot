"""Routing/resolution regressions: real isolated catalog, controlled Laya decisions.

Live Laya/API verification is separate; these tests isolate backend boundaries
from inference variability and never alter the production database or cart.
"""
import asyncio
import json
import re
import unittest
from unittest.mock import Mock

import test_backend as fixtures
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService


class TestChatRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.TestShopAIBackend.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        fixtures.TestShopAIBackend.tearDownClass.__func__(cls)

    def setUp(self):
        self.service = ChatService(self.db)
        self.service.laya.decide = Mock()
        self.service.ollama.generate = Mock(side_effect=AssertionError("Unexpected inference call"))
        self.apple = self.service.search_tool.get_product_by_id("apple-iphone-13-blue-128gb")
        self.samsung = self.service.search_tool.search_products(query="galaxy a16 5g", brand="Samsung", limit=1)[0]
        self.cart = [dict(id=p["id"], name=p["name"], price=p["price"], quantity=2) for p in [self.apple, self.samsung]]

    def answer(self, query, choice, *, expected=None, recent=None, cart=None):
        self.service.laya.decide.return_value = dict(choice=choice, confidence=0.5, source="receptron-laya-onnx")
        context = dict(recent_product_ids=recent or [], cart=cart or [])
        request = ChatRequest(message=query + "\n\n<shopai_client_context>" + json.dumps(context) + "</shopai_client_context>")
        with self.assertLogs("shopai.services.chat", level="INFO") as logs:
            response = asyncio.run(self.service.generate_response(request)).response
        self.assertTrue(any(f"INTENT/ACTION: {expected or choice} " in line for line in logs.output))
        self.service.laya.decide.assert_called_once_with(query)
        self.service.ollama.generate.assert_not_called()
        return response

    def assert_add(self, query, expected_product, recent=None):
        response = self.answer(query, "add_to_cart", recent=recent)
        self.assertIn(f"[[SHOPAI_ADD_TO_CART:{expected_product['id']}]]", response)
        self.assertIn(expected_product["name"], response)
        self.assertIn(f"{expected_product['price']:,.0f}", response)

    def assert_details(self, query, expected_product, recent=None):
        response = self.answer(query, "product_details", recent=recent)
        self.assertTrue(response.startswith(f"### **{expected_product['name']}**"))
        self.assertNotIn("SHOPAI_ADD_TO_CART", response)
        self.assertIn(f"[[SHOPAI_PRODUCTS:{expected_product['id']}]]", response)

    def assert_command(self, query, operation, target, choice="cart_action", cart=None):
        response = self.answer(query, choice, expected="cart_action", cart=self.cart if cart is None else cart)
        match = re.search(r"\[\[SHOPAI_CART_ACTION:(\{.*?\})\]\]", response)
        self.assertIsNotNone(match)
        command = json.loads(match.group(1))
        self.assertEqual(command, dict(action=operation, product_id=self.apple["id"], expected_quantity=(cart or self.cart)[0]["quantity"], quantity=target))
        self.assertNotIn("SHOPAI_ADD_TO_CART", response)

    def test_gaming_budget_recommendation(self):
        response = self.answer("I need a good phone for gaming under 30000", "recommendation")
        filters = self.service._filters("I need a good phone for gaming under 30000", "recommendation")
        self.assertEqual(filters["category"], "Mobiles")
        self.assertEqual(filters["max_price"], 30000)
        self.assertEqual(filters["use_case"], "gaming")
        self.assertIsNone(filters["search_term"])
        self.assert_recommendations(response, 30000)

    def test_gaming_recommendation_without_budget(self):
        response = self.answer("Which phone is best for gaming?", "recommendation")
        self.assert_recommendations(response)

    def assert_recommendations(self, response, budget=None):
        ids = re.search(r"\[\[SHOPAI_PRODUCTS:([^\]]+)\]\]", response).group(1).split(",")
        self.assertTrue(ids)
        products = [self.service.search_tool.get_product_by_id(pid) for pid in ids]
        self.assertTrue(all(p["category"] == "Mobiles" and p["in_stock"] for p in products))
        if budget is not None:
            self.assertTrue(all(p["price"] <= budget for p in products))
        ratings = [p["rating"] or 0 for p in products]
        self.assertEqual(ratings, sorted(ratings, reverse=True))
        self.assertIn("don't have verified performance comparisons", response)

    def test_details_named_apple(self):
        self.assert_details("Tell me about Apple iPhone 13", self.apple)

    def test_details_named_samsung(self):
        self.assert_details("Give me details about Samsung Galaxy A16 5G", self.samsung)

    def test_specs_named_apple(self):
        self.assert_details("What are the specs of Apple iPhone 13?", self.apple)

    def test_add_named_apple(self):
        self.assert_add("Add Apple iPhone 13 to my cart", self.apple)

    def test_add_named_samsung(self):
        self.assert_add("Add Samsung Galaxy A16 5G to my cart", self.samsung)

    def test_explicit_model_qualifier_is_preserved(self):
        pro = self.service.search_tool.get_product_by_id("apple-iphone-13-pro-graphite-1tb")
        self.assert_add("Add Apple iPhone 13 Pro to my cart", pro)

    def test_meaningful_model_word_is_not_instruction_filler(self):
        filters = self.service._filters("Tell me about Acer One Z2 493", "product_details")
        self.assertEqual(filters["search_term"], "acer one z2 493")

    def test_about_a_numbered_model_does_not_create_a_price_filter(self):
        filters = self.service._filters("Tell me about Oppo A16", "product_details")
        self.assertIsNone(filters["min_price"])
        self.assertIsNone(filters["max_price"])
        self.assertEqual(filters["search_term"], "oppo a16")

    def test_add_named_sony(self):
        sony = self.service.search_tool.search_products(query="mdr ex15ap", brand="Sony", limit=1)[0]
        self.assert_add("Add Sony MDR-EX15AP Earphone to my cart", sony)

    def test_polite_named_add_command(self):
        self.assert_add("Can you please add Apple iPhone 13 to my cart", self.apple)

    def test_question_about_adding_does_not_mutate_cart(self):
        response = self.answer("How do I add Apple iPhone 13 to my cart?", "add_to_cart", expected="product_search", recent=[self.apple["id"]])
        self.assertNotIn("SHOPAI_ADD_TO_CART", response)

    def test_negated_add_does_not_mutate_cart(self):
        response = self.answer("Do not add Apple iPhone 13 to my cart", "add_to_cart", expected="product_search", recent=[self.apple["id"]])
        self.assertNotIn("SHOPAI_ADD_TO_CART", response)

    def test_remove_named_apple(self):
        self.assert_command("Remove Apple iPhone 13 from my cart", "remove", 0)

    def test_increase_named_apple(self):
        self.assert_command("Increase quantity of Apple iPhone 13", "increase", 3, choice="add_to_cart")

    def test_decrease_named_apple(self):
        self.assert_command("Decrease quantity of Apple iPhone 13", "decrease", 1, choice="add_to_cart")

    def test_decrease_last_item_removes(self):
        cart = [dict(self.cart[0], quantity=1)]
        self.assert_command("Decrease quantity of Apple iPhone 13", "decrease", 0, cart=cart)

    def test_add_named_overrides_stale_selection(self):
        self.assert_add("Add Apple iPhone 13 to my cart", self.apple, recent=[self.samsung["id"]])

    def test_details_named_overrides_stale_selection(self):
        self.assert_details("Tell me about Samsung Galaxy A16 5G", self.samsung, recent=[self.apple["id"]])

    def test_unknown_explicit_name_never_uses_stale_selection(self):
        response = self.answer("Tell me about nonexistentproductzzzz", "product_details", recent=[self.apple["id"]])
        self.assertNotIn(self.apple["name"], response)
        self.assertIn("Which product", response)

    def test_reference_uses_selected_product_without_adding(self):
        self.assert_details("Tell me about it", self.apple, recent=[self.apple["id"]])

    def test_reference_add_uses_selected_product(self):
        self.assert_add("Add it to my cart", self.apple, recent=[self.apple["id"]])

    def test_reference_with_category_uses_selected_product(self):
        self.assert_details("Tell me about this phone", self.apple, recent=[self.apple["id"]])

    def test_thank_you_cannot_add_even_with_wrong_laya_decision(self):
        response = self.answer("Thank you", "add_to_cart", expected="general_query", recent=[self.apple["id"]], cart=self.cart)
        self.assertIn("You're welcome", response)
        self.assertNotIn("SHOPAI_ADD_TO_CART", response)

    def test_cart_view_uses_client_cart_despite_wrong_laya_decision(self):
        response = self.answer("What's in my cart?", "product_search", expected="cart_action", cart=self.cart)
        for item in self.cart:
            self.assertIn(item["name"], response)
        self.assertIn("Qty: 2", response)

    def test_cart_view_empty_context_never_invents_contents(self):
        response = self.answer("What's in my cart?", "cart_action", recent=[self.apple["id"]])
        self.assertIn("empty", response)
        self.assertNotIn(self.apple["name"], response)

    def test_mutation_missing_from_cart_does_not_emit_command(self):
        response = self.answer("Remove Apple iPhone 13 from my cart", "cart_action", cart=[self.cart[1]])
        self.assertIn("isn't in your cart", response)
        self.assertNotIn("SHOPAI_CART_ACTION", response)

    def test_add_out_of_stock_does_not_emit_command(self):
        self.service._resolve_product = Mock(return_value=dict(self.apple, in_stock=False))
        response = self.answer("Add Apple iPhone 13 to my cart", "add_to_cart")
        self.assertIn("out of stock", response)
        self.assertNotIn("SHOPAI_ADD_TO_CART", response)

    def test_recommendation_other_use_case_is_not_literal_name_filter(self):
        response = self.answer("Suggest a phone for photography under 30000", "recommendation")
        self.assertIn("SHOPAI_PRODUCTS", response)
        self.assertIsNone(self.service._filters("Suggest a phone for photography under 30000", "recommendation")["search_term"])


def search_test(query, brand=None, budget=None, expect_results=True):
    def run(self):
        response = self.answer(query, "product_search")
        marker = re.search(r"\[\[SHOPAI_PRODUCTS:([^\]]+)\]\]", response)
        if not expect_results:
            self.assertIsNone(marker)
            self.assertIn("couldn't find", response)
            return
        self.assertIsNotNone(marker)
        products = [self.service.search_tool.get_product_by_id(pid) for pid in marker.group(1).split(",")]
        if brand:
            self.assertTrue(all(p["brand"] == brand for p in products))
        if budget is not None:
            self.assertTrue(all(p["price"] <= budget for p in products))
    return run


for name, query, brand, budget, results in [
    ("apple", "Show Apple iphone under 50000", "Apple", 50000, True),
    ("samsung", "Show Samsung phones under 30000", "Samsung", 30000, True),
    ("sony", "Show Sony earphones under 1000", "Sony", 1000, True),
    ("laptops", "Show me laptops", None, None, True),
    ("mobiles", "Show mobiles", None, None, True),
    ("no_sony", "Show Sony earphones under 1", "Sony", 1, False),
    ("no_iphone", "Show iPhone under ₹100", None, 100, False),
    ("no_gaming", "Show gaming phones under ₹1", None, 1, False),
]:
    setattr(TestChatRegressions, "test_search_" + name, search_test(query, brand, budget, results))


def general_test(query, expected):
    def run(self):
        response = self.answer(query, "general_query")
        self.assertIn(expected, response)
        self.assertNotIn("SHOPAI_ADD_TO_CART", response)
    return run


for name, query, expected in [
    ("hi", "hi", "Tell me what you're looking for"),
    ("hello", "hello", "Tell me what you're looking for"),
    ("bye", "bye", "Have a great day"),
]:
    setattr(TestChatRegressions, "test_general_" + name, general_test(query, expected))
