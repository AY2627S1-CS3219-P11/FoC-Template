from fastapi import APIRouter, HTTPException, Request, Response
from jwt import InvalidTokenError
from common.db import get_db_connection
from common.config_manager import settings
from auth.exceptions import AuthenticationUnavailableError, InvalidCredentialsError, UserAlreadyExistsError
from auth.service import authenticate_user, verify_access_token, register_user
from auth.models import AuthenticationResponse, SignInRequest, SignUpRequest
from auth.responses import clear_access_token_cookie, unauthorized_response


router = APIRouter(prefix="/authentication", tags=["Authentication"])

# TODO: check role/membership role

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


@router.get("/sessions/current", response_model=AuthenticationResponse)
def verify(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return unauthorized_response()
    try:
        verify_access_token(token)
    except InvalidTokenError:
        return unauthorized_response()
    except AuthenticationUnavailableError:
        raise HTTPException(status_code=503, detail="Authentication is temporarily unavailable.") from None
    return AuthenticationResponse(message="Authenticated user.")


@router.delete("/sessions/current", status_code=204)
def sign_out() -> Response:
    response = Response(status_code=204)
    clear_access_token_cookie(response)
    return response
