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
    auth_provider: Literal["legacy", "keycloak"] = "legacy"
    keycloak_issuer: str = "http://localhost:8080/realms/foc"
    keycloak_audience: str = "foc-api"
    keycloak_jwks_url: str | None = None
    keycloak_server_url: str = "http://localhost:8080"
    keycloak_realm: str = "foc"
    keycloak_backend_client_id: str = "foc-backend"
    keycloak_backend_client_secret: SecretStr | None = None
    keycloak_api_client_id: str = "foc-api"
    keycloak_api_client_secret: SecretStr | None = None
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
