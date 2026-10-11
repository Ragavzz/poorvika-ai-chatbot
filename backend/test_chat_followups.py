import asyncio
import json
import re
import unittest
from unittest.mock import Mock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database.base import Base
from app.models.product import Product
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService, SESSIONS

class FollowupTests(unittest.TestCase):
    def setUp(self):
        SESSIONS.clear()
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        rows = [('hp', 'HP Laptop', 'HP', 'Computers', 45000, True),
                ('dell', 'Dell Laptop', 'Dell', 'Computers', 40000, True),
                ('hp-high', 'HP Premium Laptop', 'HP', 'Computers', 60000, True),
                ('s1', 'Samsung Phone A', 'Samsung', 'Mobiles', 20000, True),
                ('s2', 'Samsung Phone B', 'Samsung', 'Mobiles', 24000, True),
                ('s3', 'Samsung Phone C', 'Samsung', 'Mobiles', 30000, True),
                ('sony', 'Sony Earphone A', 'Sony', 'Headphones', 900, True),
                ('sony2', 'Sony Earphone B', 'Sony', 'Headphones', 950, True),
                ('sony-high', 'Sony Earphone C', 'Sony', 'Headphones', 1200, True),
                ('cable', 'USB Cable', 'Generic', 'Data Cables', 300, True),
                ('dead', 'USB Charger', 'Generic', 'Battery Chargers', 400, False)]
        for pid, name, brand, category, price, available in rows:
            self.db.add(Product(id=pid, name=name, brand=brand, category=category,
                                price=price, online_price=price, in_stock=available,
                                stock=5 if available else 0, availability=str(available),
                                rating=4, flattened_specs={'Connector': 'USB'}))
        self.db.commit()
    def tearDown(self):
        self.db.close()
        self.engine.dispose()
    def ask(self, text, choice='general_query', sid='session-0000000001'):
        service = ChatService(self.db)  # Real request-scoped lifecycle
        service.laya.decide = Mock(return_value={'choice': choice, 'confidence': .9})
        service.ollama.generate = Mock(side_effect=AssertionError('Unexpected LLM'))
        response = asyncio.run(service.generate_response(ChatRequest(message=text +
            '\n\n<shopai_client_context>' + json.dumps({'session_id': sid}) + '</shopai_client_context>'))).response
        service.laya.decide.assert_called_once_with(text)
        return response
    def ids(self, response):
        match = re.search(r'\[\[SHOPAI_PRODUCTS:([^\]]*)\]\]', response)
        return match.group(1).split(',') if match else []
    def state(self):
        return SESSIONS['session-0000000001']['context']
    def test_laptop_brand_budget(self):
        self.ask('Show me laptops under ₹50,000')
        self.assertEqual(self.ids(self.ask('Only show HP laptops.')), ['hp'])
        self.assertEqual(self.state()['search_filters']['max_price'], 50000)
        self.assertEqual(len(SESSIONS['session-0000000001']['history']), 2)
    def test_cheapest(self):
        self.ask('Show me Samsung mobiles')
        self.assertEqual(self.ids(self.ask('Which one is the cheapest?')), ['s1'])
        self.assertIn('20,000', self.ask('What is its price?'))
        self.assertIn('In Stock', self.ask('Is it available in stock?'))
        self.assertIn('SHOPAI_ADD_TO_CART:s1', self.ask('Add it to my cart.'))
    def test_similar_and_empty(self):
        self.ask('Show me Sony earphones under ₹1000')
        answer = self.ask('Show me similar earphones.')
        self.assertEqual(self.ids(answer), [])
        self.assertIn('1000', answer)
        self.assertIn('Sony', answer)
        self.assertEqual(self.state()['recent_product_ids'], [])
    def test_similar_selected(self):
        self.ask('Show me Sony earphones under ₹1000')
        self.ask('Tell me about the first product', 'product_details')
        self.assertEqual(self.ids(self.ask('Show me similar earphones.')), ['sony2'])
    def test_another_option(self):
        self.ask('Show me Samsung mobiles under ?25000')
        self.ask('Which one is the cheapest?')
        self.assertEqual(self.ids(self.ask('Show me another option.')), ['s2'])
        self.assertEqual(self.state()['search_filters']['max_price'], 25000)

    def test_gaming_budget(self):
        self.ask('Recommend a phone for gaming', 'recommendation')
        answer = self.ask('My budget is ₹25,000.')
        self.assertEqual(set(self.ids(answer)), {'s1', 's2'})
        self.assertEqual(self.state()['search_filters']['use_case'], 'gaming')
        self.assertEqual(self.state()['search_filters']['max_price'], 25000)
    def test_available_first_and_stock_refresh(self):
        self.assertEqual(self.ids(self.ask('Show me available accessories')), ['cable'])
        self.assertIn('SHOPAI_ADD_TO_CART:cable', self.ask('Add the first product to my cart.'))
        self.db.query(Product).filter_by(id='cable').update({'in_stock': False, 'stock': 0})
        self.db.commit()
        answer = self.ask('Add the first product to my cart.')
        self.assertNotIn('SHOPAI_ADD_TO_CART', answer)
        self.assertIn('out of stock', answer)
    def test_ambiguity_and_isolation(self):
        self.ask('Show me products')
        answer = self.ask('What is its price?')
        self.assertEqual(self.ids(answer), [])
        self.assertIn('choose', answer)
        self.assertNotIn('SHOPAI_ADD_TO_CART', self.ask('Add it to my cart.'))
        self.assertEqual(self.ids(self.ask('What is its price?', sid='session-0000000002')), [])
        self.assertIn('choose', self.ask('Which one has the best specifications?'))

if __name__ == '__main__':
    unittest.main()
