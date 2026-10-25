"""Async database session management."""

import os
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from lam.infrastructure.config import settings


def normalize_database_url(url: str) -> str:
    """Normalizes connection strings for asyncpg compatibility across cloud providers."""
    if not url:
        return url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if "sslmode=true" in url:
        url = url.replace("sslmode=true", "ssl=require")
    elif "sslmode=false" in url:
        url = url.replace("sslmode=false", "sslmode=disable")
    return url


DATABASE_URL = normalize_database_url(
    os.getenv(
        "DATABASE_URL",
        settings.database_url,
    )
)


def create_engine_for_url(url: str) -> AsyncEngine:
    """Creates a configured AsyncEngine with pool pre-ping and tuning."""
    engine_kwargs: dict[str, Any] = {
        "echo": False,
        "future": True,
        "pool_pre_ping": True,
    }
    if "postgresql" in url:
        engine_kwargs.update(
            {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_recycle": settings.db_pool_recycle,
            }
        )
    return create_async_engine(url, **engine_kwargs)


engine: AsyncEngine = create_engine_for_url(DATABASE_URL)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an isolated async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def verify_db_connection(target_engine: AsyncEngine = engine) -> bool:
    """Verifies database connectivity without mutating schema.

    Schema lifecycle is managed strictly and exclusively through Alembic migrations.
    """
    async with target_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
