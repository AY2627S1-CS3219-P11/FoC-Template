import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager, suppress

from sqlalchemy.ext.asyncio import async_sessionmaker

from common.config_manager import settings
from common.db import get_engine
from orders.messaging import MessagingResources, initialize_order_messaging
from orders.orm_models import Base
from workers.expiry import expiry_worker


@asynccontextmanager
async def initialize_order_service() -> AsyncIterator[MessagingResources]:
    if settings.rabbitmq_url is None or not settings.rabbitmq_url.get_secret_value():
        raise RuntimeError("RABBITMQ_URL is not configured")

    engine = get_engine()
    async with AsyncExitStack() as resources:
        resources.push_async_callback(engine.dispose)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with initialize_order_messaging(
            settings.rabbitmq_url.get_secret_value(), session_factory,
        ) as messaging:
            expiry_task = asyncio.create_task(expiry_worker(session_factory))
            try:
                yield messaging
            finally:
                expiry_task.cancel()
                with suppress(asyncio.CancelledError):
                    await expiry_task
