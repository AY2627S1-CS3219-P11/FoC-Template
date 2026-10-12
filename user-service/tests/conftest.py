import os

# The example's blank bootstrap email is invalid even when startup is skipped.
os.environ.setdefault("INITIAL_ADMIN_EMAIL", "tests@example.com")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import main
from common.db import get_session
from auth.orm_models import Base, User


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def session_override():
        async with factory() as session:
            yield session

    main.app.dependency_overrides[get_session] = session_override
    async with factory() as session:
        from uuid import UUID
        session.add(User(user_id=UUID("a0000000-0000-0000-0000-000000000007"), username="test-user", user_email="user@example.com", password_hash="unused", user_role="user"))
        await session.commit()
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as http:
        yield http
    main.app.dependency_overrides.clear()
    await engine.dispose()
