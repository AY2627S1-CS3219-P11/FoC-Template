from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from jwt import InvalidTokenError

from common.config_manager import settings
from auth.exceptions import AuthenticationUnavailableError, InvalidCredentialsError
from auth.service import authenticate_user, verify_access_token
from auth.models import AuthenticationResponse, SignInRequest


router = APIRouter(prefix="/authentication", tags=["Authentication"])


def validate_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is not None and origin not in settings.cors_origins:
        raise HTTPException(status_code=403, detail="Origin is not allowed.")
    if origin is None and request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(status_code=403, detail="Origin is not allowed.")


def clear_access_token_cookie(response: Response) -> None:
    response.delete_cookie(
        "access_token",
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )


def unauthorized_response() -> JSONResponse:
    response = JSONResponse(status_code=401, content={"message": "Invalid or expired token. Please sign in."})
    clear_access_token_cookie(response)
    return response


@router.post("/sessions", response_model=AuthenticationResponse)
def sign_in(credentials: SignInRequest, request: Request, response: Response):
    validate_origin(request)
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
def sign_out(request: Request) -> Response:
    validate_origin(request)
    response = Response(status_code=204)
    clear_access_token_cookie(response)
    return response
