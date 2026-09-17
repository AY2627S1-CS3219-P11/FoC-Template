from typing import Annotated

from fastapi import Depends, HTTPException, Request
from jwt import InvalidTokenError

from auth.exceptions import AuthenticationUnavailableError
from auth.models import UserRoleResponse
from auth.service import get_current_user_role, verify_access_token


def get_authenticated_user(request: Request) -> UserRoleResponse:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="No authentication token found. Please sign in.",
        )

    try:
        claims = verify_access_token(token)
        return get_current_user_role(claims.sub)
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
