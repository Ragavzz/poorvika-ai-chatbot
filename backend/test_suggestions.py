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
        app = FastAPI()
        app.include_router(suggestions_router)
        self.client = TestClient(app)
        self.product = {"name": "Test phone", "brand": "Test", "price": 7299, "specifications": {"RAM": "4GB"}}

    def post_output(self, output):
        response = Mock()
        response.json.return_value = {"message": {"content": output}}
        with patch("app.services.ollama_service.HTTP.post", return_value=response) as send:
            result = self.client.post("/api/chat/suggestions", json={"product": self.product})
        return result, send

    def test_returns_only_model_questions_using_existing_config(self):
        questions = ["Could this test phone suit my commute?", "How does this test phone compare for battery life?", "Would the supplied RAM suit daily multitasking?"]
        result, send = self.post_output(json.dumps({"suggestions": questions}))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["suggestions"], questions)
        self.assertEqual(send.call_args.args[0], settings.OLLAMA_API_URL)
        payload = send.call_args.kwargs["json"]
        self.assertEqual(payload["model"], settings.OLLAMA_MODEL)
        self.assertEqual(json.loads(payload["messages"][1]["content"]), self.product)

    def test_invalid_model_outputs_fail_without_fallback(self):
        bad = ["not json", "{}", json.dumps({"suggestions": ["Too few questions?"]}), json.dumps({"suggestions": ["Duplicate question?"] * 3}), json.dumps({"suggestions": ["Not a question", "Another invalid answer", "An unrelated answer"]}), json.dumps({"suggestions": [12, False, "A valid question here?"]})]
        for output in bad:
            with self.subTest(output=output):
                result, _ = self.post_output(output)
                self.assertEqual(result.status_code, 503)
                self.assertNotIn("suggestions", result.json())

    def test_four_questions_are_supported(self):
        questions = [f"Does this phone suit use case {index}?" for index in range(4)]
        result, _ = self.post_output(json.dumps({"suggestions": questions}))
        self.assertEqual(result.json()["suggestions"], questions)

    def test_provider_unavailable_fails_safely(self):
        with patch("app.services.ollama_service.HTTP.post", side_effect=TimeoutError):
            result = self.client.post("/api/chat/suggestions", json={"product": self.product})
        self.assertEqual(result.status_code, 503)

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
