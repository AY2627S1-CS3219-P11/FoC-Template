from unittest.mock import AsyncMock
from uuid import UUID

import pytest

import main


SUPPLIER = {
    "name": "Test Cafe", "category": "Food", "building": "COM1", "floor": 1,
    "description": "Near the entrance", "lattitude": 1.2966, "longitude": 103.7764,
    "startingTime": "09:00:00", "closingTime": "17:00:00",
}


@pytest.mark.anyio
async def test_health(client):
    assert (await client.get("/health")).json() == {"status": "healthy", "service": "supplier-service"}


@pytest.mark.anyio
async def test_database_errors_are_not_disclosed(client, caplog):
    session = AsyncMock()
    session.scalars.side_effect = RuntimeError("database-host private-query-value")
    main.app.dependency_overrides[main.get_session] = lambda: session
    response = await client.get("/suppliers")
    assert response.status_code == 500
    assert response.json() == {"detail": "Could not list suppliers"}
    assert "database-host" not in response.text
    assert "Could not list suppliers" in caplog.text


@pytest.mark.anyio
async def test_supplier_crud(client):
    created = await client.post("/suppliers", json=SUPPLIER)
    assert created.status_code == 201
    supplier = created.json()
    assert supplier["name"] == "Test Cafe"
    assert supplier["imageUrl"] is None
    path = f"/suppliers/{supplier['id']}"
    updated = await client.patch(path, json={"name": "Renamed Cafe", "floor": 2})
    assert updated.status_code == 200
    assert updated.json()["building"] == "COM1"
    assert updated.json()["name"] == "Renamed Cafe"
    assert (await client.get("/suppliers")).json()[0]["id"] == supplier["id"]
    assert (await client.delete(path)).status_code == 204
    assert (await client.get("/suppliers")).json() == []


@pytest.mark.anyio
async def test_patch_unknown_supplier_returns_404(client):
    assert (await client.patch(f"/suppliers/{UUID(int=0)}", json={"name": "missing"})).status_code == 404


@pytest.mark.anyio
@pytest.mark.parametrize("role,expected", [("user", 403), ("admin", 201), ("admin_manager", 201)])
async def test_write_permissions(client, role, expected):
    main.app.dependency_overrides[main.get_user] = lambda: main.AuthenticatedUser(user_id=UUID(int=1), role=role)
    assert (await client.post("/suppliers", json=SUPPLIER)).status_code == expected


@pytest.mark.anyio
async def test_missing_broker_configuration_fails_at_startup(monkeypatch):
    monkeypatch.setattr(main, "get_keycloak_validator", lambda: None)
    monkeypatch.delenv("RABBITMQ_URL", raising=False)
    monkeypatch.setattr(main, "get_engine", lambda: pytest.fail("Database accessed"))
    with pytest.raises(RuntimeError, match="RABBITMQ_URL must be set"):
        async with main.lifespan(main.app):
            pytest.fail("Service started without broker configuration")
