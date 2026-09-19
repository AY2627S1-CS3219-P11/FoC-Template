from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator, model_validator


PASSWORD_REQUIREMENTS_MESSAGE = (
    "Password must be 8-64 characters and include at least one uppercase letter, "
    "one lowercase letter, and one digit."
)


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

    @field_validator("password")
    @classmethod
    def validate_password_requirements(cls, value: SecretStr) -> SecretStr:
        password = value.get_secret_value()
        if not (
            any("A" <= character <= "Z" for character in password)
            and any("a" <= character <= "z" for character in password)
            and any("0" <= character <= "9" for character in password)
        ):
            raise ValueError(PASSWORD_REQUIREMENTS_MESSAGE)
        return value


class SignInRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=1)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class AuthenticationResponse(BaseModel):
    message: str


class UserRecord(BaseModel):
    id: UUID
    username: str = Field(min_length=1)
    email: EmailStr
    hashed_password: str = Field(repr=False)
    user_role: UserRole


class UserRoleResponse(BaseModel):
    user_id: UUID
    role: UserRole


class CurrentUserResponse(BaseModel):
    username: str
    email: EmailStr


class ManagedUserResponse(BaseModel):
    user_id: UUID
    username: str
    email: EmailStr
    role: Literal[UserRole.USER, UserRole.ADMIN]


class UpdateUserRoleRequest(BaseModel):
    role: Literal[UserRole.USER, UserRole.ADMIN]


class UpdateCurrentUserRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = None

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_update(self) -> Self:
        if self.username is None and self.email is None:
            raise ValueError("Provide a username or email to update.")
        return self


class AccessTokenClaims(BaseModel):
    sub: UUID
    email: EmailStr
    tokenType: Literal["access"]
    iat: int = Field(strict=True)
    exp: int = Field(strict=True)
