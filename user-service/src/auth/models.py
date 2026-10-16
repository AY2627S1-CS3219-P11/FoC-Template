from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"
    ADMIN_MANAGER = "admin_manager"


class UserRoleResponse(BaseModel):
    user_id: UUID
    role: UserRole


class CurrentUserResponse(BaseModel):
    username: str
    email: EmailStr


ManagedUserRole = Literal[UserRole.USER, UserRole.ADMIN]


class ManagedUserResponse(BaseModel):
    user_id: UUID
    username: str
    email: EmailStr
    role: ManagedUserRole


class ManagedUserPage(BaseModel):
    items: list[ManagedUserResponse]
    offset: int
    limit: int
    has_more: bool


class UpdateUserRoleRequest(BaseModel):
    role: ManagedUserRole
