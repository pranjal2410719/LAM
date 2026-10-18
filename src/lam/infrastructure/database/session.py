"""Async database session management."""

import os
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from lam.infrastructure.config import settings

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    settings.database_url,
)

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

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
