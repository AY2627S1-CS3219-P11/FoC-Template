from fastapi import HTTPException, Request

from common.config_manager import settings


STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def validate_origin(request: Request) -> None:
    if request.method not in STATE_CHANGING_METHODS:
        return

    origin = request.headers.get("origin")
    if origin is not None and origin not in settings.cors_origins:
        raise HTTPException(status_code=403, detail="Origin is not allowed.")
    if origin is None and request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(status_code=403, detail="Origin is not allowed.")
