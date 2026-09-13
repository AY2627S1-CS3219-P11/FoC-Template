from datetime import datetime, timedelta, timezone
import secrets

import bcrypt
import jwt
from pydantic import ValidationError

from common.config_manager import settings
from auth.exceptions import AuthenticationUnavailableError, InvalidCredentialsError
from auth.models import AccessTokenClaims, SignInRequest, UserRecord


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if not 1 <= len(encoded) <= 72:
        raise ValueError("Password must contain between 1 and 72 UTF-8 bytes.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=10)).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    encoded = password.encode("utf-8")
    if not 1 <= len(encoded) <= 72:
        return False
    try:
        return bcrypt.checkpw(encoded, hashed_password.encode("utf-8"))
    except ValueError:
        return False


def get_access_token_secret() -> str:
    secret = settings.access_token_secret
    if secret is None or len(secret.get_secret_value().encode("utf-8")) < 32:
        raise AuthenticationUnavailableError("Authentication is temporarily unavailable.")
    return secret.get_secret_value()


def create_access_token(user: UserRecord) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user.id,
            "email": str(user.email),
            "tokenType": "access",
            "iat": now,
            "exp": now + timedelta(seconds=settings.access_token_duration_seconds),
        },
        get_access_token_secret(),
        algorithm="HS256",
    )


def verify_access_token(token: str) -> AccessTokenClaims:
    payload = jwt.decode(
        token,
        get_access_token_secret(),
        algorithms=["HS256"],
        options={"require": ["sub", "email", "tokenType", "iat", "exp"]},
    )
    try:
        return AccessTokenClaims.model_validate(payload)
    except ValidationError:
        raise jwt.InvalidTokenError("Invalid access token claims.") from None


fallback_password_hash = hash_password(secrets.token_urlsafe(32))


def find_user_by_email(email: str) -> UserRecord | None:
    # TODO: add SQL query to find the user ID, email, and hashed password by normalized email.
    return None


def authenticate_user(credentials: SignInRequest) -> str:
    password = credentials.password.get_secret_value()
    if len(password.encode("utf-8")) > 72:
        raise InvalidCredentialsError()
    get_access_token_secret()
    user = find_user_by_email(str(credentials.email))
    matches = verify_password(password, user.hashed_password if user else fallback_password_hash)
    if user is None or not matches:
        raise InvalidCredentialsError()
    return create_access_token(user)
