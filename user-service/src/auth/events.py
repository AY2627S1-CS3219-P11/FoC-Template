import asyncio
from uuid import UUID

import aio_pika
from aio_pika.abc import AbstractExchange
from pamqp.commands import Basic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth.orm_models import UserCreatedOutbox


async def publish_pending_user_events(
    session_factory: async_sessionmaker[AsyncSession],
    exchange: AbstractExchange,
    user_id: UUID | None = None,
) -> None:
    try:
        for _ in range(1 if user_id is not None else 100):
            async with session_factory.begin() as session:
                statement = (
                    select(UserCreatedOutbox)
                    .order_by(UserCreatedOutbox.user_id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                if user_id is not None:
                    statement = statement.where(UserCreatedOutbox.user_id == user_id)
                pending = await session.scalar(statement)
                if pending is None:
                    return

                async with asyncio.timeout(5):
                    confirmation = await exchange.publish(
                        aio_pika.Message(
                            body=pending.payload.encode("utf-8"),
                            content_type="application/json",
                            type="UserCreated",
                            message_id=str(pending.user_id),
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        ),
                        routing_key="user.created",
                        mandatory=True,
                    )
                if not isinstance(confirmation, Basic.Ack):
                    raise RuntimeError("RabbitMQ did not confirm UserCreated delivery")
                await session.delete(pending)
    except Exception as error:
        print(
            f"UserCreated publication failed ({type(error).__name__}); "
            "pending event retained for retry."
        )


async def run_user_event_publisher(
    session_factory: async_sessionmaker[AsyncSession],
    exchange: AbstractExchange,
) -> None:
    while True:
        await publish_pending_user_events(session_factory, exchange)
        await asyncio.sleep(2)
