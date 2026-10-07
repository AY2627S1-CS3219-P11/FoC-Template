import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from functools import partial

import aio_pika
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker

from common.config_manager import settings
from common.db import get_engine
from credit.events import consume_user_created
from credit.orm_models import Base
from credit.views import router as credit_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.rabbitmq_url is None or not settings.rabbitmq_url.get_secret_value():
        raise RuntimeError("RABBITMQ_URL is not configured")

    engine = get_engine()
    async with AsyncExitStack() as resources:
        resources.push_async_callback(engine.dispose)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

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

        user_exchange = await rmq_channel.declare_exchange(
            "user_events", aio_pika.ExchangeType.DIRECT, durable=True,
        )
        await rmq_channel.set_qos(prefetch_count=1)

        queue = await rmq_channel.declare_queue(
            "credit_user_created", durable=True, exclusive=False,
        )
        await queue.bind(user_exchange, routing_key="user.created")

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        consumer_tag = await queue.consume(
            partial(consume_user_created, session_factory=session_factory), no_ack=False,
        )
        resources.push_async_callback(queue.cancel, consumer_tag)

        app.state.rmq_connection = rmq_connection
        app.state.rmq_channel = rmq_channel
        app.state.user_exchange = user_exchange

        yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(credit_router)
