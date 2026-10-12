import httpx
import pytest

from auth.exceptions import AuthenticationUnavailableError, UserAlreadyExistsError
from auth.keycloak import KeycloakAdmin
from test_keycloak import SUBJECT


@pytest.fixture
def transport(monkeypatch):
    calls = []
    state = {"status": 200}

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "service-token", "expires_in": 60})
        assert request.headers["Authorization"] == "Bearer service-token"
        if state["status"] != 200:
            return httpx.Response(state["status"])
        if request.url.path.endswith("/roles/user"):
            return httpx.Response(200, json={"id": "user-role", "name": "user"})
        if request.method == "GET":
            return httpx.Response(200, json=[{"name": "admin", "id": "admin-role"}, {"name": "default-roles-foc"}])
        return httpx.Response(201, headers={"Location": f"http://keycloak/admin/realms/foc/users/{SUBJECT}"})

    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    return KeycloakAdmin("http://keycloak", "foc", "foc-backend", "server-secret"), calls, state


@pytest.mark.anyio
async def test_account_creation_and_role_mapping_preserve_builtin_roles(transport):
    admin, calls, _ = transport
    assert await admin.create_user("test-user", "test@example.com", "Password123") == SUBJECT
    assert len([r for r in calls if r.url.path.endswith("/token")]) == 1
    import json
    removed = [json.loads(r.content) for r in calls if r.method == "DELETE"]
    assert removed == [[{"name": "admin", "id": "admin-role"}]]


@pytest.mark.anyio
@pytest.mark.parametrize("status,error", [(409, UserAlreadyExistsError), (503, AuthenticationUnavailableError)])
async def test_account_administration_maps_errors(transport, status, error):
    admin, _, state = transport
    state["status"] = status
    with pytest.raises(error):
        await admin.create_user("test-user", "test@example.com", "Password123")


@pytest.mark.anyio
async def test_deleting_already_removed_account_is_idempotent(transport):
    admin, _, state = transport
    state["status"] = 404
    await admin.delete_user(SUBJECT)
