"""Supplier authentication uses signed bearer tokens, never another service."""

import os
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from auth.tokens import (
    ApplicationRoleRequiredError,
    AuthenticationUnavailableError,
    KeycloakTokenValidator,
)


class AuthenticatedUser(BaseModel):
    user_id: UUID
    role: str


@lru_cache
def get_keycloak_validator() -> KeycloakTokenValidator:
    return KeycloakTokenValidator(
        os.environ.get("KEYCLOAK_ISSUER", ""),
        os.environ.get("KEYCLOAK_AUDIENCE", ""),
        os.environ.get("KEYCLOAK_JWKS_URL") or None,
    )


bearer_scheme = HTTPBearer(auto_error=False)


async def get_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="No authentication token found. Please sign in.")
    try:
        identity = await run_in_threadpool(get_keycloak_validator().validate, credentials.credentials)
        return AuthenticatedUser(user_id=identity.user_id, role=identity.role)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token. Please sign in.") from None
    except ApplicationRoleRequiredError:
        raise HTTPException(status_code=403, detail="A FoC application role is required.") from None
    except AuthenticationUnavailableError:
        raise HTTPException(status_code=503, detail="Authentication is temporarily unavailable.") from None
