import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

import main


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(monkeypatch):
    """An async client backed by a fresh in-memory database for one test."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(main, "get_engine", lambda: engine)

    async with engine.begin() as connection:
        await connection.run_sync(main.Base.metadata.create_all)

    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    main.app.dependency_overrides.clear()
    async with engine.begin() as connection:
        await connection.run_sync(main.Base.metadata.drop_all)
    await engine.dispose()
