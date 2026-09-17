from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from jwt import InvalidTokenError
from shared_auth import require_user_id
from common.db import get_db_connection
from common.config_manager import settings
from auth.exceptions import (
    AuthenticationUnavailableError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
)
from auth.service import (
    authenticate_user,
    get_current_user_profile,
    get_current_user_role,
    register_user,
    update_current_user_profile,
    verify_access_token,
)
from auth.models import (
    AuthenticationResponse,
    CurrentUserResponse,
    SignInRequest,
    SignUpRequest,
    TokenVerificationResponse,
    UpdateCurrentUserRequest,
    UserRoleResponse,
)
from auth.responses import clear_access_token_cookie, unauthorized_response


router = APIRouter(prefix="/authentication", tags=["Authentication"])
AuthenticatedUserId = Annotated[str, Depends(require_user_id)]


@router.post("/users", status_code=201)
def sign_up(credentials: SignUpRequest):
    try:
        user = register_user(credentials)
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    return {"message": "Account created successfully. Please sign in to continue."}


@router.get("/users/current", response_model=CurrentUserResponse)
def get_current_user(user_id: AuthenticatedUserId):
    try:
        return get_current_user_profile(UUID(user_id))
    except (InvalidTokenError, ValueError):
        return unauthorized_response()


@router.patch("/users/current", response_model=CurrentUserResponse)
def update_current_user(update: UpdateCurrentUserRequest, user_id: AuthenticatedUserId):
    try:
        return update_current_user_profile(UUID(user_id), update)
    except UserAlreadyExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except (InvalidTokenError, ValueError):
        return unauthorized_response()


@router.post("/sessions", response_model=AuthenticationResponse)
def sign_in(credentials: SignInRequest, response: Response):
    try:
        token = authenticate_user(credentials)
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Invalid email or password.") from None
    except AuthenticationUnavailableError:
        raise HTTPException(status_code=503, detail="Authentication is temporarily unavailable.") from None

    response.set_cookie(
        "access_token",
        token,
        max_age=settings.access_token_duration_seconds,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return AuthenticationResponse(message="Successfully signed in.")


@router.get("/sessions/current", response_model=TokenVerificationResponse)
def verify(request: Request):
    token = request.cookies.get("access_token")

    if not token:
        return unauthorized_response()
    try:
        claims = verify_access_token(token)
    except InvalidTokenError:
        return unauthorized_response()
    except AuthenticationUnavailableError:
        raise HTTPException(status_code=503, detail="Authentication is temporarily unavailable.") from None
    return TokenVerificationResponse(message="Authenticated user.", user_id=str(claims.sub))


@router.get("/sessions/current/role", response_model=UserRoleResponse)
def get_current_role(user_id: AuthenticatedUserId):
    try:
        return get_current_user_role(UUID(user_id))
    except (InvalidTokenError, ValueError):
        return unauthorized_response()


@router.delete("/sessions/current", status_code=204)
def sign_out() -> Response:
    response = Response(status_code=204)
    clear_access_token_cookie(response)
    return response
