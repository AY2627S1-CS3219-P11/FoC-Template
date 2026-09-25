# auth/bootstrap.py

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.orm_models import User
from auth.service import hash_password
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
    
    password_hash = hash_password(settings.initial_admin_password.get_secret_value())

    session.add(
        User(username=settings.initial_admin_username, user_email=settings.initial_admin_email,
            password_hash=password_hash, user_role="admin_manager",)
    )

    await session.commit()
