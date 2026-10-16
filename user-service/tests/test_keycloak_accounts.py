from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from auth import service
from auth.tokens import Identity
from test_keycloak import SUBJECT, keycloak


@pytest.fixture
def admin(monkeypatch, keycloak):
    admin = AsyncMock()
    admin.create_user.return_value = UUID(int=100)
    monkeypatch.setattr(service, "get_keycloak_admin", lambda: admin)
    return admin


@pytest.mark.anyio
async def test_signup_uses_keycloak(client, admin):
    response = await client.post("/authentication/users", json={
        "username": "new-user", "email": "new@example.com", "password": "Password123",
    })
    assert response.status_code == 201
    admin.create_user.assert_awaited_once_with("new-user", "new@example.com", "Password123")


@pytest.mark.anyio
async def test_password_login_and_api_logout_are_removed(client):
    assert (await client.post("/authentication/sessions", json={})).status_code == 404
    assert (await client.delete("/authentication/sessions/current")).status_code == 405


@pytest.mark.anyio
async def test_cookie_is_not_an_authentication_method(client, keycloak):
    client.cookies.set("access_token", "old-token")
    assert (await client.get("/authentication/sessions/current")).status_code == 401
    keycloak.validate.assert_not_called()


@pytest.mark.anyio
async def test_role_change_uses_keycloak(client, admin, keycloak):
    keycloak.validate.return_value = Identity(user_id=SUBJECT, role="admin_manager")
    response = await client.patch(f"/authentication/users/{SUBJECT}/role",
        headers={"Authorization": "Bearer token"}, json={"role": "admin"})
    assert response.status_code == 200
    admin.set_role.assert_awaited_once_with(SUBJECT, "admin")
