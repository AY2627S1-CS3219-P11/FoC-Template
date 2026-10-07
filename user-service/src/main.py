import asyncio
from contextlib import AsyncExitStack, asynccontextmanager, suppress

import aio_pika
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import async_sessionmaker

from auth.bootstrap import provision_admin_manager
from auth.events import run_user_event_publisher
from auth.orm_models import Base
from auth.models import PASSWORD_REQUIREMENTS_MESSAGE
from auth.views import router as authentication_router
from common.config_manager import settings
from common.db import get_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.rabbitmq_url is None or not settings.rabbitmq_url.get_secret_value():
        raise RuntimeError("RABBITMQ_URL is not configured")

    engine = get_engine()
    async with AsyncExitStack() as resources:
        resources.push_async_callback(engine.dispose)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            await provision_admin_manager(session)

        rmq_connection = None
        for attempt in range(10):
            try:
                rmq_connection = await aio_pika.connect_robust(
                    settings.rabbitmq_url.get_secret_value(), timeout=5,
                )
                break
            except (ConnectionRefusedError, OSError):
                if attempt < 9:
                    await asyncio.sleep(2)

        if rmq_connection is None:
            raise RuntimeError("Could not connect to RabbitMQ")

        resources.push_async_callback(rmq_connection.close)

        rmq_channel = await rmq_connection.channel(
            publisher_confirms=True, on_return_raises=True,
        )
        resources.push_async_callback(rmq_channel.close)

        user_exchange = await rmq_channel.declare_exchange(
            "user_events", aio_pika.ExchangeType.DIRECT, durable=True,
        )

        app.state.rmq_connection = rmq_connection
        app.state.rmq_channel = rmq_channel
        app.state.user_exchange = user_exchange
        app.state.session_factory = session_factory

        publisher = asyncio.create_task(run_user_event_publisher(session_factory, user_exchange))
        app.state.user_event_publisher = publisher
        try:
            yield
        finally:
            publisher.cancel()
            with suppress(asyncio.CancelledError):
                await publisher


app = FastAPI(title=settings.app_name, lifespan=lifespan,)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "user-service",
    }

@app.exception_handler(RequestValidationError)
async def invalid_request_handler(request: Request, exception: RequestValidationError):
    if request.url.path.endswith("/authentication/users") and any(
        error.get("loc") == ("body", "password") for error in exception.errors()
    ):
        return JSONResponse(status_code=422, content={"message": PASSWORD_REQUIREMENTS_MESSAGE})
    return JSONResponse(status_code=422, content={"message": "Invalid request."})


app.include_router(authentication_router)

# TODO(team): why do we have CORSMiddleware to 5173? 
# with ui container running on compose; we likely dont need this anymore
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)
