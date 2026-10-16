"""Identity administration owned by user-service, not used for JWT verification."""

import asyncio
from functools import lru_cache
from time import monotonic
from urllib.parse import quote
from uuid import UUID

import httpx
from pydantic import ValidationError

from auth.exceptions import AuthenticationUnavailableError, UserAlreadyExistsError, UserNotFoundError
from auth.models import CurrentUserResponse, ManagedUserResponse
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
                token = data["access_token"]
                if not isinstance(token, str) or not token:
                    raise ValueError("Missing service token")
                self._expires = monotonic() + max(0, int(data["expires_in"]) - 30)
                self._access_token = token
                return token
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                raise AuthenticationUnavailableError("Keycloak administration is unavailable.") from error

    async def _request(self, method: str, path: str, *, body=None, params=None) -> httpx.Response:
        try:
            token = await self._token()
            async with httpx.AsyncClient(base_url=self.url, timeout=5) as client:
                response = await client.request(method, f"/admin/realms/{self.realm}{path}",
                    json=body, params=params, headers={"Authorization": f"Bearer {token}"})
            if response.status_code == 404:
                raise UserNotFoundError("Account not found.")
            if response.status_code == 409:
                raise UserAlreadyExistsError("Username or email already exists.")
            response.raise_for_status()
            return response
        except httpx.HTTPError as error:
            raise AuthenticationUnavailableError("Keycloak administration is unavailable.") from error

    async def _json(self, path: str, *, params=None):
        response = await self._request("GET", path, params=params)
        try:
            return response.json()
        except ValueError as error:
            raise AuthenticationUnavailableError("Invalid identity response.") from error

    async def get_user(self, user_id: UUID) -> CurrentUserResponse:
        data = await self._json(f"/users/{user_id}")
        try:
            return CurrentUserResponse.model_validate(data)
        except ValidationError as error:
            raise AuthenticationUnavailableError("Invalid identity response.") from error

    async def roles(self, user_id: UUID, *, effective: bool = True) -> list[dict]:
        suffix = "/composite" if effective else ""
        roles = await self._json(f"/users/{user_id}/role-mappings/realm{suffix}")
        if not isinstance(roles, list) or any(
            not isinstance(role, dict) or not isinstance(role.get("name"), str)
            or not isinstance(role.get("id"), str) for role in roles
        ):
            raise AuthenticationUnavailableError("Invalid role response.")
        return roles

    async def role_members(self, role: str, *, first: int = 0, max_results: int = 100) -> list[dict]:
        users = await self._json(f"/roles/{quote(role, safe='')}/users",
            params={"first": first, "max": max_results})
        if not isinstance(users, list) or any(not isinstance(user, dict) for user in users):
            raise AuthenticationUnavailableError("Invalid identity response.")
        return users

    async def accounts(self, *, first: int = 0, max_results: int = 100) -> list[dict]:
        # Role-member endpoints omit users who inherit roles through composites.
        users = await self._json("/users", params={"first": first, "max": max_results})
        if not isinstance(users, list) or any(not isinstance(user, dict) for user in users):
            raise AuthenticationUnavailableError("Invalid identity response.")
        return users

    async def managed_user(self, user_id: UUID) -> ManagedUserResponse:
        roles = {role["name"] for role in await self.roles(user_id)}
        if "admin_manager" in roles or not roles.intersection({"user", "admin"}):
            raise UserNotFoundError("Managed user not found.")
        profile = await self.get_user(user_id)
        return ManagedUserResponse(user_id=user_id, **profile.model_dump(),
            role="admin" if "admin" in roles else "user")

    async def set_managed_role(self, user_id: UUID, role: str) -> ManagedUserResponse:
        if role not in {"user", "admin"}:
            raise ValueError("Only user and admin roles can be managed")
        await self.managed_user(user_id)  # Includes inherited manager-role protection.
        direct = await self.roles(user_id, effective=False)
        effective = await self.roles(user_id)
        if role == "user" and any(r["name"] == "admin" for r in effective) and not any(
            r["name"] == "admin" for r in direct
        ):
            raise UserAlreadyExistsError("Inherited administrator access must be changed in Keycloak.")
        desired = await self._json(f"/roles/{role}")
        if not isinstance(desired, dict) or desired.get("name") != role or not desired.get("id"):
            raise AuthenticationUnavailableError("Invalid role response.")
        path = f"/users/{user_id}/role-mappings/realm"
        await self._request("POST", path, body=[desired])
        remove = [r for r in direct if r["name"] in {"user", "admin"} and r["name"] != role]
        if remove:
            await self._request("DELETE", path, body=remove)
        # No forced logout: existing tokens expire within five minutes.
        user = await self.managed_user(user_id)
        if user.role != role:
            raise UserAlreadyExistsError("Inherited administrator access must be changed in Keycloak.")
        return user

    async def bootstrap_manager(self, username: str, email: str, password: str) -> None:
        response = await self._request("POST", "/users", body={
            "username": username, "email": email, "enabled": False,
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        })
        try:
            user_id = UUID(response.headers["Location"].rstrip("/").rsplit("/", 1)[1])
        except (KeyError, ValueError) as error:
            raise AuthenticationUnavailableError("Invalid account creation response.") from error
        desired = await self._json("/roles/admin_manager")
        if not isinstance(desired, dict) or desired.get("name") != "admin_manager" or not desired.get("id"):
            raise AuthenticationUnavailableError("Invalid bootstrap role response.")
        await self._request("POST", f"/users/{user_id}/role-mappings/realm", body=[desired])
        await self._request("PUT", f"/users/{user_id}", body={"enabled": True})
        # On failure leave the new account disabled for operator reconciliation.
        # Never adopt an existing username or delete an identity as compensation.


@lru_cache
def get_keycloak_admin() -> KeycloakAdmin:
    return KeycloakAdmin(
        settings.keycloak_server_url, settings.keycloak_realm,
        settings.keycloak_backend_client_id,
        settings.keycloak_backend_client_secret.get_secret_value()
        if settings.keycloak_backend_client_secret else "",
    )
