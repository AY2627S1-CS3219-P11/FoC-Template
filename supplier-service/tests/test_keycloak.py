from unittest.mock import Mock
from uuid import UUID

import pytest
from foc_auth import ApplicationRoleRequiredError, AuthenticationUnavailableError, Identity
from jwt import InvalidTokenError
from sqlalchemy import select

import main
from auth import dependencies
from test_main import SUPPLIER


SUBJECT = UUID("00000000-0000-0000-0000-000000000007")


@pytest.fixture
def keycloak(monkeypatch):
    monkeypatch.setenv("AUTH_PROVIDER", "keycloak")
    monkeypatch.delenv("INTERNAL_GATEWAY_URL", raising=False)
    validator = Mock()
    validator.validate.return_value = Identity(user_id=SUBJECT, role="admin")
    monkeypatch.setattr(dependencies, "get_keycloak_validator", lambda: validator)
    return validator


@pytest.mark.anyio
@pytest.mark.parametrize("via_cookie", [False, True])
async def test_keycloak_supplier_crud_without_gateway(client, keycloak, monkeypatch, via_cookie):
    main.app.dependency_overrides.pop(main.get_user)
    monkeypatch.delenv("INTERNAL_GATEWAY_URL", raising=False)
    monkeypatch.setattr(dependencies.httpx, "AsyncClient", lambda *_a, **_k: pytest.fail("Legacy HTTP client created"))
    if via_cookie:
        client.cookies.set("access_token", "keycloak-token")
    else:
        client.headers["Authorization"] = "Bearer keycloak-token"
    created = await client.post("/suppliers", json=SUPPLIER)
    assert created.status_code == 201
    supplier_id = created.json()["id"]
    assert (await client.patch(f"/suppliers/{supplier_id}", json={"name": "Updated"})).status_code == 200
    assert (await client.delete(f"/suppliers/{supplier_id}")).status_code == 204
    assert (await client.get("/suppliers")).json() == []
    async for session in main.get_session():
        supplier = await session.scalar(select(main.Supplier).where(main.Supplier.id == UUID(supplier_id)))
        assert supplier.created_by == supplier.updated_by == supplier.deleted_by == SUBJECT
    assert keycloak.validate.call_count == 3


@pytest.mark.anyio
@pytest.mark.parametrize("error,expected", [
    (InvalidTokenError(), 401),
    (ApplicationRoleRequiredError(), 403),
    (AuthenticationUnavailableError(), 503),
])
async def test_validation_failures_never_fall_back(client, keycloak, monkeypatch, error, expected):
    main.app.dependency_overrides.pop(main.get_user)
    monkeypatch.delenv("INTERNAL_GATEWAY_URL", raising=False)
    monkeypatch.setattr(dependencies.httpx, "AsyncClient", lambda *_a, **_k: pytest.fail("Legacy fallback"))
    keycloak.validate.side_effect = error
    response = await client.post("/suppliers", json=SUPPLIER, headers={"Authorization": "Bearer invalid"})
    assert response.status_code == expected


@pytest.mark.anyio
async def test_regular_keycloak_user_cannot_write(client, keycloak):
    main.app.dependency_overrides.pop(main.get_user)
    keycloak.validate.return_value = Identity(user_id=SUBJECT, role="user")
    response = await client.post("/suppliers", json=SUPPLIER, headers={"Authorization": "Bearer user-token"})
    assert response.status_code == 403


@pytest.mark.anyio
async def test_bearer_takes_precedence_over_cookie(client, keycloak):
    main.app.dependency_overrides.pop(main.get_user)
    client.cookies.set("access_token", "old-cookie")
    response = await client.post("/suppliers", json=SUPPLIER, headers={"Authorization": "Bearer current-token"})
    assert response.status_code == 201
    keycloak.validate.assert_called_once_with("current-token")
