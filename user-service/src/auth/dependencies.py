from typing import Annotated
from functools import lru_cache

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens import ApplicationRoleRequiredError, AuthenticationUnavailableError, KeycloakTokenValidator
from common.db import get_session
from common.config_manager import settings
from auth.models import UserRole, UserRoleResponse
from auth.service import get_current_user_role


bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_keycloak_validator() -> KeycloakTokenValidator:
    return KeycloakTokenValidator(
        settings.keycloak_issuer, settings.keycloak_audience, settings.keycloak_jwks_url,
    )


async def get_authenticated_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserRoleResponse:
    if credentials is None:
        raise HTTPException(status_code=401, detail="No authentication token found. Please sign in.")
    try:
        identity = await run_in_threadpool(get_keycloak_validator().validate, credentials.credentials)
        await get_current_user_role(identity.user_id, session)
        return UserRoleResponse(user_id=identity.user_id, role=identity.role)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token. Please sign in.") from None
    except ApplicationRoleRequiredError:
        raise HTTPException(status_code=403, detail="A FoC application role is required.") from None
    except AuthenticationUnavailableError:
        raise HTTPException(status_code=503, detail="Authentication is temporarily unavailable.") from None


AuthenticatedUser = Annotated[UserRoleResponse, Depends(get_authenticated_user)]


async def get_admin_manager_user(user: AuthenticatedUser) -> UserRoleResponse:
    if user.role != UserRole.ADMIN_MANAGER:
        raise HTTPException(status_code=403, detail="Admin manager access required.")
    return user


AdminManagerUser = Annotated[UserRoleResponse, Depends(get_admin_manager_user)]
