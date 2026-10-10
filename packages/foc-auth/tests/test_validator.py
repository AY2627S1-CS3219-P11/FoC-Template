import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from time import time
from types import SimpleNamespace
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from foc_auth import (
    ApplicationRoleRequiredError,
    AuthenticationUnavailableError,
    KeycloakTokenValidator,
)


SUBJECT = "00000000-0000-0000-0000-000000000001"
ISSUER = "http://localhost:8080/realms/foc"


@pytest.fixture(scope="module")
def keys():
    return [rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2)]


@pytest.fixture
def server(keys):
    state = {"requests": 0, "index": 0, "status": 200, "malformed": False}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            from urllib.parse import parse_qs
            state["introspection"] = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
            self.send_response(state.get("session_status", 200))
            self.end_headers()
            self.wfile.write(json.dumps(state.get("session", {"active": True})).encode())

        def do_GET(self):
            state["requests"] += 1
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            index = state["index"]
            jwk = json.loads(RSAAlgorithm.to_jwk(keys[index].public_key()))
            jwk.update(kid=f"key-{index}", use="sig", alg="RS256")
            self.wfile.write(b"invalid-json" if state["malformed"] else json.dumps({"keys": [jwk]}).encode())

        def log_message(self, *_args):
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    validator = KeycloakTokenValidator(ISSUER, "foc-api", f"http://127.0.0.1:{http.server_port}/certs")
    yield validator, state
    http.shutdown()
    http.server_close()
    thread.join()


def token(keys, index=0, **changes):
    now = int(time())
    claims = {
        "sub": SUBJECT, "iss": ISSUER, "aud": ["foc-api", "account"],
        "exp": now + 300, "iat": now, "typ": "Bearer",
        "realm_access": {"roles": ["offline_access", "user"]},
    } | changes
    return jwt.encode(claims, keys[index], algorithm="RS256", headers={"kid": f"key-{index}"})


def test_valid_token_uses_cached_keys(server, keys):
    validator, state = server
    identity = validator.validate(token(keys))
    assert identity.user_id == UUID(SUBJECT)
    assert identity.role == "user"
    validator.validate(token(keys))
    assert state["requests"] == 1


def test_key_rotation_refreshes_jwks(server, keys, monkeypatch):
    validator, state = server
    validator.validate(token(keys))
    state["index"] = 1
    # A new signing key is retrieved after the library's 30-second refresh
    # cooldown. Advance its clock rather than sleeping in the test.
    import jwt.jwks_client
    future = jwt.jwks_client.time.monotonic() + 31
    monkeypatch.setattr(jwt.jwks_client, "time", SimpleNamespace(monotonic=lambda: future))
    assert validator.validate(token(keys, index=1)).role == "user"
    assert state["requests"] == 2
    with pytest.raises(jwt.InvalidTokenError):
        validator.validate(token(keys))


def test_unknown_kids_do_not_trigger_a_fetch_storm(server, keys):
    validator, state = server
    validator.validate(token(keys))
    for _ in range(3):
        with pytest.raises(jwt.InvalidTokenError):
            validator.validate(token(keys, index=1))
    assert state["requests"] == 1


@pytest.mark.parametrize("changes", [
    {"exp": 1}, {"iat": int(time()) + 600}, {"nbf": int(time()) + 600},
    {"iss": "http://attacker/realms/foc"}, {"aud": "another-api"},
    {"sub": "not-a-uuid"}, {"sub": None}, {"typ": "ID"},
    {"realm_access": {"roles": "admin"}}, {"realm_access": {"roles": [123]}},
])
def test_invalid_claims_rejected(server, keys, changes):
    validator, _ = server
    with pytest.raises(jwt.InvalidTokenError):
        validator.validate(token(keys, **changes))


@pytest.mark.parametrize("missing", ["sub", "iss", "aud", "exp", "iat", "typ"])
def test_required_claims(server, keys, missing):
    validator, _ = server
    claims = jwt.decode(token(keys), options={"verify_signature": False})
    claims.pop(missing)
    signed = jwt.encode(claims, keys[0], algorithm="RS256", headers={"kid": "key-0"})
    with pytest.raises(jwt.InvalidTokenError):
        validator.validate(signed)


def test_wrong_signature_and_unknown_key_rejected(server, keys):
    validator, _ = server
    signed = jwt.encode(
        jwt.decode(token(keys), options={"verify_signature": False}),
        keys[1], algorithm="RS256", headers={"kid": "key-0"},
    )
    with pytest.raises(jwt.InvalidTokenError):
        validator.validate(signed)
    with pytest.raises(jwt.InvalidTokenError):
        validator.validate(token(keys, index=1))


def test_legacy_token_rejected_without_key_request(server):
    validator, state = server
    legacy = jwt.encode({"sub": SUBJECT}, "x" * 32, algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        validator.validate(legacy)
    assert state["requests"] == 0


def test_keys_unavailable(server, keys):
    validator, state = server
    state["status"] = 503
    with pytest.raises(AuthenticationUnavailableError):
        validator.validate(token(keys))


def test_malformed_key_response_is_unavailable(server, keys):
    validator, state = server
    state["malformed"] = True
    with pytest.raises(AuthenticationUnavailableError):
        validator.validate(token(keys))


@pytest.mark.parametrize("roles,expected", [
    (["user", "admin"], "admin"),
    (["admin", "admin_manager", "user"], "admin_manager"),
])
def test_application_role_priority(server, keys, roles, expected):
    validator, _ = server
    assert validator.validate(token(keys, realm_access={"roles": roles})).role == expected


def test_builtin_roles_do_not_grant_application_access(server, keys):
    validator, _ = server
    with pytest.raises(ApplicationRoleRequiredError):
        validator.validate(token(keys, realm_access={"roles": ["offline_access", "uma_authorization"]}))


@pytest.mark.parametrize("response,expected", [
    ({"active": True}, None), ({"active": False}, jwt.InvalidTokenError),
    ({"active": "true"}, AuthenticationUnavailableError), ({}, AuthenticationUnavailableError),
])
def test_session_checks_reject_revoked_tokens_and_malformed_responses(server, keys, response, expected):
    base, state = server
    state["session"] = response
    validator = KeycloakTokenValidator(ISSUER, "foc-api", base.jwks_url,
        introspection_url=base.jwks_url.replace("/certs", "/introspect"),
        client_id="foc-backend", client_secret="server-secret")
    signed = token(keys, sid="session-id")
    if expected:
        with pytest.raises(expected):
            validator.validate(signed)
    else:
        assert validator.validate(signed).session_id == "session-id"
    assert state["introspection"]["token"] == [signed]
    assert state["introspection"]["client_id"] == ["foc-backend"]


def test_session_check_outage_fails_closed(server, keys):
    base, state = server
    state["session_status"] = 503
    validator = KeycloakTokenValidator(ISSUER, "foc-api", base.jwks_url,
        introspection_url=base.jwks_url.replace("/certs", "/introspect"),
        client_id="foc-backend", client_secret="server-secret")
    with pytest.raises(AuthenticationUnavailableError):
        validator.validate(token(keys))


def test_session_check_requires_backend_credentials():
    with pytest.raises(ValueError):
        KeycloakTokenValidator(ISSUER, "foc-api", introspection_url=ISSUER + "/introspect")
