"""Currency/filter regressions using the existing isolated real-catalog fixture."""
import asyncio
import unittest
from unittest.mock import Mock

import test_backend as fixtures
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService


class SearchBudgetRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.TestShopAIBackend.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        fixtures.TestShopAIBackend.tearDownClass.__func__(cls)

    def setUp(self):
        self.service = ChatService(self.db)
        self.service.laya.decide = Mock(return_value={"choice": "product_search", "confidence": 0.9})
        self.service.ollama.generate = Mock(side_effect=AssertionError("Catalog lookup must not call generation"))
        self.sony = self.service.search_tool.get_product_by_id("sony-mdr-ex15ap-earphone-black")

    def test_currency_units_are_budget_not_product_terms(self):
        for budget in ("under 1000 rupees", "under 1000 rupee", "below ₹1000", "under Rs. 1000",
                       "under INR 1,000", "under 1k rupees", "under rupees 1000", "under 1000 INR"):
            with self.subTest(budget=budget):
                query = "Show me Sony earphones " + budget
                filters = self.service._filters(query)
                self.assertEqual(filters["brand"], "Sony")
                self.assertEqual(filters["category"], "Headphones")
                self.assertEqual(filters["max_price"], 1000)
                self.assertIsNone(filters["search_term"])
                rows = self.service._find_products(filters)
                self.assertIn(self.sony["id"], [row["id"] for row in rows])

    def test_all_is_listing_modifier_not_required_product_term(self):
        filters = self.service._filters("Show me all Sony earphones")
        self.assertIsNone(filters["search_term"])
        rows = self.service._find_products(filters)
        self.assertIn(self.sony["id"], [row["id"] for row in rows])
        self.assertTrue(all(row["brand"] == "Sony" and row["category"] == "Headphones" for row in rows))

    def test_currency_cleanup_preserves_named_model_and_genuine_empty_budget(self):
        filters = self.service._filters("Show Sony MDR-EX15AP earphones under 1000 rupees")
        self.assertEqual(filters["search_term"], "mdr ex15ap")
        self.assertIn(self.sony["id"], [row["id"] for row in self.service._find_products(filters)])
        filters = self.service._filters("Show Sony earphones under 1 rupee")
        self.assertEqual(self.service._find_products(filters), [])

    def test_chat_formats_matching_catalog_row_after_model_decision(self):
        response = asyncio.run(self.service.generate_response(
            ChatRequest(message="Show me Sony earphones under 1000 rupees"))).response
        self.assertIn(self.sony["name"], response)
        self.assertIn("₹829", response)
        self.assertIn("[[SHOPAI_PRODUCTS:" + self.sony["id"], response)
        self.service.laya.decide.assert_called_once_with("Show me Sony earphones under 1000 rupees")
        self.service.ollama.generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
