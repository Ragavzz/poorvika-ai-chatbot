"""Product-page suggestion routing regressions, after the real Laya boundary."""
import asyncio
import json
from unittest.mock import Mock
import test_chat_regressions as regression
from app.schemas.chat import ChatRequest


class TestSuggestionClick(regression.TestChatRegressions):
    def setUp(self):
        super().setUp()
        self.tecno = self.service.search_tool.get_product_by_id("tecno-spark-go-1-glittery-white-64gb-4gb-ram")

    def test_popup_information_uses_existing_llm_after_laya(self):
        questions = ["Is the 120Hz refresh rate suitable for gaming on the Tecno Spark Go 1?", "How does the 13MP camera perform in low light?", "Can this phone be used with a 5G network?", "Is this phone worth buying?"]
        for choice in ("recommendation", "product_search", "general_query", "product_details"):
            for question in questions:
                with self.subTest(choice=choice, question=question):
                    self.service.laya.decide = Mock(return_value={"choice": choice, "confidence": 0.2, "source": "receptron-laya-onnx"})
                    self.service.ollama.generate = Mock(return_value="Controlled LLM output")
                    context = {"recent_product_ids": [self.tecno["id"]], "suggestion_product_id": self.tecno["id"], "cart": []}
                    request = ChatRequest(message=question + "\n\n<shopai_client_context>" + json.dumps(context) + "</shopai_client_context>")
                    response = asyncio.run(self.service.generate_response(request))
                    self.assertEqual(response.response, "Controlled LLM output")
                    self.service.laya.decide.assert_called_once_with(question)
                    self.service.ollama.generate.assert_called_once()
                    grounded = self.service.ollama.generate.call_args.args[1]["products"][0]
                    self.assertEqual(grounded["id"], self.tecno["id"])
                    self.assertIn("Network Type", grounded["flattened_specs"])

    def test_popup_search_and_similar_products_keep_catalog_behavior(self):
        for question in ("Show phones under ₹10000.", "Show similar products."):
            self.service.laya.decide = Mock(return_value={"choice": "product_search", "confidence": 0.5, "source": "receptron-laya-onnx"})
            self.service.ollama.generate = Mock(side_effect=AssertionError("Search should not invoke the LLM"))
            context = {"recent_product_ids": [self.tecno["id"]], "suggestion_product_id": self.tecno["id"], "cart": []}
            request = ChatRequest(message=question + "\n\n<shopai_client_context>" + json.dumps(context) + "</shopai_client_context>")
            response = asyncio.run(self.service.generate_response(request)).response
            self.assertIn("| Product |", response)
            self.assertNotIn("couldn't find", response)
            self.service.ollama.generate.assert_not_called()
