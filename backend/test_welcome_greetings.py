import asyncio
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from app.config import settings
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.decision_provider import is_greeting
from app.services.ollama_service import OllamaService


class GreetingTests(unittest.TestCase):
    def test_exact_intent_boundary(self):
        for text in ['hi', 'Hello!', 'hey', 'good morning', 'Good afternoon.', 'good evening']:
            self.assertTrue(is_greeting(text))
        for text in ['hi show phones', 'Sony', 'yes', 'only HP', 'add it', 'good morning show phones']:
            self.assertFalse(is_greeting(text))

    def test_greetings_override_bad_decision_without_catalog_calls(self):
        for text in ['hi', 'hello', 'hey', 'good morning']:
            with self.subTest(text=text), patch.object(settings, 'OLLAMA_ENABLED', True):
                service = ChatService(Mock())
                service.laya.decide = Mock(return_value={'choice': 'product_search'})
                service.search_tool = Mock()
                service.ollama.generate = Mock(return_value='Actual model response')
                timings = {}
                result = asyncio.run(service.generate_response(ChatRequest(message=text), timings))
                self.assertEqual(result.response, 'Actual model response')
                self.assertEqual(timings['resolved_action'], 'general_query')
                service.laya.decide.assert_called_once_with(text)
                self.assertTrue(service.ollama.generate.call_args.args[1]['greeting'])
                self.assertEqual(service.search_tool.mock_calls, [])

    def test_greeting_service_failure_is_truthful(self):
        for enabled in [True, False]:
            with patch.object(settings, 'OLLAMA_ENABLED', enabled):
                service = ChatService(Mock())
                service.laya.decide = Mock(return_value={'choice': 'product_search'})
                service.ollama.generate = Mock(side_effect=ConnectionError('offline'))
                with self.assertRaises(HTTPException) as failure:
                    asyncio.run(service.generate_response(ChatRequest(message='hi')))
                self.assertEqual(failure.exception.status_code, 503)
                self.assertNotIn('catalog', failure.exception.detail)
                self.assertEqual(service.ollama.generate.call_count, int(enabled))

    def test_general_prompt_does_not_require_empty_catalog_error(self):
        response = Mock()
        response.json.return_value = {'message': {'content': 'Model greeting'}}
        with patch('app.services.ollama_service.HTTP.post', return_value=response) as post:
            OllamaService().generate('hi', {'greeting': True})
        prompt = post.call_args.kwargs['json']['messages'][0]['content']
        self.assertIn('welcome', prompt)
        self.assertIn('No catalog search has', prompt)


if __name__ == '__main__':
    unittest.main()
