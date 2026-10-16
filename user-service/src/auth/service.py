from uuid import UUID

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from auth.exceptions import UserAlreadyExistsError, UserNotFoundError
from auth.models import (
    CurrentUserResponse, ManagedUserRole, ManagedUserResponse, SignUpRequest,
    UpdateCurrentUserRequest, UpdateUserRoleRequest, UserRecord, UserRoleResponse,
)
from auth.repository import (
    find_user_by_id, create_user, find_managed_users, find_user_by_email,
    find_user_profile_by_id, find_user_by_username, find_user_role_by_id,
    update_managed_user_role, update_user_profile,
)
from auth.keycloak import get_keycloak_admin


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


async def get_users_for_access_management(
    role: ManagedUserRole, query: str | None, session: AsyncSession,
) -> list[ManagedUserResponse]:
    return await find_managed_users(session, role, query)


async def update_user_role(
    user_id: UUID, request: UpdateUserRoleRequest, session: AsyncSession,
) -> ManagedUserResponse:
    previous = await find_user_by_id(session, user_id, for_update=True)
    if previous is None or previous.user_role == "admin_manager":
        raise UserNotFoundError("User not found.")
    admin = get_keycloak_admin()
    try:
        await admin.set_role(user_id, request.role)
        await admin.logout_user(user_id)
        user = await update_managed_user_role(session, user_id, request.role)
        if user is None:
            raise UserNotFoundError("User not found.")
    except Exception:
        await admin.set_role(user_id, previous.user_role)
        await admin.logout_user(user_id)
        raise
    return user


async def update_current_user_profile(
    user_id: UUID, request: UpdateCurrentUserRequest, session: AsyncSession,
) -> CurrentUserResponse:
    if request.username is not None:
        existing = await find_user_by_username(session, request.username)
        if existing is not None and existing.id != user_id:
            raise UserAlreadyExistsError("Username already exists")
    if request.email is not None:
        existing = await find_user_by_email(session, str(request.email))
        if existing is not None and existing.id != user_id:
            raise UserAlreadyExistsError("Email already exists")
    previous = await find_user_by_id(session, user_id, for_update=True)
    if previous is None:
        raise jwt.InvalidTokenError("The authenticated user no longer exists.")
    admin = get_keycloak_admin()
    await admin.update_profile(user_id, request.username or previous.username,
        str(request.email) if request.email is not None else str(previous.email))
    try:
        profile = await update_user_profile(session=session, user_id=user_id,
            username=request.username, email=str(request.email) if request.email is not None else None)
        if profile is None:
            raise jwt.InvalidTokenError("The authenticated user no longer exists.")
    except Exception:
        await admin.update_profile(user_id, previous.username, str(previous.email))
        raise
    return profile


async def register_user(request: SignUpRequest, session: AsyncSession) -> UserRecord:
    if await find_user_by_email(session, str(request.email)) is not None:
        raise UserAlreadyExistsError("Email already exists")
    if await find_user_by_username(session, request.username) is not None:
        raise UserAlreadyExistsError("Username already exists")
    admin = get_keycloak_admin()
    user_id = await admin.create_user(request.username, str(request.email), request.password.get_secret_value())
    try:
        return await create_user(session=session, username=request.username,
            email=str(request.email), hashed_password="", user_id=user_id)
    except Exception:
        await admin.delete_user(user_id)
        raise
