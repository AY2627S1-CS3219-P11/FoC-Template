import asyncio
from uuid import uuid4

import aio_pika
from aio_pika.abc import AbstractExchange, AbstractIncomingMessage
from pamqp.commands import Basic
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from credit.models import CreditAccountsSyncRequested, UserCreated
from credit.service import create_credit_account


async def request_credit_account_sync(exchange: AbstractExchange) -> None:
    event = CreditAccountsSyncRequested(event="CreditAccountsSyncRequested")
    try:
        async with asyncio.timeout(5):
            confirmation = await exchange.publish(
                aio_pika.Message(
                    body=event.model_dump_json().encode("utf-8"),
                    content_type="application/json",
                    type="CreditAccountsSyncRequested",
                    message_id=str(uuid4()),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key="credit.accounts.sync.requested",
                mandatory=True,
            )
        if not isinstance(confirmation, Basic.Ack):
            raise RuntimeError("RabbitMQ did not confirm credit account reconciliation")
    except Exception:
        raise RuntimeError("Could not request credit account reconciliation") from None
    print("Credit account reconciliation requested; missing accounts will be initialized asynchronously.")


async def consume_user_created(
    message: AbstractIncomingMessage,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        event = UserCreated.model_validate_json(message.body)
    except ValidationError:
        print("Invalid UserCreated event; message rejected without requeue.")
        await message.reject(requeue=False)
        return

    try:
        async with session_factory() as session:
            await create_credit_account(session, event)
        await message.ack()
    except Exception as error:
        print(
            f"UserCreated processing failed ({type(error).__name__}); "
            "message will be requeued for retry."
        )
        await asyncio.sleep(2)
        try:
            await message.nack(requeue=True)
        except Exception:
            print("Could not requeue UserCreated; unacknowledged delivery awaits broker recovery.")
