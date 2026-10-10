from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from foc_auth import ApplicationRoleRequiredError, AuthenticationUnavailableError, Identity
from jwt import InvalidTokenError

from auth import dependencies, service
from common.config_manager import settings


SUBJECT = UUID("a0000000-0000-0000-0000-000000000007")


@pytest.fixture
def keycloak(monkeypatch):
    monkeypatch.setattr(settings, "auth_provider", "keycloak")
    validator = Mock()
    validator.validate.return_value = Identity(user_id=SUBJECT, role="user")
    monkeypatch.setattr(dependencies, "get_keycloak_validator", lambda: validator)
    monkeypatch.setattr(dependencies, "verify_access_token", lambda *_a: pytest.fail("Legacy verification used"))
    monkeypatch.setattr(dependencies, "get_authenticated_user_role", lambda *_a: pytest.fail("Legacy session queried"))
    monkeypatch.setattr(service, "get_keycloak_admin", lambda: AsyncMock())
    return validator


@pytest.mark.anyio
async def test_keycloak_session_profile_and_update(client, keycloak):
    client.headers["Authorization"] = "Bearer keycloak-token"
    response = await client.get("/authentication/sessions/current")
    assert response.status_code == 200
    assert response.json() == {"user_id": str(SUBJECT), "role": "user"}
    response = await client.get("/authentication/users/current")
    assert response.status_code == 200
    assert response.json() == {"username": "test-user", "email": "user@example.com"}
    response = await client.patch("/authentication/users/current", json={"username": "changed-user"})
    assert response.status_code == 200
    assert response.json()["username"] == "changed-user"


@pytest.mark.anyio
async def test_unmapped_subject_is_not_linked_or_created(client, keycloak):
    keycloak.validate.return_value = Identity(user_id=UUID(int=999), role="user")
    response = await client.get("/authentication/users/current", headers={"Authorization": "Bearer token"})
    assert response.status_code == 401


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
async def test_admin_manager_boundary(client, keycloak, role, expected):
    keycloak.validate.return_value = Identity(user_id=SUBJECT, role=role)
    response = await client.get("/authentication/users", headers={"Authorization": "Bearer token"})
    assert response.status_code == expected


@pytest.mark.anyio
async def test_swagger_bearer_and_cors_preflight(client, keycloak):
    schema = (await client.get("/openapi.json")).json()
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    response = await client.options("/authentication/users/current", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization",
    })
    assert response.status_code == 200
