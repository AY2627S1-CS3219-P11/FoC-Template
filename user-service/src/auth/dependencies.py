from typing import Annotated

from fastapi import Depends, HTTPException, Request
from jwt import InvalidTokenError

from sqlalchemy.ext.asyncio import AsyncSession

from common.db import get_session
from auth.exceptions import AuthenticationUnavailableError
from auth.models import UserRoleResponse
from auth.service import get_current_user_role, verify_access_token


async def get_authenticated_user(request: Request, session: Annotated[AsyncSession, Depends(get_session)],) -> UserRoleResponse:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="No authentication token found. Please sign in.",
        )

    try:
        claims = verify_access_token(token)
        return await get_current_user_role(claims.sub, session)
    except InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token. Please sign in.",
        ) from None
    except AuthenticationUnavailableError:
        raise HTTPException(
            status_code=503,
            detail="Authentication is temporarily unavailable.",
        ) from None


AuthenticatedUser = Annotated[UserRoleResponse, Depends(get_authenticated_user)]
