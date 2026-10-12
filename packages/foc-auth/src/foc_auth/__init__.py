"""Shared Keycloak token validation for independently deployed FoC services."""

from dataclasses import dataclass
from json import JSONDecodeError, load
from threading import Lock
from urllib.parse import urlsplit
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError
from uuid import UUID

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError, PyJWKSetError


class AuthenticationUnavailableError(Exception):
    """Keycloak signing keys or session verification are unavailable."""


class ApplicationRoleRequiredError(Exception):
    """A valid identity has no FoC application role."""


@dataclass(frozen=True)
class Identity:
    user_id: UUID
    role: str
    session_id: str | None = None


def auth_provider(value: str) -> str:
    if value not in {"legacy", "keycloak"}:
        raise ValueError("AUTH_PROVIDER must be legacy or keycloak")
    return value


def _http_url(value: str, setting: str) -> str:
    url = urlsplit(value)
    if (
        url.scheme not in {"http", "https"}
        or not url.hostname
        or url.username is not None
        or url.password is not None
        or url.query
        or url.fragment
    ):
        raise ValueError(f"{setting} must be an HTTP(S) URL without credentials, query or fragment")
    return value


class KeycloakTokenValidator:
    def __init__(
        self, issuer: str, audience: str, jwks_url: str | None = None, *,
        introspection_url: str | None = None, client_id: str | None = None,
        client_secret: str | None = None,
    ):
        self.issuer = _http_url(issuer.rstrip("/"), "KEYCLOAK_ISSUER")
        if not audience.strip():
            raise ValueError("KEYCLOAK_AUDIENCE must be set")
        self.audience = audience
        self.jwks_url = _http_url(
            jwks_url or self.issuer + "/protocol/openid-connect/certs",
            "KEYCLOAK_JWKS_URL",
        )
        # Cache the key set rather than caching individual keys indefinitely.
        self._keys = PyJWKClient(self.jwks_url, cache_jwk_set=True, lifespan=300, timeout=5)
        self._lock = Lock()
        self.introspection_url = None
        if introspection_url is not None:
            self.introspection_url = _http_url(introspection_url, "KEYCLOAK_INTROSPECTION_URL")
            if not client_id or not client_secret:
                raise ValueError("Keycloak session checks require backend client credentials")
        self._client_id = client_id
        self._client_secret = client_secret

    def _check_session(self, token: str) -> None:
        if self.introspection_url is None:
            return
        body = urlencode({
            "token": token, "token_type_hint": "access_token",
            "client_id": self._client_id, "client_secret": self._client_secret,
        }).encode()
        try:
            request = Request(self.introspection_url, data=body, headers={
                "Content-Type": "application/x-www-form-urlencoded",
            })
            with urlopen(request, timeout=5) as response:
                active = load(response)
        except (URLError, TimeoutError, JSONDecodeError) as error:
            raise AuthenticationUnavailableError("Keycloak session verification is unavailable") from error
        if not isinstance(active, dict) or not isinstance(active.get("active"), bool):
            raise AuthenticationUnavailableError("Invalid session verification response")
        if not active["active"]:
            raise jwt.InvalidTokenError("The Keycloak session is inactive")

    def validate(self, token: str) -> Identity:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str) or not header["kid"]:
            raise jwt.InvalidTokenError("Expected an RS256 token with a signing key ID")
        try:
            # Services call this synchronous method from a worker thread.
            with self._lock:
                key = self._keys.get_signing_key_from_jwt(token).key
        except (PyJWKClientConnectionError, JSONDecodeError, PyJWKSetError) as error:
            raise AuthenticationUnavailableError("Signing keys are unavailable") from error
        except PyJWKClientError as error:
            raise jwt.InvalidTokenError("No matching signing key") from error

        claims = jwt.decode(
            token, key, algorithms=["RS256"], issuer=self.issuer, audience=self.audience,
            options={"require": ["sub", "iss", "aud", "exp", "iat", "typ"]},
        )
        if claims["typ"] != "Bearer":
            raise jwt.InvalidTokenError("Expected an access token")
        try:
            user_id = UUID(claims["sub"])
        except (TypeError, ValueError, AttributeError) as error:
            raise jwt.InvalidTokenError("Expected a UUID subject") from error

        self._check_session(token)
        session_id = claims.get("sid")
        if session_id is not None and not isinstance(session_id, str):
            raise jwt.InvalidTokenError("Invalid session ID")

        realm_access = claims.get("realm_access", {})
        roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
        if not isinstance(roles, list) or any(not isinstance(role, str) for role in roles):
            raise jwt.InvalidTokenError("Invalid realm roles")
        for role in ("admin_manager", "admin", "user"):
            if role in roles:
                return Identity(user_id=user_id, role=role, session_id=session_id)
        raise ApplicationRoleRequiredError("A FoC application role is required")
