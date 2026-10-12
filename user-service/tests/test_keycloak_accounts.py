from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from auth import service, views
from auth.exceptions import AuthenticationUnavailableError, UserAlreadyExistsError
from auth.models import UserRecord, UserRole
from auth.export_keycloak_users import build_import
from foc_auth import Identity

from test_keycloak import SUBJECT, keycloak

NEW_SUBJECT = UUID("a0000000-0000-0000-0000-000000000100")


@pytest.fixture
def admin(monkeypatch, keycloak):
    admin = AsyncMock()
    admin.create_user.return_value = NEW_SUBJECT
    monkeypatch.setattr(service, "get_keycloak_admin", lambda: admin)
    monkeypatch.setattr(views, "get_keycloak_admin", lambda: admin)
    return admin


SIGNUP = {"username": "new-user", "email": "new@example.com", "password": "Password123"}


@pytest.mark.anyio
async def test_signup_uses_keycloak_uuid_and_omits_local_password(client, admin, monkeypatch):
    response = await client.post("/authentication/users", json=SIGNUP)
    assert response.status_code == 201
    admin.create_user.assert_awaited_once_with("new-user", "new@example.com", "Password123")
    admin.delete_user.assert_not_awaited()
    from common.db import get_session
    import main
    from auth.repository import find_user_by_email
    async for session in main.app.dependency_overrides[get_session]():
        user = await find_user_by_email(session, "new@example.com")
        assert user.id == NEW_SUBJECT
        assert user.hashed_password == ""


@pytest.mark.anyio
async def test_signup_database_failure_removes_keycloak_account(client, admin, monkeypatch):
    monkeypatch.setattr(service, "create_user", AsyncMock(side_effect=UserAlreadyExistsError("Conflict")))
    response = await client.post("/authentication/users", json=SIGNUP)
    assert response.status_code == 409
    admin.delete_user.assert_awaited_once_with(NEW_SUBJECT)


@pytest.mark.anyio
async def test_signup_validation_and_duplicates_do_not_create_accounts(client, admin):
    assert (await client.post("/authentication/users", json=SIGNUP | {"password": "weak"})).status_code == 422
    assert (await client.post("/authentication/users", json=SIGNUP | {"email": "user@example.com"})).status_code == 409
    admin.create_user.assert_not_awaited()


@pytest.mark.anyio
async def test_administration_outage_returns_503(client, admin):
    admin.create_user.side_effect = AuthenticationUnavailableError()
    assert (await client.post("/authentication/users", json=SIGNUP)).status_code == 503


@pytest.mark.anyio
async def test_legacy_login_is_disabled_in_keycloak_mode(client, admin):
    response = await client.post("/authentication/sessions", json={"email": "user@example.com", "password": "unused"})
    assert response.status_code == 409
    assert "set-cookie" not in response.headers


@pytest.mark.anyio
async def test_profile_update_and_database_failure_restore_identity(client, admin, monkeypatch):
    client.headers["Authorization"] = "Bearer token"
    response = await client.patch("/authentication/users/current", json={"email": "new@example.com"})
    assert response.status_code == 200
    admin.update_profile.assert_awaited_once_with(SUBJECT, "test-user", "new@example.com")
    admin.update_profile.reset_mock()
    monkeypatch.setattr(service, "update_user_profile", AsyncMock(side_effect=UserAlreadyExistsError("Conflict")))
    response = await client.patch("/authentication/users/current", json={"username": "new-name"})
    assert response.status_code == 409
    assert [call.args for call in admin.update_profile.await_args_list] == [
        (SUBJECT, "new-name", "new@example.com"), (SUBJECT, "test-user", "new@example.com"),
    ]


@pytest.mark.anyio
async def test_role_change_syncs_and_revokes_sessions(client, admin, keycloak):
    keycloak.validate.return_value = Identity(user_id=SUBJECT, role="admin_manager")
    response = await client.patch(f"/authentication/users/{SUBJECT}/role",
        headers={"Authorization": "Bearer token"}, json={"role": "admin"})
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    admin.set_role.assert_awaited_once_with(SUBJECT, UserRole.ADMIN)
    admin.logout_user.assert_awaited_once_with(SUBJECT)


@pytest.mark.anyio
async def test_role_change_failure_restores_identity(client, admin, keycloak, monkeypatch):
    keycloak.validate.return_value = Identity(user_id=SUBJECT, role="admin_manager")
    monkeypatch.setattr(service, "update_managed_user_role", AsyncMock(side_effect=AuthenticationUnavailableError()))
    response = await client.patch(f"/authentication/users/{SUBJECT}/role",
        headers={"Authorization": "Bearer token"}, json={"role": "admin"})
    assert response.status_code == 503
    assert [call.args for call in admin.set_role.await_args_list] == [(SUBJECT, UserRole.ADMIN), (SUBJECT, UserRole.USER)]
    assert admin.logout_user.await_count == 2


@pytest.mark.anyio
async def test_session_revocation_failure_restores_role(client, admin, keycloak):
    keycloak.validate.return_value = Identity(user_id=SUBJECT, role="admin_manager")
    admin.logout_user.side_effect = [AuthenticationUnavailableError(), None]
    response = await client.patch(f"/authentication/users/{SUBJECT}/role",
        headers={"Authorization": "Bearer token"}, json={"role": "admin"})
    assert response.status_code == 503
    assert [call.args for call in admin.set_role.await_args_list] == [(SUBJECT, UserRole.ADMIN), (SUBJECT, UserRole.USER)]


@pytest.mark.anyio
async def test_logout_revokes_only_presented_session(client, admin, keycloak, monkeypatch):
    monkeypatch.setattr(views, "get_keycloak_validator", lambda: keycloak)
    keycloak.validate.return_value = Identity(user_id=SUBJECT, role="user", session_id="session-123")
    response = await client.delete("/authentication/sessions/current", headers={"Authorization": "Bearer token"})
    assert response.status_code == 204
    admin.logout_session.assert_awaited_once_with("session-123")
    admin.logout_user.assert_not_awaited()


def test_import_preserves_uuid_roles_and_requires_password_reset():
    user = UserRecord(id=SUBJECT, username="legacy-user", email="legacy@example.com",
        hashed_password="legacy-bcrypt-hash", user_role=UserRole.ADMIN)
    realm, passwords = build_import([user])
    exported = realm["users"][0]
    assert realm["ifResourceExists"] == "FAIL"
    assert exported["id"] == str(SUBJECT)
    assert exported["realmRoles"] == ["admin"]
    assert exported["requiredActions"] == ["UPDATE_PASSWORD"]
    assert exported["credentials"][0]["temporary"] is True
    assert exported["credentials"][0]["value"] == passwords[0]["temporary_password"]
    assert "legacy-bcrypt-hash" not in str(realm)
