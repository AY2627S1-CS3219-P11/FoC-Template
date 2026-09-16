from typing import Literal

from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator

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


class UserRecord(BaseModel):
    id: str = Field(min_length=1)
    username: str = Field(min_length=1)
    email: EmailStr
    hashed_password: str = Field(repr=False)
    user_role: Literal["user", "admin", "admin_manager"]


class AccessTokenClaims(BaseModel):
    sub: str = Field(min_length=1, strict=True)
    email: EmailStr
    tokenType: Literal["access"]
    iat: int = Field(strict=True)
    exp: int = Field(strict=True)
