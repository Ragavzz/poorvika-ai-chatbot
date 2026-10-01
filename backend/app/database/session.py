"""PostgreSQL-first SQLAlchemy sessions with a persistent SQLite fallback."""

import os
import time
import logging
from typing import Generator, Tuple

from fastapi import HTTPException, status
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings

logger = logging.getLogger("shopai.database")

connect_args = {"check_same_thread": False} if settings.TESTING_MODE else {"connect_timeout": 3}
engine = create_engine(settings.sqlalchemy_database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
_connection_cache = {"time": 0.0, "status": False, "msg": "Unchecked"}
_fallback_active = False


def _activate_sqlite_fallback() -> Tuple[bool, str]:
    """Use and initialize a persistent local catalog after PostgreSQL fails."""
    global engine, SessionLocal, _fallback_active
    if _fallback_active:
        return True, "SQLite fallback connected"
    try:
        from app.database.base import Base
        from app.database.ingest import ingest_products, load_dataset_records
        from app.models.product import Product

        sqlite_path = os.path.join(os.path.dirname(settings.DATASET_PATH), "poorvika_fallback.sqlite3")
        os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
        fallback_engine = create_engine(
            f"sqlite:///{sqlite_path}",
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
        fallback_sessions = sessionmaker(
            bind=fallback_engine, autocommit=False, autoflush=False, expire_on_commit=False
        )
        Base.metadata.create_all(bind=fallback_engine)
        with fallback_sessions() as db:
            if db.query(Product).count() == 0:
                records = load_dataset_records(settings.DATASET_PATH)
                if records:
                    ingest_products(db, records)
        engine, SessionLocal = fallback_engine, fallback_sessions
        _fallback_active = True
        logger.warning("Using SQLite catalog fallback at %s", sqlite_path)
        return True, f"SQLite fallback connected ({sqlite_path})"
    except Exception as exc:
        logger.exception("Could not initialize SQLite fallback")
        return False, f"PostgreSQL unavailable and SQLite fallback failed: {exc}"


def check_db_connection(force: bool = False) -> Tuple[bool, str]:
    """Check PostgreSQL first, then activate SQLite when PostgreSQL is unavailable."""
    global _connection_cache
    if settings.TESTING_MODE:
        return True, "SQLite isolated testing mode"
    if _fallback_active:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True, "SQLite fallback connected"
        except Exception as exc:
            return False, str(exc)

    now = time.time()
    cache_ttl = 30.0 if _connection_cache["status"] else 10.0
    if not force and now - _connection_cache["time"] < cache_ttl:
        return _connection_cache["status"], _connection_cache["msg"]
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar()
        _connection_cache = {"time": now, "status": True, "msg": "PostgreSQL connected successfully"}
        return True, _connection_cache["msg"]
    except Exception as exc:
        logger.warning("PostgreSQL connection failed; trying SQLite fallback: %s", exc)
        ok, message = _activate_sqlite_fallback()
        _connection_cache = {"time": now, "status": ok, "msg": message}
        return ok, message


def get_db() -> Generator[Session, None, None]:
    """Yield a PostgreSQL session or a SQLite catalog session when needed."""
    is_ok, err_msg = check_db_connection()
    if not is_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {err_msg}",
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
