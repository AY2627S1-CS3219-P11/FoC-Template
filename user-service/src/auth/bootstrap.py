from auth.keycloak import get_keycloak_admin
from common.config_manager import settings


async def provision_admin_manager() -> None:
    admin = get_keycloak_admin()
    if await admin.role_members("admin_manager", max_results=1):
        return
    if not all((settings.initial_admin_username, settings.initial_admin_email, settings.initial_admin_password)):
        raise RuntimeError("Initial Admin Manager credentials are not configured.")
    await admin.bootstrap_manager(settings.initial_admin_username,
        str(settings.initial_admin_email), settings.initial_admin_password.get_secret_value())
