from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.orm_models import User
from auth.keycloak import get_keycloak_admin
from auth.repository import create_user
from common.config_manager import settings


async def provision_admin_manager(session: AsyncSession) -> None:
    existing = await session.scalar(select(User.user_id).where(User.user_role == "admin_manager").limit(1))
    if existing is not None:
        return
    if not all((settings.initial_admin_username, settings.initial_admin_email, settings.initial_admin_password)):
        raise RuntimeError("Initial Admin Manager credentials are not configured.")
    admin = get_keycloak_admin()
    user_id = await admin.create_user(settings.initial_admin_username,
        str(settings.initial_admin_email), settings.initial_admin_password.get_secret_value(), "admin_manager")
    try:
        await create_user(session, settings.initial_admin_username,
            str(settings.initial_admin_email), "", user_id=user_id, role="admin_manager")
    except Exception:
        await admin.delete_user(user_id)
        raise
