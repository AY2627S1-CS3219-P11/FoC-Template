import json
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import SecretStr

from auth import bootstrap
from auth.exceptions import AuthenticationUnavailableError, UserAlreadyExistsError, UserNotFoundError
from auth.keycloak import KeycloakAdmin
from common.config_manager import settings
from test_keycloak import SUBJECT


@pytest.fixture
def transport(monkeypatch):
    calls = []
    state = {"status": 200, "roles": [{"name": "user", "id": "user-role"}], "inherited": []}

    def handler(request):
        calls.append(request)
        path = request.url.path
        if path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "service-token", "expires_in": 60})
        assert request.headers["Authorization"] == "Bearer service-token"
        if state["status"] != 200:
            return httpx.Response(state["status"])
        if "/roles/" in path:
            role = path.rsplit("/", 1)[1]
            return httpx.Response(200, json={"id": f"{role}-role", "name": role})
        if path.endswith("/role-mappings/realm/composite"):
            return httpx.Response(200, json=state["roles"] + state["inherited"])
        if path.endswith("/role-mappings/realm"):
            if request.method == "GET":
                return httpx.Response(200, json=state["roles"])
            roles = json.loads(request.content)
            if request.method == "POST":
                state["roles"] += [r for r in roles if r not in state["roles"]]
            else:
                state["roles"] = [r for r in state["roles"] if r not in roles]
            return httpx.Response(204)
        if request.method == "GET":
            return httpx.Response(200, json={"id": str(SUBJECT), "username": "test-user", "email": "user@example.com"})
        return httpx.Response(201, headers={"Location": f"http://keycloak/admin/realms/foc/users/{SUBJECT}"})

    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    return KeycloakAdmin("http://keycloak", "foc", "foc-backend", "server-secret"), calls, state


@pytest.mark.anyio
async def test_role_mapping_preserves_builtin_roles_and_does_not_logout(transport):
    admin, calls, state = transport
    state["roles"].append({"id": "built-in", "name": "offline_access"})
    assert (await admin.set_managed_role(SUBJECT, "admin")).role == "admin"
    removed = [json.loads(r.content) for r in calls if r.method == "DELETE"]
    assert removed == [[{"name": "user", "id": "user-role"}]]
    assert {r["name"] for r in state["roles"]} == {"offline_access", "admin"}
    assert len([r for r in calls if r.url.path.endswith("/token")]) == 1
    assert not any(r.url.path.endswith("/logout") for r in calls)


@pytest.mark.anyio
@pytest.mark.parametrize("inherited", [False, True])
async def test_manager_target_is_protected_without_writes(transport, inherited):
    admin, calls, state = transport
    state["inherited" if inherited else "roles"].append({"name": "admin_manager", "id": "manager"})
    with pytest.raises(UserNotFoundError):
        await admin.set_managed_role(SUBJECT, "user")
    assert not any(r.method in {"PUT", "DELETE"} or
        (r.method == "POST" and not r.url.path.endswith("/token")) for r in calls)


@pytest.mark.anyio
async def test_inherited_administrator_access_is_not_silently_demoted(transport):
    admin, calls, state = transport
    state["inherited"] = [{"name": "admin", "id": "admin-role"}]
    with pytest.raises(UserAlreadyExistsError):
        await admin.set_managed_role(SUBJECT, "user")
    assert not any(r.method == "DELETE" for r in calls)


@pytest.mark.anyio
@pytest.mark.parametrize("status,error", [
    (404, UserNotFoundError), (409, UserAlreadyExistsError), (503, AuthenticationUnavailableError),
])
async def test_account_administration_maps_errors(transport, status, error):
    admin, _, state = transport
    state["status"] = status
    with pytest.raises(error):
        await admin.get_user(SUBJECT)


@pytest.mark.anyio
async def test_bootstrap_enables_account_only_after_manager_role_is_assigned(transport):
    admin, calls, _ = transport
    await admin.bootstrap_manager("manager", "manager@example.com", "Password123")
    writes = [r for r in calls if r.method != "GET" and not r.url.path.endswith("/token")]
    assert json.loads(writes[0].content)["enabled"] is False
    assert json.loads(writes[1].content)[0]["name"] == "admin_manager"
    assert json.loads(writes[2].content) == {"enabled": True}


@pytest.mark.anyio
async def test_bootstrap_does_not_promote_existing_username_on_conflict(transport):
    admin, calls, state = transport
    state["status"] = 409
    with pytest.raises(UserAlreadyExistsError):
        await admin.bootstrap_manager("existing", "manager@example.com", "Password123")
    assert len([r for r in calls if not r.url.path.endswith("/token")]) == 1


@pytest.mark.anyio
async def test_bootstrap_skips_existing_manager(monkeypatch):
    admin = AsyncMock()
    admin.role_members.return_value = [{"id": str(SUBJECT)}]
    monkeypatch.setattr(bootstrap, "get_keycloak_admin", lambda: admin)
    await bootstrap.provision_admin_manager()
    admin.bootstrap_manager.assert_not_awaited()


@pytest.mark.anyio
async def test_bootstrap_uses_only_keycloak(monkeypatch):
    admin = AsyncMock()
    admin.role_members.return_value = []
    monkeypatch.setattr(bootstrap, "get_keycloak_admin", lambda: admin)
    monkeypatch.setattr(settings, "initial_admin_username", "manager")
    monkeypatch.setattr(settings, "initial_admin_email", "manager@example.com")
    monkeypatch.setattr(settings, "initial_admin_password", SecretStr("Password123"))
    await bootstrap.provision_admin_manager()
    admin.bootstrap_manager.assert_awaited_once_with("manager", "manager@example.com", "Password123")
