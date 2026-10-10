from typing import Annotated
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from foc_auth import (
    ApplicationRoleRequiredError,
    AuthenticationUnavailableError as KeycloakUnavailableError,
    KeycloakTokenValidator,
)
from starlette.concurrency import run_in_threadpool

from sqlalchemy.ext.asyncio import AsyncSession

from common.db import get_session
from common.config_manager import settings
from auth.exceptions import AuthenticationUnavailableError
from auth.models import UserRole, UserRoleResponse
from auth.service import get_authenticated_user_role, get_current_user_role, verify_access_token


bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_keycloak_validator() -> KeycloakTokenValidator:
    return KeycloakTokenValidator(
        settings.keycloak_issuer, settings.keycloak_audience, settings.keycloak_jwks_url
    )


async def get_authenticated_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserRoleResponse:
    token = (
        credentials.credentials
        if credentials is not None
        else request.cookies.get("access_token")
    )
    if not token:
        raise HTTPException(
            status_code=401,
            detail="No authentication token found. Please sign in.",
        )

    try:
        if settings.auth_provider == "keycloak":
            identity = await run_in_threadpool(get_keycloak_validator().validate, token)
            # Account migration must preserve existing application UUIDs.
            # Never create or link accounts by email during token validation.
            await get_current_user_role(identity.user_id, session)
            return UserRoleResponse(user_id=identity.user_id, role=identity.role)
        claims = verify_access_token(token)
        return await get_authenticated_user_role(token, claims.sub, session)
    except InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token. Please sign in.",
        ) from None
    except ApplicationRoleRequiredError:
        raise HTTPException(status_code=403, detail="A FoC application role is required.") from None
    except (AuthenticationUnavailableError, KeycloakUnavailableError):
        raise HTTPException(
            status_code=503,
            detail="Authentication is temporarily unavailable.",
        ) from None


AuthenticatedUser = Annotated[UserRoleResponse, Depends(get_authenticated_user)]


async def get_admin_manager_user(user: AuthenticatedUser) -> UserRoleResponse:
    if user.role != UserRole.ADMIN_MANAGER:
        raise HTTPException(status_code=403, detail="Admin manager access required.")
    return user


AdminManagerUser = Annotated[UserRoleResponse, Depends(get_admin_manager_user)]
