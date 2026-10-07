import asyncio
from contextlib import AsyncExitStack, asynccontextmanager

import aio_pika
from fastapi import FastAPI
from sqlalchemy import text

from common.config_manager import settings
from common.db import get_engine
from credit.views import router as credit_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.rabbitmq_url is None or not settings.rabbitmq_url.get_secret_value():
        raise RuntimeError("RABBITMQ_URL is not configured")

    engine = get_engine()
    async with AsyncExitStack() as resources:
        resources.push_async_callback(engine.dispose)
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

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
        rmq_channel = await rmq_connection.channel()
        resources.push_async_callback(rmq_channel.close)

        app.state.rmq_connection = rmq_connection
        app.state.rmq_channel = rmq_channel
        yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(credit_router)
