"""Regression tests for the isolated LLM suggestion endpoint."""
import json
import unittest
from unittest.mock import Mock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.config import settings
from app.routes.suggestions import suggestions_router


class SuggestionTests(unittest.TestCase):
    def setUp(self):
        from app.services.suggestion_service import CACHE
        CACHE.clear()
        app = FastAPI()
        app.include_router(suggestions_router)
        self.generation = patch.object(settings, 'OLLAMA_ENABLED', True)
        self.generation.start()
        self.addCleanup(self.generation.stop)
        self.client = TestClient(app)
        self.product = {"name": "Test phone", "brand": "Test", "price": 7299, "specifications": {"RAM": "4GB"}}

    def test_disabled_provider_never_calls_model(self):
        with patch.object(settings, 'OLLAMA_ENABLED', False), patch("app.services.ollama_service.HTTP.post") as send:
            result = self.client.post("/api/chat/suggestions", json={"product": self.product})
        self.assertEqual(result.status_code, 503)
        self.assertNotIn('suggestions', result.json())
        send.assert_not_called()

    def post_output(self, output):
        from app.services.suggestion_service import CACHE
        CACHE.clear()
        response = Mock()
        response.json.return_value = {"message": {"content": output}}
        with patch("app.services.ollama_service.HTTP.post", return_value=response) as send:
            result = self.client.post("/api/chat/suggestions", json={"product": self.product})
        return result, send

    def test_returns_only_model_questions_using_existing_config(self):
        questions = ["Could this test phone suit my commute?", "How does this test phone compare for battery life?", "Would the supplied RAM suit daily multitasking?", "Which option fits a busy schedule?"]
        result, send = self.post_output(json.dumps(questions))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["suggestions"], questions)
        self.assertEqual(send.call_args.args[0], settings.OLLAMA_API_URL)
        payload = send.call_args.kwargs["json"]
        self.assertEqual(payload["model"], settings.OLLAMA_MODEL)
        compact_context = json.loads(payload["messages"][1]["content"])
        self.assertEqual(compact_context["name"], self.product["name"])
        self.assertEqual(compact_context["price"], self.product["price"])
        self.assertEqual(compact_context["specifications"], self.product["specifications"])
        self.assertEqual(payload["format"]["type"], "array")
        self.assertEqual((payload["format"]["minItems"], payload["format"]["maxItems"]), (4, 4))
        self.assertEqual(payload["options"]["num_predict"], 96)

    def test_invalid_model_outputs_fail_without_fallback(self):
        bad = ["not json", "{}", json.dumps({"suggestions": ["Too few questions?"]}), json.dumps(["Too few questions?"]), json.dumps(["Duplicate question?"] * 3), json.dumps(["Not a question", "Another invalid answer", "An unrelated answer"]), json.dumps([12, False, "A valid question here?"])]
        for output in bad:
            with self.subTest(output=output):
                result, _ = self.post_output(output)
                self.assertEqual(result.status_code, 503)
                self.assertNotIn("suggestions", result.json())

    def test_four_questions_are_supported(self):
        questions = [f"Does this phone suit {use}?" for use in ['gaming', 'travel', 'photography', 'work']]
        result, _ = self.post_output(json.dumps(questions))
        self.assertEqual(result.json()["suggestions"], questions)

    def test_invented_price_or_specification_hides_suggestions(self):
        questions = ['Does this phone have 512GB storage?', 'Is this suitable for work?', 'Which alternatives suit travel?']
        result, _ = self.post_output(json.dumps(questions))
        self.assertEqual(result.status_code, 503)
        self.assertNotIn('suggestions', result.json())

    def test_catalog_price_formatting_is_allowed(self):
        questions = ['Is this phone worth INR 7,299.00?', 'Is this suitable for work?', 'Which alternatives suit travel?', 'What should I know before choosing?']
        result, _ = self.post_output(json.dumps(questions))
        self.assertEqual(result.status_code, 200)

    def test_listing_ram_value_cannot_transfer_from_a06_to_a16_and_regenerates(self):
        listing = {"name": "Mobiles", "category": "Mobiles", "products": [
            {"id": "a06", "name": "Samsung Galaxy A06 (Black, 4GB-64GB)", "brand": "Samsung", "price": 7999,
             "specifications": {"RAM": "4GB", "Internal Storage": "64GB"}},
            {"id": "a16-6", "name": "Samsung Galaxy A16 5G (Blue Black, 6GB-128GB)", "brand": "Samsung", "price": 15999,
             "specifications": {"RAM": "6GB", "Internal Storage": "128GB"}},
            {"id": "a16-8", "name": "Samsung Galaxy A16 5G (Gold, 8GB-128GB)", "brand": "Samsung", "price": 17499,
             "specifications": {"RAM": "8GB", "Internal Storage": "128GB"}},
        ]}
        misleading = ["Are the Samsung Galaxy A16 models available in a 4GB RAM variant?",
                      "Does Samsung Galaxy A16 have 4GB of RAM?",
                      "How does the Samsung Galaxy A06 compare with the Samsung Galaxy A16 at 4GB RAM?",
                      "Does the Samsung Galaxy A16 cost 7,999?"]
        valid = ["Which listed Samsung color options are available?", "How do the listed mobile prices compare?",
                 "What should shoppers consider when choosing among these Samsung phones?",
                 "Does the Samsung Galaxy A06 have 4GB RAM?"]
        responses = []
        for output in (misleading, valid):
            response = Mock()
            response.raise_for_status.return_value = None
            response.json.return_value = {"message": {"content": json.dumps(output)}, "eval_duration": 1000000,
                                          "load_duration": 1000, "prompt_eval_duration": 1000, "total_duration": 2000000}
            responses.append(response)
        timings = {}
        with patch("app.services.ollama_service.HTTP.post", side_effect=responses) as send:
            from app.services.ollama_service import OllamaService
            result = OllamaService().generate_suggestions(listing, timings=timings)
        self.assertEqual(result.suggestions, valid)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(timings["ollama_call_count"], 2)
        self.assertEqual(timings["semantic_retry_count"], 1)
        self.assertEqual(len(timings["ollama_attempts"]), 2)
        self.assertTrue(all("ollama_wall_ms" in attempt and "generation_ms" in attempt for attempt in timings["ollama_attempts"]))
        self.assertIn("exact named product", send.call_args.kwargs["json"]["messages"][-1]["content"])
        self.assertLess(timings["association_validation_ms"], 20)

    def test_misleading_question_after_single_regeneration_returns_error_without_fallback(self):
        listing = {"name": "Mobiles", "category": "Mobiles", "products": [
            {"name": "Samsung Galaxy A06 4GB-64GB", "price": 7999},
            {"name": "Samsung Galaxy A16 6GB-128GB", "price": 15999},
        ]}
        wrong = ["Does the Samsung Galaxy A16 have 4GB RAM?", "How does the listed phone fit daily use?",
                 "Which option suits a mobile shopper?", "What should buyers consider before choosing?"]
        responses = []
        for _ in range(2):
            response = Mock()
            response.raise_for_status.return_value = None
            response.json.return_value = {"message": {"content": json.dumps(wrong)}}
            responses.append(response)
        with patch("app.services.ollama_service.HTTP.post", side_effect=responses) as send:
            result = self.client.post("/api/chat/suggestions", json={"product": listing})
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("suggestions", result.json())
        self.assertEqual(send.call_count, 2)

    def test_provider_unavailable_fails_safely(self):
        with patch("app.services.ollama_service.HTTP.post", side_effect=TimeoutError):
            result = self.client.post("/api/chat/suggestions", json={"product": self.product})
        self.assertEqual(result.status_code, 504)

    def test_invalid_context_never_calls_model(self):
        with patch("app.services.ollama_service.HTTP.post") as send:
            for product in [{}, {"name": "   "}, {"name": "Phone", "price": -1}]:
                self.assertEqual(self.client.post("/api/chat/suggestions", json={"product": product}).status_code, 422)
        send.assert_not_called()



class ChatSuggestionPromptTests(unittest.TestCase):
    def call_generate(self, context, message="Is the 120Hz refresh rate suitable for gaming?"):
        response = Mock()
        response.json.return_value = {"message": {"content": "LLM answer"}}
        with patch("app.services.ollama_service.HTTP.post", return_value=response) as post:
            from app.services.ollama_service import OllamaService
            answer = OllamaService().generate(message, context)
        self.assertEqual(answer, "LLM answer")
        return post.call_args.kwargs["json"]

    def test_normal_chat_prompt_and_settings_are_unchanged(self):
        from app.services.ollama_service import SYSTEM_PROMPT
        payload = self.call_generate({"products": [{"name": "Phone", "price": 100, "in_stock": True, "flattened_specs": {"Refresh Rate": "120Hz"}}]})
        self.assertEqual(payload["messages"][0]["content"], SYSTEM_PROMPT)
        self.assertEqual(payload["options"], {"temperature": 0.1, "num_predict": 72, "num_ctx": 2048})
        self.assertNotIn("flattened_specs", payload["messages"][1]["content"])

    def test_popup_information_retains_and_highlights_catalog_specs(self):
        payload = self.call_generate({"suggestion_information": True, "products": [{"name": "Phone", "price": 100, "in_stock": True, "flattened_specs": {"Refresh Rate": "120Hz", "Network Type": "4G"}}]})
        self.assertIn("Refresh Rate: 120Hz", payload["messages"][1]["content"])
        self.assertIn("flattened_specs", payload["messages"][1]["content"])

    def test_broad_evaluation_retains_all_catalog_specs(self):
        payload = self.call_generate({"suggestion_information": True, "products": [{"name": "Phone", "price": 100, "in_stock": True, "flattened_specs": {"Generic Name": "Smart Phone", "Refresh Rate": "120Hz", "Primary Camera": "13MP"}}]}, "Is this phone worth buying?")
        self.assertIn("Refresh Rate: 120Hz", payload["messages"][1]["content"])
        self.assertIn("Primary Camera: 13MP", payload["messages"][1]["content"])

if __name__ == "__main__":
    unittest.main()
