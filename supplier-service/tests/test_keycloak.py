from unittest.mock import Mock
from uuid import UUID

import pytest
from auth.tokens import ApplicationRoleRequiredError, AuthenticationUnavailableError, Identity
from jwt import InvalidTokenError
from sqlalchemy import select

import main
from auth import dependencies
from test_main import SUPPLIER


SUBJECT = UUID(int=7)


@pytest.fixture
def keycloak(monkeypatch):
    validator = Mock()
    validator.validate.return_value = Identity(user_id=SUBJECT, role="admin")
    monkeypatch.setattr(dependencies, "get_keycloak_validator", lambda: validator)
    return validator


@pytest.mark.anyio
async def test_supplier_crud_uses_signed_subject(client, keycloak):
    main.app.dependency_overrides.pop(main.get_user)
    client.headers["Authorization"] = "Bearer token"
    created = await client.post("/suppliers", json=SUPPLIER)
    assert created.status_code == 201
    supplier_id = created.json()["id"]
    assert (await client.patch(f"/suppliers/{supplier_id}", json={"name": "Updated"})).status_code == 200
    assert (await client.delete(f"/suppliers/{supplier_id}")).status_code == 204
    async for session in main.get_session():
        supplier = await session.scalar(select(main.Supplier).where(main.Supplier.id == UUID(supplier_id)))
        assert supplier.created_by == supplier.updated_by == supplier.deleted_by == SUBJECT
    assert keycloak.validate.call_count == 3


@pytest.mark.anyio
@pytest.mark.parametrize("error,expected", [
    (InvalidTokenError(), 401), (ApplicationRoleRequiredError(), 403), (AuthenticationUnavailableError(), 503),
])
async def test_validation_failures(client, keycloak, error, expected):
    main.app.dependency_overrides.pop(main.get_user)
    keycloak.validate.side_effect = error
    response = await client.post("/suppliers", json=SUPPLIER, headers={"Authorization": "Bearer invalid"})
    assert response.status_code == expected


@pytest.mark.anyio
async def test_cookie_is_not_accepted(client, keycloak):
    main.app.dependency_overrides.pop(main.get_user)
    client.cookies.set("access_token", "old-cookie")
    assert (await client.post("/suppliers", json=SUPPLIER)).status_code == 401
    keycloak.validate.assert_not_called()
