import pytest

from auth.exceptions import UserNotFoundError
from auth.models import ManagedUserResponse
from auth.tokens import Identity
from test_keycloak import SUBJECT, admin, keycloak


@pytest.mark.anyio
async def test_password_and_profile_write_endpoints_are_removed(client):
    assert (await client.post("/authentication/sessions", json={})).status_code == 404
    assert (await client.delete("/authentication/sessions/current")).status_code == 405
    assert (await client.post("/authentication/users", json={})).status_code == 405
    assert (await client.patch("/authentication/users/current", json={})).status_code == 405


@pytest.mark.anyio
async def test_cookie_is_not_an_authentication_method(client, keycloak):
    client.cookies.set("access_token", "old-token")
    assert (await client.get("/authentication/sessions/current")).status_code == 401
    keycloak.validate.assert_not_called()


@pytest.mark.anyio
async def test_role_change_uses_narrow_keycloak_method(client, admin, keycloak):
    keycloak.validate.return_value = Identity(user_id=SUBJECT, role="admin_manager")
    admin.set_managed_role.return_value = ManagedUserResponse(
        user_id=SUBJECT, username="test-user", email="user@example.com", role="admin")
    response = await client.patch(f"/authentication/users/{SUBJECT}/role",
        headers={"Authorization": "Bearer token"}, json={"role": "admin"})
    assert response.status_code == 200
    admin.set_managed_role.assert_awaited_once_with(SUBJECT, "admin")


@pytest.mark.anyio
async def test_manager_promotion_is_not_an_application_capability(client, admin, keycloak):
    keycloak.validate.return_value = Identity(user_id=SUBJECT, role="admin_manager")
    response = await client.patch(f"/authentication/users/{SUBJECT}/role",
        headers={"Authorization": "Bearer token"}, json={"role": "admin_manager"})
    assert response.status_code == 422
    admin.set_managed_role.assert_not_awaited()


@pytest.mark.anyio
async def test_manager_listing_filters_protected_accounts_and_passes_pagination(client, admin, keycloak):
    keycloak.validate.return_value = Identity(user_id=SUBJECT, role="admin_manager")
    admin.accounts.return_value = [{"id": str(SUBJECT)}]
    admin.managed_user.side_effect = UserNotFoundError("Protected account")
    response = await client.get("/authentication/users?offset=100&limit=10",
        headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json() == {"items": [], "offset": 100, "limit": 10, "has_more": False}
    admin.accounts.assert_awaited_once_with(first=100, max_results=11)


@pytest.mark.anyio
async def test_filtered_empty_page_still_has_next_page(client, admin, keycloak):
    keycloak.validate.return_value = Identity(user_id=SUBJECT, role="admin_manager")
    admin.accounts.return_value = [{"id": str(SUBJECT)}] * 3
    admin.managed_user.return_value = ManagedUserResponse(
        user_id=SUBJECT, username="test-user", email="user@example.com", role="user")
    response = await client.get("/authentication/users?role=user&query=missing&limit=2",
        headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json() == {"items": [], "offset": 0, "limit": 2, "has_more": True}
    assert admin.managed_user.await_count == 2


@pytest.mark.anyio
@pytest.mark.parametrize("params", ["offset=-1", "limit=0", "limit=101"])
async def test_invalid_page_bounds(client, keycloak, params):
    keycloak.validate.return_value = Identity(user_id=SUBJECT, role="admin_manager")
    response = await client.get(f"/authentication/users?{params}",
        headers={"Authorization": "Bearer token"})
    assert response.status_code == 422
