"""Verify slow decision HTTP work yields to other requests."""
import asyncio
import time
import unittest
from unittest.mock import Mock, patch
from app.config import settings
from fastapi import HTTPException
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService

class ChatConcurrencyTests(unittest.TestCase):
    def test_slow_laya_does_not_block_event_loop(self):
        with patch.object(settings, 'OLLAMA_ENABLED', False):
            service = ChatService(Mock())
            def decide(message):
                time.sleep(0.15)
                return {"choice": "general_query", "confidence": 0.9}
            service.laya.decide = decide
            async def verify():
                task = asyncio.create_task(service.generate_response(ChatRequest(message="thanks")))
                await asyncio.sleep(0.02)
                self.assertFalse(task.done(), "Slow inference blocked the event loop")
                with self.assertRaises(HTTPException):
                    await task
            asyncio.run(verify())

    def test_slow_generation_wrapper_does_not_block_event_loop(self):
        service = ChatService(Mock())
        service.laya.decide = Mock(return_value={"choice": "general_query", "confidence": 0.9})
        service._filters = Mock(return_value={})
        def generate(*args, **kwargs):
            time.sleep(0.15)
            return "Controlled answer"
        # Exercise thread-pool scheduling independently of whether generation is
        # configured on. No Ollama client or model is invoked by this test.
        service._ollama_answer = generate
        async def verify():
            task = asyncio.create_task(service.generate_response(ChatRequest(message="What is the return policy?")))
            await asyncio.sleep(0.02)
            self.assertFalse(task.done(), "Slow generation blocked the event loop")
            self.assertEqual((await task).response, "Controlled answer")
        asyncio.run(verify())

    def test_disabled_generation_never_calls_ollama(self):
        with patch.object(settings, 'DECISION_PROVIDER', 'rules'), patch.object(settings, 'OLLAMA_ENABLED', False):
            service = ChatService(Mock())
            service._filters = Mock(return_value={})
            service.ollama.generate = Mock(side_effect=AssertionError('Unexpected Ollama call'))
            timings = {}
            with self.assertRaises(HTTPException) as failure:
                asyncio.run(service.generate_response(ChatRequest(message='What is the return policy?'), timings))
            self.assertEqual(failure.exception.status_code, 503)
            service.ollama.generate.assert_not_called()
            self.assertEqual(timings['decision_provider'], 'rule-based')
            self.assertEqual(timings['ollama_skipped_reason'], 'disabled_by_configuration')

if __name__ == "__main__":
    unittest.main()
