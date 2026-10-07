import asyncio

from aio_pika.abc import AbstractIncomingMessage
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from credit.models import UserCreated
from credit.repository import create_credit_account


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
