from datetime import datetime, timedelta, timezone
import secrets
from uuid import UUID

import bcrypt
import jwt
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from common.config_manager import settings
from auth.exceptions import (
    AuthenticationUnavailableError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
)
from auth.models import (
    AccessTokenClaims,
    CurrentUserResponse,
    SignInRequest,
    SignUpRequest,
    UpdateCurrentUserRequest,
    UserRecord,
    UserRoleResponse,
)
from auth.repository import (
    create_user,
    find_user_by_email,
    find_user_profile_by_id,
    find_user_by_username,
    find_user_role_by_id,
    update_user_profile,
)


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
            "sub": str(user.id),
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


async def authenticate_user(credentials: SignInRequest, session: AsyncSession) -> str:
    password = credentials.password.get_secret_value()
    if len(password.encode("utf-8")) > 72:
        raise InvalidCredentialsError()

    get_access_token_secret()
    user = await find_user_by_email(session, str(credentials.email))
    fallback_password_hash = hash_password(secrets.token_urlsafe(32))
    matches = verify_password(password, user.hashed_password if user else fallback_password_hash)

    if user is None or not matches:
        raise InvalidCredentialsError()
    return create_access_token(user)


async def get_current_user_role(user_id: UUID, session: AsyncSession) -> UserRoleResponse:
    role = await find_user_role_by_id(session, user_id)
    if role is None:
        raise jwt.InvalidTokenError("The authenticated user no longer exists.")
    return role


async def get_current_user_profile(user_id: UUID, session: AsyncSession) -> CurrentUserResponse:
    profile = await find_user_profile_by_id(session, user_id)
    if profile is None:
        raise jwt.InvalidTokenError("The authenticated user no longer exists.")
    return profile


async def update_current_user_profile(
    user_id: UUID,
    request: UpdateCurrentUserRequest, 
    session: AsyncSession
) -> CurrentUserResponse:
    if request.username is not None:
        existing_username = await find_user_by_username(session, request.username)
        if existing_username is not None and existing_username.id != str(user_id):
            raise UserAlreadyExistsError("Username already exists")

    if request.email is not None:
        existing_email = await find_user_by_email(session, str(request.email))
        if existing_email is not None and existing_email.id != str(user_id):
            raise UserAlreadyExistsError("Email already exists")

    profile = await update_user_profile(
        session=session, 
        user_id=user_id,
        username=request.username,
        email=str(request.email) if request.email is not None else None,
    )
    if profile is None:
        raise jwt.InvalidTokenError("The authenticated user no longer exists.")
    return profile


async def register_user(request: SignUpRequest, session: AsyncSession) -> UserRecord:
    existing_email = await find_user_by_email(session, str(request.email))
    if existing_email is not None:
        raise UserAlreadyExistsError("Email already exists")

    existing_username = await find_user_by_username(session, request.username)
    if existing_username is not None:
        raise UserAlreadyExistsError("Username already exists")

    hashed_password = hash_password(request.password.get_secret_value())

    return await create_user(session=session, username=request.username,
                              email=str(request.email), hashed_password=hashed_password)
