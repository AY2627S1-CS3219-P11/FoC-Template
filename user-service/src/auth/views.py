from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from auth.dependencies import AdminManagerUser, AuthenticatedUser
from auth.keycloak import get_keycloak_admin
from auth.models import (
    CurrentUserResponse, ManagedUserRole, ManagedUserResponse,
    UpdateUserRoleRequest, UserRole, UserRoleResponse,
)
from auth.service import get_users_for_access_management, update_user_role


router = APIRouter(prefix="/authentication", tags=["Authentication"])


@router.get("/sessions/current", response_model=UserRoleResponse)
async def verify(user: AuthenticatedUser):
    return user


@router.get("/users/current", response_model=CurrentUserResponse)
async def get_current_user(user: AuthenticatedUser):
    return await get_keycloak_admin().get_user(user.user_id)


@router.get("/users", response_model=list[ManagedUserResponse])
async def get_users(
    _admin_manager: AdminManagerUser,
    role: ManagedUserRole = UserRole.ADMIN,
    query: Annotated[str | None, Query(min_length=1, max_length=254)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    return await get_users_for_access_management(role, query, offset, limit)


@router.patch("/users/{user_id}/role", response_model=ManagedUserResponse)
async def change_user_role(
    user_id: UUID, update: UpdateUserRoleRequest, _admin_manager: AdminManagerUser,
):
    return await update_user_role(user_id, update)
