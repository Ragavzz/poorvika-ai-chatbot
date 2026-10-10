"""Short device/accessory queries: real isolated catalog; model choices are mocked."""
import asyncio
import copy
import json
import unittest
from unittest.mock import Mock
import test_backend as fixtures
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService


class ShortAccessoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.TestShopAIBackend.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        fixtures.TestShopAIBackend.tearDownClass.__func__(cls)

    def setUp(self):
        self.service = ChatService(self.db)
        self.service.laya.decide = Mock(return_value={"choice": "product_search", "confidence": 0.5})
        self.service.ollama.generate = Mock(side_effect=AssertionError("Unexpected generation"))
        self.protector = self.service.search_tool.get_product_by_id(
            "2-5d-clear-tempered-glass-screen-protector-for-samsung-tab-s7-plus-12-4-inch")
        self.samsung = self.service.search_tool.get_product_by_id("samsung-silicone-case-for-galaxy-a54-5g-lime")
        self.inbase = self.service.search_tool.get_product_by_id("inbase-flip-cover-for-samsung-tab-a7-lite-8-7-inch-black")

    def rows(self, message):
        return self.service._find_products(self.service._filters(message))

    def answer(self, message, choice="product_search", context=None):
        self.service.laya.decide.return_value = {"choice": choice, "confidence": 0.5}
        wire = message
        if context is not None:
            wire += "\n\n<shopai_client_context>" + json.dumps(context) + "</shopai_client_context>"
        reply = asyncio.run(self.service.generate_response(ChatRequest(message=wire))).response
        self.service.laya.decide.assert_called_once_with(message)
        self.service.ollama.generate.assert_not_called()
        return reply

    def test_short_query_resolves_real_out_of_stock_protector(self):
        message = "Show me the Samsung Tab S7 screen protector"
        filters = self.service._filters(message)
        self.assertIsNone(filters["brand"])
        self.assertIn("samsung", filters["search_term"])
        self.assertIn("s7", filters["search_term"])
        self.assertEqual(self.rows(message)[0]["id"], self.protector["id"])
        reply = self.answer(message)
        self.assertIn(self.protector["name"], reply)
        self.assertIn("₹999", reply)
        self.assertIn("Out of Stock", reply)
        self.assertNotIn("These options are currently in stock", reply)

    def test_long_exact_query_still_resolves(self):
        message = "Show me " + self.protector["name"]
        self.assertEqual(self.rows(message)[0]["id"], self.protector["id"])

    def test_samsung_manufactured_accessory_keeps_manufacturer(self):
        message = "Show me " + self.samsung["name"]
        self.assertEqual(self.service._filters(message)["brand"], "Samsung")
        self.assertEqual(self.rows(message)[0]["id"], self.samsung["id"])

    def test_inbase_implicit_device_accessory_keeps_actual_manufacturer(self):
        message = "Show me Inbase Samsung Tab A7 Lite flip cover"
        filters = self.service._filters(message)
        self.assertEqual(filters["brand"], "Inbase")
        self.assertIn("samsung", filters["search_term"])
        self.assertEqual(self.rows(message)[0]["id"], self.inbase["id"])

    def test_different_models_do_not_match_s7(self):
        for model in ("S9", "S6", "S70"):
            with self.subTest(model=model):
                ids = [p["id"] for p in self.rows("Show me the Samsung Tab " + model + " screen protector")]
                self.assertNotIn(self.protector["id"], ids)

    def test_nonexistent_accessory_does_not_fall_back_to_selection(self):
        message = "Show me the Samsung Tab UnknownDevice999 holographic protector"
        self.assertEqual(self.rows(message), [])
        self.assertIsNone(self.service._resolve_product("Add Samsung Tab S9 unknown-protector to my cart",
                                                       {"recent_product_ids": [self.inbase["id"]]}))

    def test_short_out_of_stock_add_rejected_cart_context_unchanged(self):
        context = {"recent_product_ids": [self.inbase["id"]], "cart": [
            {"id": self.inbase["id"], "name": self.inbase["name"], "price": self.inbase["price"], "quantity": 2}]}
        before = copy.deepcopy(context)
        reply = self.answer("Add the Samsung Tab S7 screen protector to my cart", "add_to_cart", context)
        self.assertIn("out of stock", reply)
        self.assertNotIn("SHOPAI_ADD_TO_CART", reply)
        self.assertNotIn("SHOPAI_CART_ACTION", reply)
        self.assertEqual(context, before)

    def test_quantity_increase_rejected_without_mutating_context(self):
        context = {"cart": [{"id": self.protector["id"], "quantity": 1}]}
        before = copy.deepcopy(context)
        reply = self.service._cart_mutation_answer("Increase quantity of the Samsung Tab S7 screen protector",
                                                   context, "increase")
        self.assertIn("out of stock", reply)
        self.assertNotIn("SHOPAI_CART_ACTION", reply)
        self.assertEqual(context, before)

    def test_manual_selection_context_does_not_override_named_search(self):
        reply = self.answer("Show me the Samsung Tab S7 screen protector", context={
            "recent_product_ids": [self.inbase["id"]], "cart": []})
        self.assertIn(self.protector["name"], reply)
        self.assertNotIn(self.inbase["name"], reply)

    def test_short_budget_constraint_is_retained(self):
        self.assertEqual(self.rows("Show me the Samsung Tab S7 screen protector under 500 rupees"), [])
        ids = [p["id"] for p in self.rows("Show me the Samsung Tab S7 screen protector under 1000 rupees")]
        self.assertIn(self.protector["id"], ids)

    def test_explicit_manufacturer_constraint_is_retained(self):
        filters = self.service._filters("Show me the Samsung Tab S7 screen protector by Samsung")
        self.assertEqual(filters["brand"], "Samsung")
        self.assertEqual(self.service._find_products(filters), [])

    def test_explicit_category_constraint_is_retained(self):
        filters = self.service._filters("Show me the Samsung Tab S7 screen protector in category Mobiles")
        self.assertEqual(filters["category"], "Mobiles")
        self.assertEqual(self.service._find_products(filters), [])

    def test_exact_alternative_obeys_all_tool_constraints(self):
        for constraint in ({"brand": "Samsung"}, {"category": "Mobiles"}, {"max_price": 500},
                           {"min_price": 2000}, {"in_stock_only": True}, {"min_rating": 5.1},
                           {"min_discount": 100}):
            with self.subTest(constraint=constraint):
                self.assertEqual(self.service.search_tool.search_products(
                    query="samsung tab s7 screen protector", exact_name=self.protector["name"], **constraint), [])

    def test_sony_budget_searches_still_work(self):
        for message in ("Show me Sony earphones under 1000 rupees", "Find Sony earphones below ₹1000"):
            with self.subTest(message=message):
                self.assertIn("sony-mdr-ex15ap-earphone-black", [p["id"] for p in self.rows(message)])


if __name__ == "__main__":
    unittest.main()
