"""Authentication dependencies, separate from supplier business operations."""

import os
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from foc_auth import (
    ApplicationRoleRequiredError,
    AuthenticationUnavailableError,
    KeycloakTokenValidator,
    auth_provider,
)
from jwt import InvalidTokenError
from pydantic import AnyHttpUrl, BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool


class AuthenticatedUser(BaseModel):
    user_id: UUID
    role: str


def get_internal_gateway_url() -> str:
    value = os.environ.get("INTERNAL_GATEWAY_URL")
    if value is None or not value.strip():
        raise RuntimeError("INTERNAL_GATEWAY_URL must be set")
    message = "INTERNAL_GATEWAY_URL must be an HTTP(S) origin without credentials, a path, query, or fragment"
    try:
        url = AnyHttpUrl(value)
    except ValidationError as error:
        raise RuntimeError(message) from error
    if url.path not in {None, "", "/"} or any(
        part is not None for part in (url.username, url.password, url.query, url.fragment)
    ):
        raise RuntimeError(message)
    return str(url).rstrip("/")


@lru_cache
def get_keycloak_validator() -> KeycloakTokenValidator:
    return KeycloakTokenValidator(
        os.environ.get("KEYCLOAK_ISSUER", ""),
        os.environ.get("KEYCLOAK_AUDIENCE", ""),
        os.environ.get("KEYCLOAK_JWKS_URL") or None,
        introspection_url=f"{os.environ.get('KEYCLOAK_SERVER_URL', 'http://localhost:8080').rstrip('/')}/realms/{os.environ.get('KEYCLOAK_REALM', 'foc')}/protocol/openid-connect/token/introspect",
        client_id=os.environ.get("KEYCLOAK_API_CLIENT_ID", "foc-api"),
        client_secret=os.environ.get("KEYCLOAK_API_CLIENT_SECRET"),
    )


async def get_internal_gateway_client() -> AsyncIterator[httpx.AsyncClient | None]:
    if auth_provider(os.environ.get("AUTH_PROVIDER", "legacy")) == "keycloak":
        # No client or gateway configuration is needed in Keycloak mode.
        yield None
        return
    async with httpx.AsyncClient(base_url=get_internal_gateway_url(), timeout=5.0) as client:
        yield client


bearer_scheme = HTTPBearer(auto_error=False)


async def get_user(
    request: Request,
    client: Annotated[httpx.AsyncClient | None, Depends(get_internal_gateway_client)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
) -> AuthenticatedUser:
    token = credentials.credentials if credentials is not None else request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="No authentication token found. Please sign in.")
    try:
        if auth_provider(os.environ.get("AUTH_PROVIDER", "legacy")) == "keycloak":
            identity = await run_in_threadpool(get_keycloak_validator().validate, token)
            return AuthenticatedUser(user_id=identity.user_id, role=identity.role)

        # Legacy compatibility is explicit. Keycloak mode never falls
        # back to this path, even when validation or signing-key retrieval fails.
        if client is None:
            raise AuthenticationUnavailableError()
        response = await client.get(
            "/user-api/authentication/sessions/current",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 401:
            raise InvalidTokenError()
        if not response.is_success:
            raise AuthenticationUnavailableError()
        try:
            return AuthenticatedUser.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise AuthenticationUnavailableError() from error
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token. Please sign in.") from None
    except ApplicationRoleRequiredError:
        raise HTTPException(status_code=403, detail="A FoC application role is required.") from None
    except (AuthenticationUnavailableError, httpx.RequestError):
        raise HTTPException(status_code=503, detail="Authentication is temporarily unavailable.") from None
