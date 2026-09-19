from uuid import UUID

import datetime

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth.orm_models import User
from auth.models import (
    CurrentUserResponse,
    ManagedUserResponse,
    UserRecord,
    UserRole,
    UserRoleResponse,
)
from auth.exceptions import UserAlreadyExistsError

async def create_user(session: AsyncSession,
                      username: str,email: str, hashed_password: str,) -> UserRecord:

    user = User(username=username, user_email=email, password_hash=hashed_password,)

    session.add(user)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()

        constraint = getattr(exc.orig.diag, "constraint_name", None,)

        if constraint == "users_username_key" or constraint == "users_email_key":
            raise UserAlreadyExistsError("Username or Email already exists.") from None
        
        raise

    await session.refresh(user)

    return UserRecord(id=str(user.user_id), username=user.username,
        email=user.user_email, hashed_password=user.password_hash, user_role=user.user_role,)

async def find_user_by_email(session: AsyncSession, email: str,) -> UserRecord | None:

    result = await session.execute(
        select(User).where(User.user_email == email)
    )

    user = result.scalar_one_or_none()

    if user is None:
        return None

    return UserRecord(id=str(user.user_id), username=user.username,
        email=user.user_email, hashed_password=user.password_hash, user_role=user.user_role,)

async def find_user_by_username(session: AsyncSession, username: str,) -> UserRecord | None:

    result = await session.execute(
        select(User).where(User.username == username)
    )

    user = result.scalar_one_or_none()

    if user is None:
        return None

    return UserRecord(id=str(user.user_id), username=user.username,
        email=user.user_email, hashed_password=user.password_hash, user_role=user.user_role,)

async def find_user_role_by_id(session: AsyncSession, user_id: UUID,) -> UserRoleResponse | None:

    result = await session.execute(
        select(User.user_id, User.user_role).where(User.user_id == user_id)
    )

    user = result.one_or_none()

    if user is None:
        return None

    return UserRoleResponse(user_id=user.user_id, role=user.user_role)


async def find_managed_users(
    session: AsyncSession,
    query: str | None,
) -> list[ManagedUserResponse]:
    statement = select(User).where(User.user_role != UserRole.ADMIN_MANAGER)

    if query is None:
        statement = statement.where(User.user_role == UserRole.ADMIN)
    else:
        identifier = query.strip()
        statement = statement.where(
            or_(
                User.username == identifier,
                User.user_email == identifier.lower(),
            )
        )

    result = await session.scalars(statement.order_by(User.username))
    return [
        ManagedUserResponse(
            user_id=user.user_id,
            username=user.username,
            email=user.user_email,
            role=user.user_role,
        )
        for user in result.all()
    ]


async def update_managed_user_role(
    session: AsyncSession,
    user_id: UUID,
    role: UserRole,
) -> ManagedUserResponse | None:
    result = await session.execute(
        select(User).where(
            User.user_id == user_id,
            User.user_role != UserRole.ADMIN_MANAGER,
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        return None

    user.user_role = role
    user.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await session.commit()
    await session.refresh(user)

    return ManagedUserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.user_email,
        role=user.user_role,
    )

async def find_user_profile_by_id(session: AsyncSession, user_id: UUID,) -> CurrentUserResponse | None:

    result = await session.execute(
        select(User.username, User.user_email).where(User.user_id == user_id)
    )

    user = result.scalar_one_or_none()

    if user is None:
        return None

    return CurrentUserResponse(username=user.username, email=user.user_email)

async def update_user_profile(session: AsyncSession, user_id: UUID, 
                              username: str | None, email: str | None,) -> CurrentUserResponse | None:

    result = await session.execute(
        select(User).where(User.user_id == user_id)
    )

    user = result.scalar_one_or_none()

    if user is None:
        return None

    if username is not None:
        user.username = username
    if email is not None:
        user.user_email = email

    user.updated_at = datetime.datetime.now(datetime.timezone.utc)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()

        constraint = getattr(exc.orig.diag, "constraint_name", None,)

        if constraint == "users_username_key" or constraint == "users_email_key":
            raise UserAlreadyExistsError("Username or Email already exists.") from None
        
        raise

    await session.refresh(user)

    return CurrentUserResponse(username=user.username, email=user.user_email)
