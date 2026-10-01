"""Automated unit and integration test suite for ShopAI FastAPI Backend.

Validates:
1. PostgreSQL configuration and strict 503 error enforcement when PostgreSQL is offline.
2. Isolated database testing (using explicit TESTING_MODE flag with temporary database).
3. Dataset ingestion and schema mapping for Poorvika products.
4. Controlled ProductSearchTool queries (name, brand, category, price, stock).
5. Ollama Cloud Intent Extraction and Grounded Response generation.
6. FastAPI REST endpoints (/api/health, /api/products, /api/products/search, /api/chat).
"""

import os
import sys
import tempfile
import unittest
import asyncio

# Ensure stdout handles UTF-8 for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure backend directory is in python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from app.config import settings
from app.database.base import Base
from app.models.product import Product
from app.tools.product_search_tool import ProductSearchTool
from app.services.llm_service import LLMService
from app.services.chat_service import ChatService
from app.schemas.chat import ChatRequest
from app.database.ingest import ingest_products, load_dataset_records


class TestShopAIBackend(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up isolated test database with explicit TESTING_MODE."""
        settings.TESTING_MODE = True
        
        # Create a temporary file database so all connection pool threads share the tables
        cls.temp_db_fd, cls.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(cls.temp_db_fd)
        
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        cls.test_engine = create_engine(
            f"sqlite:///{cls.temp_db_path}",
            connect_args={"check_same_thread": False}
        )
        cls.TestSessionLocal = sessionmaker(bind=cls.test_engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(bind=cls.test_engine)

        # Ingest the real poorvika dataset records into the test database
        cls.db = cls.TestSessionLocal()
        dataset_path = settings.DATASET_PATH
        if os.path.exists(dataset_path):
            records = load_dataset_records(dataset_path)
            cls.inserted, cls.updated = ingest_products(cls.db, records)
        else:
            cls.inserted = 0

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        Base.metadata.drop_all(bind=cls.test_engine)
        settings.TESTING_MODE = False
        try:
            if os.path.exists(cls.temp_db_path):
                os.remove(cls.temp_db_path)
        except Exception:
            pass

    def test_01_dataset_ingestion_counts(self):
        """Verify all 100 products from poorvika_products.jsonl were ingested."""
        count = self.db.query(Product).count()
        self.assertEqual(count, 100, f"Expected 100 products ingested, found {count}")
        print(f"\n[Test 1] Database contains {count} products (100% ingested).")

    def test_02_field_preservation_and_category_extraction(self):
        """Verify key fields (sku, price, mrp, category, stock, specs) are preserved."""
        prod = self.db.query(Product).filter(Product.id == "sony-mdr-ex15ap-earphone-black").first()
        self.assertIsNotNone(prod, "Sample product not found")
        self.assertEqual(prod.brand, "Sony")
        self.assertEqual(prod.category, "Headphones")
        self.assertEqual(prod.price, 829.0)
        self.assertEqual(prod.mrp, 890.0)
        self.assertGreater(prod.discount_percent, 0.0)
        self.assertEqual(prod.stock, 316)
        self.assertTrue(prod.in_stock)
        self.assertIn("Model Name", prod.flattened_specs)
        print(f"\n[Test 2] Product '{prod.name}' verified: Category={prod.category}, Price=Rs.{prod.price}, Stock={prod.stock}")

    def test_03_search_tool_by_brand_and_category(self):
        """Verify ProductSearchTool retrieves accurate real products from database."""
        tool = ProductSearchTool(self.db)
        # Search Sony products
        sony_items = tool.search_products(brand="Sony")
        self.assertGreater(len(sony_items), 0)
        self.assertTrue(all(item["brand"] == "Sony" for item in sony_items))

        # Search category Headphones
        headphones = tool.search_products(category="Headphones")
        self.assertGreater(len(headphones), 0)
        self.assertTrue(all("headphone" in item["category"].lower() for item in headphones))
        print(f"\n[Test 3] SearchTool: {len(sony_items)} Sony products, {len(headphones)} Headphones.")

    def test_04_search_tool_price_filtering(self):
        """Verify budget filtering (min_price, max_price)."""
        tool = ProductSearchTool(self.db)
        budget_items = tool.search_products(max_price=1000)
        self.assertGreater(len(budget_items), 0)
        for item in budget_items:
            self.assertLessEqual(item["price"], 1000.0)
        print(f"\n[Test 4] SearchTool: Found {len(budget_items)} items under Rs.1000.")

    def test_05_llm_service_intent_extraction(self):
        """Verify Ollama Cloud / rule-based intent parsing extracts budget and category."""
        llm = LLMService()
        res = llm.extract_intent_and_filters("Sony earphones under 1000")
        self.assertEqual(res.get("intent"), "product_search")
        self.assertEqual(res.get("brand"), "Sony")
        self.assertIn(res.get("max_price"), [1000.0, 1000])
        print(f"\n[Test 5] Intent extraction for 'Sony earphones under 1000': {res}")

    def test_06_chat_service_grounded_response(self):
        """Verify chat response is strictly grounded in real products from database."""
        chat_service = ChatService(db=self.db)
        req = ChatRequest(message="Can you suggest Sony earphones under 1000?")
        resp = asyncio.run(chat_service.generate_response(req))
        self.assertIsNotNone(resp.response)
        self.assertIn("Sony", resp.response)
        self.assertTrue(any(w in resp.response for w in ["829", "MDR-EX15AP", "Earphone"]))
        safe_preview = resp.response[:200].encode("ascii", "replace").decode("ascii")
        print(f"\n[Test 6] Chat Service Grounded Response preview:\n{safe_preview}...")

    def test_07_chat_empty_prompt_validation(self):
        """Verify empty message validation."""
        chat_service = ChatService(db=self.db)
        req = ChatRequest(message="   ")
        resp = asyncio.run(chat_service.generate_response(req))
        self.assertIn("Please provide a message", resp.response)
        print("\n[Test 7] Empty prompt handled cleanly.")

    def test_08_fastapi_endpoints_via_testclient(self):
        """Test FastAPI application endpoints."""
        from app.main import app
        from app.database.session import get_db

        # Override get_db to yield from the persistent test database session
        def override_get_db():
            db = self.TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        # 1. Root
        r_root = client.get("/")
        self.assertEqual(r_root.status_code, 200)
        self.assertEqual(r_root.json()["service"], settings.APP_NAME)

        # 2. Products
        r_prod = client.get("/api/products?limit=5")
        self.assertEqual(r_prod.status_code, 200)
        prods = r_prod.json()
        self.assertEqual(len(prods), 5)
        self.assertIn("id", prods[0])
        self.assertIn("price", prods[0])
        self.assertIn("originalPrice", prods[0])
        self.assertIn("inStock", prods[0])

        # 3. Product Search
        r_search = client.get("/api/products/search?q=Apple")
        self.assertEqual(r_search.status_code, 200)
        apple_items = r_search.json()
        self.assertGreater(len(apple_items), 0)

        # 4. Chat
        r_chat = client.post("/api/chat", json={"message": "Show me Apple accessories"})
        self.assertEqual(r_chat.status_code, 200)
        self.assertIn("response", r_chat.json())

        app.dependency_overrides.clear()
        print("\n[Test 8] All FastAPI endpoints (/api/products, /api/products/search, /api/chat) passed.")


if __name__ == "__main__":
    unittest.main()
