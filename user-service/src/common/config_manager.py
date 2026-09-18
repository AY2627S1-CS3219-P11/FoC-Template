from pathlib import Path
from typing import Literal

from pydantic import SecretStr, EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Campus Errands User Service"
    database_url: SecretStr | None = None
    initial_admin_username: str | None = None
    initial_admin_email: EmailStr | None = None
    initial_admin_password: SecretStr | None = None
    access_token_secret: SecretStr | None = None
    access_token_duration_seconds: int = 6 * 60 * 60
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
