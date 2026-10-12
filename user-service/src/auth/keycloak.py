"""Keycloak account administration. Only this service changes identities."""

import asyncio
from functools import lru_cache
from time import monotonic
from urllib.parse import quote
from uuid import UUID

import httpx

from auth.exceptions import AuthenticationUnavailableError, UserAlreadyExistsError, UserNotFoundError
from common.config_manager import settings


class KeycloakAdmin:
    def __init__(self, url: str, realm: str, client_id: str, client_secret: str):
        if not client_secret:
            raise ValueError("KEYCLOAK_BACKEND_CLIENT_SECRET must be set")
        self.url = url.rstrip("/")
        self.realm = quote(realm, safe="")
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: str | None = None
        self._expires = 0.0
        self._lock = asyncio.Lock()

    async def _token(self) -> str:
        async with self._lock:
            if self._access_token and monotonic() < self._expires:
                return self._access_token
            try:
                async with httpx.AsyncClient(base_url=self.url, timeout=5) as client:
                    response = await client.post(f"/realms/{self.realm}/protocol/openid-connect/token", data={
                        "grant_type": "client_credentials", "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    })
                response.raise_for_status()
                data = response.json()
                self._access_token = data["access_token"]
                self._expires = monotonic() + max(0, int(data["expires_in"]) - 30)
                return self._access_token
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                raise AuthenticationUnavailableError("Keycloak administration is unavailable.") from error

    async def _request(self, method: str, path: str, *, body=None, missing_ok=False) -> httpx.Response:
        try:
            token = await self._token()
            async with httpx.AsyncClient(base_url=self.url, timeout=5) as client:
                response = await client.request(method, f"/admin/realms/{self.realm}{path}", json=body,
                    headers={"Authorization": f"Bearer {token}"})
            if response.status_code == 404:
                if missing_ok:
                    return response
                raise UserNotFoundError("Keycloak account not found. Import the account before signing in.")
            if response.status_code == 409:
                raise UserAlreadyExistsError("Username or email already exists.")
            response.raise_for_status()
            return response
        except httpx.HTTPError as error:
            raise AuthenticationUnavailableError("Keycloak administration is unavailable.") from error

    async def create_user(self, username: str, email: str, password: str, role: str = "user") -> UUID:
        response = await self._request("POST", "/users", body={
            "username": username, "email": email, "enabled": True,
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        })
        try:
            user_id = UUID(response.headers["Location"].rstrip("/").rsplit("/", 1)[1])
        except (KeyError, ValueError) as error:
            raise AuthenticationUnavailableError("Invalid account creation response.") from error
        try:
            await self.set_role(user_id, role)
        except Exception:
            await self.delete_user(user_id)
            raise
        return user_id

    async def delete_user(self, user_id: UUID) -> None:
        await self._request("DELETE", f"/users/{user_id}", missing_ok=True)

    async def update_profile(self, user_id: UUID, username: str, email: str) -> None:
        await self._request("PUT", f"/users/{user_id}", body={"username": username, "email": email})

    async def set_role(self, user_id: UUID, role: str) -> None:
        if role not in {"user", "admin", "admin_manager"}:
            raise ValueError("Unknown application role")
        current = (await self._request("GET", f"/users/{user_id}/role-mappings/realm")).json()
        desired = (await self._request("GET", f"/roles/{role}")).json()
        await self._request("POST", f"/users/{user_id}/role-mappings/realm", body=[desired])
        remove = [r for r in current if r["name"] in {"user", "admin", "admin_manager"} and r["name"] != role]
        if remove:
            await self._request("DELETE", f"/users/{user_id}/role-mappings/realm", body=remove)

    async def logout_user(self, user_id: UUID) -> None:
        await self._request("POST", f"/users/{user_id}/logout")

    async def logout_session(self, session_id: str) -> None:
        # Quote identifiers so even a signed claim cannot alter the request path.
        await self._request("DELETE", f"/sessions/{quote(session_id, safe='')}", missing_ok=True)


@lru_cache
def get_keycloak_admin() -> KeycloakAdmin:
    return KeycloakAdmin(
        settings.keycloak_server_url, settings.keycloak_realm,
        settings.keycloak_backend_client_id,
        settings.keycloak_backend_client_secret.get_secret_value()
        if settings.keycloak_backend_client_secret else "",
    )
