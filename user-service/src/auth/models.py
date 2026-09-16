from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"
    ADMIN_MANAGER = "admin_manager"


class SignUpRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr
    password: SecretStr = Field(min_length=8, max_length=64)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

class SignInRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=1)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class AuthenticationResponse(BaseModel):
    message: str


class TokenVerificationResponse(AuthenticationResponse):
    user_id: str = Field(min_length=1)


class UserRecord(BaseModel):
    id: UUID
    username: str = Field(min_length=1)
    email: EmailStr
    hashed_password: str = Field(repr=False)
    user_role: UserRole


class UserRoleResponse(BaseModel):
    user_id: UUID
    role: UserRole


class AccessTokenClaims(BaseModel):
    sub: UUID
    email: EmailStr
    tokenType: Literal["access"]
    iat: int = Field(strict=True)
    exp: int = Field(strict=True)
