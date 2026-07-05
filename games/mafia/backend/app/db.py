from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for persistent (SQLite) ORM models — users, profiles, match
    history, saved configs. Active game state never uses this; it lives in the
    in-memory stores under app/platform/stores instead.
    """


async def init_db() -> None:
    """Create tables from Base.metadata. Fine for development; a real
    migration tool (Alembic) is a future improvement once the schema needs
    to evolve without dropping data.
    """
    from app import models  # noqa: F401  imported here (not at module scope)
    # to register all model classes on Base.metadata without creating a
    # circular import (each model module imports Base from this file).

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
