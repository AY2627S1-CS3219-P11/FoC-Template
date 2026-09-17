from fastapi import APIRouter, HTTPException, Response
from jwt import InvalidTokenError
from common.db import get_db_connection
from common.config_manager import settings
from auth.dependencies import AuthenticatedUser
from auth.exceptions import (
    AuthenticationUnavailableError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
)
from auth.service import (
    authenticate_user,
    get_current_user_profile,
    register_user,
    update_current_user_profile,
)
from auth.models import (
    AuthenticationResponse,
    CurrentUserResponse,
    SignInRequest,
    SignUpRequest,
    UpdateCurrentUserRequest,
    UserRoleResponse,
)
from auth.responses import clear_access_token_cookie, unauthorized_response


router = APIRouter(prefix="/authentication", tags=["Authentication"])


@router.post("/users", status_code=201)
def sign_up(credentials: SignUpRequest):
    try:
        user = register_user(credentials)
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    return {"message": "Account created successfully. Please sign in to continue."}


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


@router.get("/sessions/current", response_model=UserRoleResponse)
def verify(user: AuthenticatedUser):
    return user


@router.get("/users/current", response_model=CurrentUserResponse)
def get_current_user(user: AuthenticatedUser):
    try:
        return get_current_user_profile(user.user_id)
    except InvalidTokenError:
        return unauthorized_response()


@router.patch("/users/current", response_model=CurrentUserResponse)
def update_current_user(update: UpdateCurrentUserRequest, user: AuthenticatedUser):
    try:
        return update_current_user_profile(user.user_id, update)
    except UserAlreadyExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except InvalidTokenError:
        return unauthorized_response()


@router.delete("/sessions/current", status_code=204)
def sign_out() -> Response:
    response = Response(status_code=204)
    clear_access_token_cookie(response)
    return response
