import json
import os
from typing import Annotated
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import jwt
from fastapi import Cookie, HTTPException


def require_user_id(
    access_token: Annotated[str | None, Cookie()] = None,
) -> str:
    """Verify the access token locally and return its user ID."""
    if not access_token:
        raise HTTPException(401, "No authentication token found. Please sign in.")

    secret = os.getenv("ACCESS_TOKEN_SECRET")
    if secret is None or len(secret.encode("utf-8")) < 32:
        raise HTTPException(503, "Authentication is temporarily unavailable.")

    try:
        payload = jwt.decode(
            access_token,
            secret,
            algorithms=["HS256"],
            options={"require": ["sub", "email", "tokenType", "iat", "exp"]},
        )
        user_id = payload["sub"]
        if not isinstance(user_id, str) or not user_id or payload["tokenType"] != "access":
            raise jwt.InvalidTokenError()
    except (jwt.InvalidTokenError, KeyError):
        raise HTTPException(401, "Invalid or expired token. Please sign in.") from None
    return user_id


def require_user_identity(
    access_token: Annotated[str | None, Cookie()] = None,
) -> dict[str, str]:
    """Ask user-service for the user ID and current database role."""
    if not access_token:
        raise HTTPException(401, "No authentication token found. Please sign in.")

    user_service_url = os.getenv("USER_SERVICE_URL")
    if not user_service_url:
        raise HTTPException(503, "Authentication is temporarily unavailable.")

    request = Request(
        f"{user_service_url.rstrip('/')}/authentication/sessions/current/role",
        headers={"Cookie": f"access_token={access_token}"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            user = json.loads(response.read())
            if (
                not isinstance(user, dict)
                or not isinstance(user.get("user_id"), str)
                or user.get("role") not in {"user", "admin", "admin_manager"}
            ):
                raise ValueError()
            return {"user_id": user["user_id"], "role": user["role"]}
    except HTTPError as error:
        if error.code == 401:
            raise HTTPException(401, "Invalid or expired token. Please sign in.") from None
        raise HTTPException(503, "Authentication is temporarily unavailable.") from None
    except (URLError, TimeoutError, ValueError):
        raise HTTPException(503, "Authentication is temporarily unavailable.") from None
