"""Shared Keycloak token validation for independently deployed FoC services."""

from dataclasses import dataclass
from json import JSONDecodeError
from threading import Lock
from urllib.parse import urlsplit
from uuid import UUID

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError, PyJWKSetError


class AuthenticationUnavailableError(Exception):
    """The configured signing keys cannot be retrieved."""


class ApplicationRoleRequiredError(Exception):
    """A valid identity has no FoC application role."""


@dataclass(frozen=True)
class Identity:
    user_id: UUID
    role: str


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
    def __init__(self, issuer: str, audience: str, jwks_url: str | None = None):
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

        realm_access = claims.get("realm_access", {})
        roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
        if not isinstance(roles, list) or any(not isinstance(role, str) for role in roles):
            raise jwt.InvalidTokenError("Invalid realm roles")
        for role in ("admin_manager", "admin", "user"):
            if role in roles:
                return Identity(user_id=user_id, role=role)
        raise ApplicationRoleRequiredError("A FoC application role is required")
