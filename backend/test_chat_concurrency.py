"""Verify slow decision HTTP work yields to other requests."""
import asyncio
import time
import unittest
from unittest.mock import Mock
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService

class ChatConcurrencyTests(unittest.TestCase):
    def test_slow_laya_does_not_block_event_loop(self):
        service = ChatService(Mock())
        def decide(message):
            time.sleep(0.15)
            return {"choice": "general_query", "confidence": 0.9}
        service.laya.decide = decide
        async def verify():
            task = asyncio.create_task(service.generate_response(ChatRequest(message="thanks")))
            await asyncio.sleep(0.02)
            self.assertFalse(task.done(), "Slow inference blocked the event loop")
            self.assertIn("welcome", (await task).response)
        asyncio.run(verify())

    def test_slow_ollama_does_not_block_event_loop(self):
        service = ChatService(Mock())
        service.laya.decide = Mock(return_value={"choice": "general_query", "confidence": 0.9})
        service._filters = Mock(return_value={})
        def generate(*args, **kwargs):
            time.sleep(0.15)
            return "Controlled answer"
        service.ollama.generate = generate
        async def verify():
            task = asyncio.create_task(service.generate_response(ChatRequest(message="What is the return policy?")))
            await asyncio.sleep(0.02)
            self.assertFalse(task.done(), "Slow generation blocked the event loop")
            self.assertEqual((await task).response, "Controlled answer")
        asyncio.run(verify())

if __name__ == "__main__":
    unittest.main()
