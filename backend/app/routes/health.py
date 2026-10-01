"""Health check and service status routes."""

from fastapi import APIRouter
from app.config import settings
from app.database import session as database_session
from app.models.product import Product

health_router = APIRouter(tags=["Health"])


@health_router.get("/")
async def root():
    """Root verification endpoint."""
    return {
        "status": "online",
        "service": settings.APP_NAME,
        "framework": "FastAPI",
        "docs_url": "/docs",
    }


@health_router.get("/api/health")
async def health_check():
    """Reports database status and catalog counts."""
    db_connected, db_msg = database_session.check_db_connection(force=True)
    product_count = 0
    if db_connected:
        try:
            with database_session.SessionLocal() as db:
                product_count = db.query(Product).count()
        except Exception:
            pass

    return {
        "status": "healthy" if db_connected else "degraded",
        "service": settings.APP_NAME,
        "database": {
            "type": (
                "SQLite (isolated test database)" if settings.TESTING_MODE
                else "SQLite fallback" if "SQLite fallback" in db_msg
                else "PostgreSQL"
            ),
            "connected": db_connected,
            "details": db_msg,
            "product_count": product_count,
        },
    }
