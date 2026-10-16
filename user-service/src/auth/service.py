from uuid import UUID

from auth.exceptions import AuthenticationUnavailableError, UserNotFoundError
from auth.keycloak import get_keycloak_admin
from auth.models import ManagedUserRole, ManagedUserResponse, UpdateUserRoleRequest


async def get_users_for_access_management(
    role: ManagedUserRole, query: str | None, offset: int = 0, limit: int = 100,
) -> list[ManagedUserResponse]:
    admin = get_keycloak_admin()
    members = await admin.role_members(role, first=offset, max_results=limit)
    result = []
    for member in members:
        try:
            user_id = UUID(member["id"])
        except (KeyError, ValueError, TypeError) as error:
            raise AuthenticationUnavailableError("Invalid identity response.") from error
        # A manager may also hold user/admin roles. Never expose it as manageable.
        try:
            user = await admin.managed_user(user_id)
        except UserNotFoundError:
            continue
        if user.role != role:
            continue
        if query and query.strip().casefold() not in f"{user.username} {user.email}".casefold():
            continue
        result.append(user)
    return sorted(result, key=lambda user: user.username.casefold())


async def update_user_role(user_id: UUID, request: UpdateUserRoleRequest) -> ManagedUserResponse:
    return await get_keycloak_admin().set_managed_role(user_id, request.role)
