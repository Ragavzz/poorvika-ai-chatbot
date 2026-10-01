"""Main entry point for ShopAI FastAPI application.

Provides REST APIs for:
- Product Catalog & Search (/api/products)
- AI Shopping Assistant Chatbot (/api/chat)
- Service & Database Health (/api/health)
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import health_router, products_router, chat_router
from app.database import session as database_session
from app.database.base import Base
from app.database.ingest import run_dataset_ingestion
from app.models.product import Product

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("shopai.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle startup and shutdown hooks."""
    logger.info(f"Starting {settings.APP_NAME}...")
    is_connected, msg = database_session.check_db_connection(force=True)
    if is_connected:
        logger.info(f"PostgreSQL connection verified: {msg}")
        try:
            # Check if dataset needs initial ingestion
            with database_session.SessionLocal() as db:
                count = db.query(Product).count()
                if count == 0:
                    logger.info("Products table is empty. Ingesting dataset from JSONL...")
                    run_dataset_ingestion()
                else:
                    logger.info(f"PostgreSQL catalog already contains {count} products.")
        except Exception as e:
            logger.warning(f"Startup table verification note: {e}")
    else:
        logger.warning(
            f"PostgreSQL is currently not reachable at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}. "
            f"Details: {msg}. Ensure PostgreSQL service is running."
        )

    yield
    logger.info(f"Shutting down {settings.APP_NAME}.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Poorvika ShopAI powered by FastAPI, Laya decisions, the product catalog, and local Ollama",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware allowing the Vite React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(health_router)
app.include_router(products_router)
app.include_router(chat_router)
