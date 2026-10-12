import pytest
from pydantic import SecretStr

from common.config_manager import settings


@pytest.mark.anyio
async def test_legacy_signup_login_profile_and_logout(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_provider", "legacy")
    monkeypatch.setattr(settings, "access_token_secret", SecretStr("test-only-secret-" * 4))
    credentials = {"email": "new@example.com", "password": "Password123"}
    response = await client.post("/authentication/users", json=credentials | {"username": "new-user"})
    assert response.status_code == 201
    response = await client.post("/authentication/sessions", json=credentials)
    assert response.status_code == 200
    token = client.cookies.get("access_token")
    assert token
    assert (await client.get("/authentication/sessions/current")).status_code == 200
    response = await client.get("/authentication/users/current")
    assert response.json() == {"username": "new-user", "email": "new@example.com"}
    response = await client.patch("/authentication/users/current", json={"username": "renamed"})
    assert response.status_code == 200
    assert response.json()["username"] == "renamed"
    assert (await client.delete("/authentication/sessions/current")).status_code == 204
    response = await client.get("/authentication/sessions/current", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
