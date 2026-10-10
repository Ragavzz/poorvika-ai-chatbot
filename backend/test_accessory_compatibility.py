"""Accessory manufacturer/compatibility regressions with real isolated catalog rows."""
import asyncio
import unittest
from unittest.mock import Mock
import test_backend as fixtures
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService


class AccessoryCompatibilityTests(unittest.TestCase):
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

    def answer(self, message, choice="product_search"):
        self.service.laya.decide.return_value = {"choice": choice, "confidence": 0.5}
        answer = asyncio.run(self.service.generate_response(ChatRequest(message=message))).response
        self.service.laya.decide.assert_called_once_with(message)
        self.service.ollama.generate.assert_not_called()
        return answer

    def test_exact_screen_protector_query(self):
        message = "Show me " + self.protector["name"]
        filters = self.service._filters(message)
        self.assertIsNone(filters["brand"])
        self.assertIn("samsung", filters["search_term"])
        self.assertEqual(self.rows(message)[0]["id"], self.protector["id"])
        answer = self.answer(message)
        self.assertIn(self.protector["name"], answer)
        self.assertIn("₹999", answer)
        self.assertIn("Out of Stock", answer)
        self.assertNotIn("These options are currently in stock", answer)

    def test_samsung_manufacturer_is_retained(self):
        message = "Show me " + self.samsung["name"]
        self.assertEqual(self.service._filters(message)["brand"], "Samsung")
        self.assertEqual(self.rows(message)[0]["id"], self.samsung["id"])

    def test_other_manufacturer_and_compatible_brand_are_distinct(self):
        message = "Show me " + self.inbase["name"]
        filters = self.service._filters(message)
        self.assertEqual(filters["brand"], "Inbase")
        self.assertIn("samsung", filters["search_term"])
        self.assertEqual(self.rows(message)[0]["id"], self.inbase["id"])

    def test_nonexact_compatibility_search_retains_device_constraint(self):
        rows = self.rows("Find Inbase flip cover compatible with Samsung Tab A7 Lite")
        self.assertTrue(rows)
        self.assertTrue(all(p["brand"] == "Inbase" and "Samsung Tab A7 Lite" in p["name"] for p in rows))
        self.assertEqual(self.rows("Find Inbase flip cover compatible with Samsung UnknownDevice999"), [])

    def test_named_product_absent_does_not_use_recent_selection(self):
        name = "Inbase Flip Cover For Samsung UnknownDevice999 ( Black )"
        self.assertEqual(self.rows("Show me " + name), [])
        self.assertIsNone(self.service._resolve_product("Add " + name + " to my cart",
                                                       {"recent_product_ids": [self.inbase["id"]]}))

    def test_budget_not_bypassed_by_exact_name(self):
        self.assertEqual(self.rows("Show me " + self.protector["name"] + " under 500 rupees"), [])
        rows = self.rows("Show me " + self.protector["name"] + " under 1000 rupees")
        self.assertEqual(rows[0]["id"], self.protector["id"])

    def test_exact_tool_name_retains_explicit_filters(self):
        for filters in ({"brand": "Samsung"}, {"category": "Mobiles"},
                        {"max_price": 500}, {"in_stock_only": True}):
            with self.subTest(filters=filters):
                self.assertEqual(self.service.search_tool.search_products(
                    query="unmatched", exact_name=self.protector["name"], **filters), [])
        self.assertEqual(self.service.search_tool.search_products(
            query="unmatched", exact_name=self.protector["name"])[0]["id"], self.protector["id"])

    def test_compatible_number_is_not_price(self):
        filters = self.service._filters("Find screen protector for S7")
        self.assertIsNone(filters["min_price"])
        self.assertIsNone(filters["max_price"])
        rows = self.rows("Find screen protector for S7")
        self.assertTrue(rows)
        self.assertTrue(all("S7" in p["name"] for p in rows))
        self.assertEqual(self.rows("Find screen protector for S9"), [])

    def test_out_of_stock_named_add_is_rejected(self):
        answer = self.answer("Add " + self.protector["name"] + " to my cart", "add_to_cart")
        self.assertIn("out of stock", answer)
        self.assertNotIn("SHOPAI_ADD_TO_CART", answer)
        self.assertNotIn("Added", answer)

    def test_out_of_stock_quantity_increase_is_rejected(self):
        context = {"cart": [{"id": self.protector["id"], "quantity": 1}]}
        answer = self.service._cart_mutation_answer("Increase quantity of " + self.protector["name"],
                                                    context, "increase")
        self.assertIn("out of stock", answer)
        self.assertNotIn("SHOPAI_CART_ACTION", answer)

    def test_in_stock_named_add_remains_allowed(self):
        answer = self.answer("Add " + self.inbase["name"] + " to my cart", "add_to_cart")
        self.assertIn("[[SHOPAI_ADD_TO_CART:" + self.inbase["id"], answer)

    def test_sony_budget_searches_unchanged(self):
        for message in ("Show me Sony earphones under 1000 rupees", "Find Sony earphones below ₹1000",
                        "Show me all Sony earphones"):
            with self.subTest(message=message):
                self.assertIn("sony-mdr-ex15ap-earphone-black", [p["id"] for p in self.rows(message)])

    def test_recommendation_keeps_compatibility_constraint(self):
        filters = self.service._filters("Recommend Inbase flip cover for Samsung Tab A7 Lite", "recommendation")
        self.assertIn("samsung", filters["search_term"])
        rows = self.service._find_products(filters, recommendation=True)
        self.assertTrue(rows)
        self.assertTrue(all(p["in_stock"] and "Samsung Tab A7 Lite" in p["name"] for p in rows))

    def test_manufacturer_constraint_not_ignored_for_compatibility(self):
        self.assertEqual(self.rows("Find Samsung screen protector for Samsung Tab S7"), [])
        filters = self.service._filters("Find Samsung case compatible with Apple phone")
        self.assertEqual(filters["brand"], "Samsung")
        self.assertNotEqual(filters["category"], "Mobiles")
        self.assertIn("apple", filters["search_term"])

    def test_search_for_instruction_is_not_compatibility_link(self):
        rows = self.rows("Search for " + self.inbase["name"])
        self.assertEqual(rows[0]["id"], self.inbase["id"])


if __name__ == "__main__":
    unittest.main()
