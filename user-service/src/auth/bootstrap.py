# auth/bootstrap.py

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.orm_models import User
from auth.service import hash_password
from auth.keycloak import get_keycloak_admin
from auth.repository import create_user
from common.config_manager import settings


async def provision_admin_manager(session: AsyncSession,) -> None:
    result = await session.execute(
        select(User.user_id).where(User.user_role == "admin_manager").limit(1)
    )

    if result.scalar_one_or_none() is not None:
        return
    
    if (settings.initial_admin_username is None 
        or settings.initial_admin_email is None or settings.initial_admin_password is None):
        raise RuntimeError("Initial Admin Manager credentials are not configured.")

    result = await session.execute(
        select(User.user_id).where(
            or_(
                User.username == settings.initial_admin_username,
                User.user_email == settings.initial_admin_email,
            )
        ).limit(1)
    )

    if result.scalar_one_or_none() is not None:
        raise RuntimeError(
            "Initial Admin Manager username or email is already in use."
        )
    
    if settings.auth_provider == "keycloak":
        admin = get_keycloak_admin()
        user_id = await admin.create_user(settings.initial_admin_username,
            str(settings.initial_admin_email), settings.initial_admin_password.get_secret_value(), "admin_manager")
        try:
            await create_user(session, settings.initial_admin_username,
                str(settings.initial_admin_email), "", user_id=user_id, role="admin_manager")
        except Exception:
            await admin.delete_user(user_id)
            raise
        return

    password_hash = hash_password(settings.initial_admin_password.get_secret_value())

    session.add(
        User(username=settings.initial_admin_username, user_email=settings.initial_admin_email,
            password_hash=password_hash, user_role="admin_manager",)
    )

    await session.commit()
