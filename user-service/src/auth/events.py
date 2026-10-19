import asyncio
from datetime import datetime, timezone

import aio_pika
from aio_pika.abc import AbstractExchange, AbstractIncomingMessage
from pamqp.commands import Basic
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth.models import (
    CreditAccountsSyncRequested,
    RoutingKey,
    UserCreated,
    UserCreatedOutboxResponse,
)
from auth.repository import enqueue_user_created_events, find_pending_user_event


async def consume_credit_accounts_sync_requested(
    message: AbstractIncomingMessage,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        CreditAccountsSyncRequested.model_validate_json(message.body)
    except ValidationError:
        print("Invalid credit account reconciliation request; message rejected without requeue.")
        await message.reject(requeue=False)
        return

    try:
        async with session_factory.begin() as session:
            await enqueue_user_created_events(session)
        await message.ack()
        print("Credit account reconciliation queued through the UserCreated outbox.")
    except Exception as error:
        print(
            f"Credit account reconciliation failed ({type(error).__name__}); "
            "request will be requeued for retry."
        )
        await asyncio.sleep(2)
        try:
            await message.nack(requeue=True)
        except Exception:
            print("Could not requeue reconciliation; unacknowledged delivery awaits broker recovery.")


async def publish_pending_user_events(
    session_factory: async_sessionmaker[AsyncSession],
    exchange: AbstractExchange,
) -> None:
    try:
        for _ in range(100):
            async with session_factory.begin() as session:
                pending = await find_pending_user_event(session)
                if pending is None:
                    return

                outbox_response = UserCreatedOutboxResponse.model_validate(pending)
                payload = UserCreated(
                    event=outbox_response.event,
                    user_id=outbox_response.user_id,
                    created_at=outbox_response.created_at,
                )
                async with asyncio.timeout(5):
                    confirmation = await exchange.publish(
                        aio_pika.Message(
                            body=payload.model_dump_json().encode("utf-8"),
                            content_type="application/json",
                            type=payload.event,
                            message_id=str(outbox_response.user_id),
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        ),
                        routing_key=RoutingKey.USER_CREATED,
                        mandatory=True,
                    )
                if not isinstance(confirmation, Basic.Ack):
                    raise RuntimeError("RabbitMQ did not confirm UserCreated delivery")

                pending.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
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
