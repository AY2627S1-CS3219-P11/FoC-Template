from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from auth.bootstrap import provision_admin_manager
from auth.dependencies import get_keycloak_validator
from auth.exceptions import AuthenticationUnavailableError, UserAlreadyExistsError, UserNotFoundError
from auth.keycloak import get_keycloak_admin
from auth.views import router as authentication_router
from common.config_manager import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_keycloak_validator()
    get_keycloak_admin()
    await provision_admin_manager()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.exception_handler(AuthenticationUnavailableError)
async def authentication_unavailable(_request: Request, _exception: AuthenticationUnavailableError):
    return JSONResponse(status_code=503, content={"detail": "Authentication is temporarily unavailable."})


@app.exception_handler(UserNotFoundError)
async def identity_missing(_request: Request, exception: UserNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exception)})


@app.exception_handler(UserAlreadyExistsError)
async def identity_conflict(_request: Request, exception: UserAlreadyExistsError):
    return JSONResponse(status_code=409, content={"detail": str(exception)})


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "user-service"}


app.include_router(authentication_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
