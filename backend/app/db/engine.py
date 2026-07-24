"""Database engine and session management."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401  # Register every model before DEV_MODE create_all.
from app.config import settings
from app.db.base import Base
from app.db.seed import seed_warehouse_reference_data

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEV_MODE)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Bootstrap tables automatically only for local development."""
    if not settings.DEV_MODE:
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        await seed_warehouse_reference_data(session)
        await session.commit()


async def get_db() -> AsyncSession:
    """Dependency that provides a database session."""
    async with async_session() as session:
        yield session
