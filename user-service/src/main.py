from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import async_sessionmaker


from common.db import get_engine
from common.config_manager import settings
from auth.bootstrap import provision_admin_manager
from auth.orm_models import Base
from auth.models import PASSWORD_REQUIREMENTS_MESSAGE
from auth.views import router as authentication_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False,) # creates admin manager

    async with session_factory() as session:
        await provision_admin_manager(session)

    yield

    await engine.dispose()

app = FastAPI(title=settings.app_name, lifespan=lifespan,)


@app.exception_handler(RequestValidationError)
async def invalid_request_handler(request: Request, exception: RequestValidationError):
    if request.url.path.endswith("/authentication/users") and any(
        error.get("loc") == ("body", "password") for error in exception.errors()
    ):
        return JSONResponse(status_code=422, content={"message": PASSWORD_REQUIREMENTS_MESSAGE})
    return JSONResponse(status_code=422, content={"message": "Invalid request."})


app.include_router(authentication_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)
