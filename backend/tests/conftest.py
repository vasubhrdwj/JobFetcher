import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_vjob.db"

import asyncio
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.models import Base


@pytest_asyncio.fixture
async def db():
    eng = create_async_engine("sqlite+aiosqlite:///./test_vjob.db", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()