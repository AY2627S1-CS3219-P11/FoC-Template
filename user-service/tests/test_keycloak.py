from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from auth.tokens import ApplicationRoleRequiredError, AuthenticationUnavailableError, Identity
from auth.exceptions import UserNotFoundError
from auth.models import CurrentUserResponse
from jwt import InvalidTokenError

from auth import dependencies, service, views


SUBJECT = UUID("a0000000-0000-0000-0000-000000000007")


@pytest.fixture
def keycloak(monkeypatch):
    validator = Mock()
    validator.validate.return_value = Identity(user_id=SUBJECT, role="user")
    monkeypatch.setattr(dependencies, "get_keycloak_validator", lambda: validator)
    return validator


@pytest.fixture
def admin(monkeypatch):
    admin = AsyncMock()
    admin.get_user.return_value = CurrentUserResponse(username="test-user", email="user@example.com")
    admin.accounts.return_value = []
    monkeypatch.setattr(service, "get_keycloak_admin", lambda: admin)
    monkeypatch.setattr(views, "get_keycloak_admin", lambda: admin)
    return admin


@pytest.mark.anyio
async def test_keycloak_verification_is_local_and_profile_uses_keycloak(client, keycloak, admin):
    client.headers["Authorization"] = "Bearer keycloak-token"
    response = await client.get("/authentication/sessions/current")
    assert response.status_code == 200
    assert response.json() == {"user_id": str(SUBJECT), "role": "user"}
    admin.get_user.assert_not_awaited()
    response = await client.get("/authentication/users/current")
    assert response.status_code == 200
    assert response.json() == {"username": "test-user", "email": "user@example.com"}
    admin.get_user.assert_awaited_once_with(SUBJECT)


@pytest.mark.anyio
async def test_deleted_identity_profile_returns_not_found(client, keycloak, admin):
    admin.get_user.side_effect = UserNotFoundError("Account not found.")
    response = await client.get("/authentication/users/current", headers={"Authorization": "Bearer token"})
    assert response.status_code == 404
    # Bounded revocation: the signed token remains valid until expiry.
    assert (await client.get("/authentication/sessions/current", headers={"Authorization": "Bearer token"})).status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize("error,expected", [
    (InvalidTokenError(), 401), (ApplicationRoleRequiredError(), 403),
    (AuthenticationUnavailableError(), 503),
])
async def test_keycloak_failure_statuses(client, keycloak, error, expected):
    keycloak.validate.side_effect = error
    response = await client.get("/authentication/sessions/current", headers={"Authorization": "Bearer token"})
    assert response.status_code == expected


@pytest.mark.anyio
async def test_missing_token_does_not_validate(client, keycloak):
    response = await client.get("/authentication/sessions/current")
    assert response.status_code == 401
    keycloak.validate.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("role,expected", [("user", 403), ("admin", 403), ("admin_manager", 200)])
async def test_admin_manager_boundary(client, keycloak, admin, role, expected):
    keycloak.validate.return_value = Identity(user_id=SUBJECT, role=role)
    response = await client.get("/authentication/users", headers={"Authorization": "Bearer token"})
    assert response.status_code == expected
    if expected == 403:
        admin.accounts.assert_not_awaited()


@pytest.mark.anyio
async def test_swagger_bearer_and_cors_preflight(client):
    schema = (await client.get("/openapi.json")).json()
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    response = await client.options("/authentication/users/current", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization",
    })
    assert response.status_code == 200
