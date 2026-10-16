import os

os.environ.setdefault("INITIAL_ADMIN_EMAIL", "tests@example.com")

import pytest
from httpx import ASGITransport, AsyncClient

import main


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as http:
        yield http
