"""Realm configuration contract without a running identity server."""

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("configure", ROOT / "configure.py")
configure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure)


def test_registration_defaults_and_self_service_permissions():
    realm = json.loads((ROOT / "realms/foc-realm.json").read_text())
    assert realm["registrationAllowed"] is True
    assert realm["duplicateEmailsAllowed"] is False
    assert realm["accessTokenLifespan"] == 300
    default = next(role for role in realm["roles"]["realm"]
                   if role["name"] == realm["defaultRole"]["name"])
    assert default["composites"] == {"realm": ["user"]}
    profile = json.loads(realm["components"]["org.keycloak.userprofile.UserProfileProvider"]
                         [0]["config"]["kc.user.profile.config"][0])
    for attribute in profile["attributes"]:
        assert "user" in attribute["permissions"]["edit"]
    clients = {client["clientId"]: client for client in realm["clients"]}
    assert clients["foc-ui"]["publicClient"] is True
    assert clients["foc-ui"]["directAccessGrantsEnabled"] is False
    assert clients["foc-api"]["bearerOnly"] is True
    assert "secret" not in clients["foc-api"]


def test_existing_realm_receives_registration_and_default_role(monkeypatch):
    calls = []

    class Response:
        def __init__(self, data):
            self.data = data

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def read(self):
            return json.dumps(self.data).encode()

    def request(req, timeout):
        path = req.full_url.removeprefix("http://identity")
        data = json.loads(req.data) if req.data and req.get_header("Content-type") == "application/json" else None
        calls.append((req.method, path, data))
        if path.endswith("/token"):
            return Response({"access_token": "admin-token"})
        if "/clients?" in path:
            return Response([{"id": "client-id"}])
        if path.endswith("/service-account-user"):
            return Response({"id": "service-account"})
        if path.endswith("/roles"):
            return Response([{"id": "manage-users", "name": "manage-users"}])
        return Response({"id": "role-id", "name": "user"})

    monkeypatch.setattr(configure, "urlopen", request)
    configure.configure("http://identity", {
        "KEYCLOAK_ADMIN_USERNAME": "admin",
        "KEYCLOAK_ADMIN_PASSWORD": "password",
        "KEYCLOAK_BACKEND_CLIENT_SECRET": "backend-secret",
    })
    update = next(data for method, path, data in calls
                  if method == "PUT" and path == "/admin/realms/foc")
    assert update["registrationAllowed"] is True
    assert update["accessTokenLifespan"] == 300
    assert update["defaultRole"] == {"name": "default-roles-foc"}
    assert any(method == "POST" and path.endswith("/roles/default-roles-foc/composites")
               and data == [{"id": "role-id", "name": "user"}]
               for method, path, data in calls)
    clients = [data for method, path, data in calls
               if method == "PUT" and "/clients/" in path]
    assert len(clients) == 3
    assert all(client["attributes"]["access.token.lifespan"] == "" for client in clients)


def test_missing_administration_secret_rejected():
    with pytest.raises(ValueError, match="KEYCLOAK_BACKEND_CLIENT_SECRET"):
        configure.configure("http://identity", {})
