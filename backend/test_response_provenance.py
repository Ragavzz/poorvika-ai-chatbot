"""Response source checks with isolated SQL and stubbed generation, no models."""
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
import test_chat_followups as fixtures
from app.config import settings
from app.database.session import get_db
from app.routes.chat import chat_router


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        with patch.object(fixtures, 'create_engine', return_value=create_engine(
                'sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)):
            fixtures.FollowupTests.setUp(self)
    tearDown = fixtures.FollowupTests.tearDown

    def client(self):
        app = FastAPI()
        app.include_router(chat_router)
        app.dependency_overrides[get_db] = lambda: self.db
        return TestClient(app)

    def test_disabled_general_has_no_canned_reply_or_model_call(self):
        with patch.object(settings, 'DECISION_PROVIDER', 'rules'), patch.object(settings, 'OLLAMA_ENABLED', False), patch('app.services.ollama_service.HTTP.post') as model:
            for text in ['hello', 'thanks', 'Why should I shop here?']:
                result = self.client().post('/api/chat', json={'message': text})
                self.assertEqual(result.status_code, 503)
                self.assertNotIn('response', result.json())
                self.assertNotIn('Natural-language generation is disabled for this demo', result.text)
            model.assert_not_called()

    def test_catalog_and_comparison_sources_are_explicit(self):
        with patch.object(settings, 'DECISION_PROVIDER', 'rules'), patch.object(settings, 'OLLAMA_ENABLED', False), patch('app.services.ollama_service.HTTP.post') as model:
            client = self.client()
            search = client.post('/api/chat', json={'message': 'Show laptops under 50000'}).json()
            self.assertEqual(search['response_source'], 'deterministic_catalog')
            self.assertEqual(search['decision_provider'], 'rule-based')
            self.assertIn('HP Laptop', search['response'])
            comparison = client.post('/api/chat', json={'message': 'Compare the first two products'}).json()
            self.assertEqual(comparison['response_source'], 'deterministic_comparison')
            self.assertIn('at least two', comparison['response'])  # Safety clarification retained.
            model.assert_not_called()

    def test_controlled_generator_is_labeled_ollama_not_catalog(self):
        with patch.object(settings, 'DECISION_PROVIDER', 'rules'), patch.object(settings, 'OLLAMA_ENABLED', True), patch('app.services.ollama_service.OllamaService.generate', return_value='Unique controlled generated text') as model:
            result = self.client().post('/api/chat', json={'message': 'What is the return policy?'}).json()
            self.assertEqual(result['response'], 'Unique controlled generated text')
            self.assertEqual(result['response_source'], 'ollama')
            model.assert_called_once()

