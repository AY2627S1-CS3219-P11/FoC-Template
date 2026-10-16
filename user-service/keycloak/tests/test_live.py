"""Opt-in checks against a disposable Keycloak realm; never use production."""

import base64
import hashlib
import html
import os
import re
from urllib.parse import parse_qs, urlsplit
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest

from auth.exceptions import UserNotFoundError
from auth.keycloak import KeycloakAdmin
from auth.tokens import KeycloakTokenValidator
from auth import service
from test_configure import configure


@pytest.mark.anyio
async def test_default_role_accounts_and_manager_protection(monkeypatch):
    env_file = os.environ.get("FOC_KEYCLOAK_TEST_ENV")
    url = os.environ.get("FOC_KEYCLOAK_TEST_URL")
    if not env_file or not url:
        pytest.skip("Set FOC_KEYCLOAK_TEST_ENV and FOC_KEYCLOAK_TEST_URL for disposable infrastructure")
    values = configure.load_env(Path(env_file))
    adapter = KeycloakAdmin(url, "foc", "foc-backend", values["KEYCLOAK_BACKEND_CLIENT_SECRET"])
    monkeypatch.setattr(service, "get_keycloak_admin", lambda: adapter)
    created = []
    suffix = uuid4().hex
    try:
        response = await adapter._request("POST", "/users", body={
            "username": f"review-{suffix}", "email": f"review-{suffix}@example.org", "enabled": True,
        })
        user_id = UUID(response.headers["Location"].rsplit("/", 1)[1])
        created.append(user_id)
        assert "user" in {r["name"] for r in await adapter.roles(user_id)}
        assert "user" not in {r["name"] for r in await adapter.roles(user_id, effective=False)}
        # Raw account pagination must include users with inherited application roles.
        offset = 0
        listed = []
        while True:
            page = await service.get_users_for_access_management("user", None, offset, 2)
            listed.extend(user.user_id for user in page.items)
            if not page.has_more:
                break
            offset += page.limit
        assert user_id in listed
        assert (await adapter.set_managed_role(user_id, "admin")).role == "admin"
        password = uuid4().hex + "Aa1!"
        await adapter._request("PUT", f"/users/{user_id}/reset-password", body={
            "type": "password", "value": password, "temporary": False,
        })
        verifier = uuid4().hex + uuid4().hex
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        redirect = "http://localhost:4173/"
        async with httpx.AsyncClient() as browser:
            login = await browser.get(url + "/realms/foc/protocol/openid-connect/auth", params={
                "client_id": "foc-ui", "response_type": "code", "scope": "openid",
                "redirect_uri": redirect, "code_challenge": challenge, "code_challenge_method": "S256",
            })
            assert login.status_code == 200
            # Browsers allow Secure cookies on localhost HTTP; httpx does not.
            if urlsplit(url).hostname == "localhost" and urlsplit(url).scheme == "http":
                for cookie in browser.cookies.jar:
                    cookie.secure = False
            action = html.unescape(re.search(r'<form[^>]+action="([^"]+)"', login.text).group(1))
            authenticated = await browser.post(action, data={"username": f"review-{suffix}", "password": password})
            assert authenticated.status_code == 302
            code = parse_qs(urlsplit(authenticated.headers["Location"]).query)["code"][0]
            response = await browser.post(url + "/realms/foc/protocol/openid-connect/token", data={
                "grant_type": "authorization_code", "client_id": "foc-ui", "code": code,
                "redirect_uri": redirect, "code_verifier": verifier,
            })
            assert response.status_code == 200
            tokens = response.json()
        validator = KeycloakTokenValidator(url + "/realms/foc", "foc-api")
        assert validator.validate(tokens["access_token"]).role == "admin"
        assert tokens["expires_in"] <= 300
        assert (await adapter.set_managed_role(user_id, "user")).role == "user"
        await adapter._request("POST", f"/users/{user_id}/logout")
        # Demotion and logout cannot revoke an already-issued offline JWT.
        assert validator.validate(tokens["access_token"]).role == "admin"
        manager_role = await adapter._json("/roles/admin_manager")
        await adapter._request("POST", f"/users/{user_id}/role-mappings/realm", body=[manager_role])
        with pytest.raises(UserNotFoundError):
            await adapter.set_managed_role(user_id, "admin")
    finally:
        for user_id in created:
            await adapter._request("DELETE", f"/users/{user_id}")
