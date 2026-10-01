"""API Routes package."""

from app.routes.health import health_router
from app.routes.products import products_router
from app.routes.chat import chat_router

__all__ = ["health_router", "products_router", "chat_router"]
