import asyncio
from uuid import uuid4

import aio_pika
from aio_pika.abc import AbstractExchange, AbstractIncomingMessage
from pamqp.commands import Basic
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from credit.exceptions import CreditRequestConflictError
from credit.models import (
    CreditAccountsSyncRequested,
    MessageType,
    ReleaseCreditCommand,
    ReserveCreditCommand,
    RoutingKey,
    TransferCreditCommand,
    UserCreated,
)
from credit.service import create_credit_account, process_credit_command


CREDIT_COMMAND_MODELS = {
    RoutingKey.CREDIT_RESERVE: ReserveCreditCommand,
    RoutingKey.CREDIT_RELEASE: ReleaseCreditCommand,
    RoutingKey.CREDIT_TRANSFER: TransferCreditCommand,
}


# Replay users so Credit can create missing accounts
async def request_credit_account_sync(exchange: AbstractExchange) -> None:
    event = CreditAccountsSyncRequested(event=MessageType.CREDIT_ACCOUNTS_SYNC_REQUESTED)
    try:
        async with asyncio.timeout(5):
            confirmation = await exchange.publish(
                aio_pika.Message(
                    body=event.model_dump_json().encode("utf-8"),
                    content_type="application/json",
                    type=event.event,
                    message_id=str(uuid4()),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=RoutingKey.CREDIT_ACCOUNTS_SYNC_REQUESTED,
                mandatory=True,
            )
        if not isinstance(confirmation, Basic.Ack):
            raise RuntimeError("RabbitMQ did not confirm credit account reconciliation")
    except Exception:
        raise RuntimeError("Could not request credit account reconciliation") from None
    print("Credit account reconciliation requested; missing accounts will be initialized asynchronously.")


# Create the credit account and initial allocation once
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


# Commit the outcome before acknowledging the command
async def consume_credit_command(
    message: AbstractIncomingMessage,
    session_factory: async_sessionmaker[AsyncSession],
    command_exchange: AbstractExchange,
) -> None:
    try:
        credit_command = CREDIT_COMMAND_MODELS[message.routing_key].model_validate_json(message.body)
    except ValidationError:
        print("Invalid credit command; message rejected without requeue.")
        await message.reject(requeue=False)
        return

    try:
        async with session_factory() as session:
            outcome = await process_credit_command(session, credit_command)
        await message.ack()
        print(f"Credit {outcome.operation} {outcome.request_id}: {outcome.outcome}.")
    except CreditRequestConflictError:
        print(
            f"Credit request {credit_command.request_id} reused for another command; "
            "message rejected without requeue."
        )
        await message.reject(requeue=False)
    except Exception as error:
        print(
            f"Credit {credit_command.operation} {credit_command.request_id} "
            f"processing failed ({type(error).__name__}); command will be retried."
        )
        await _retry_credit_command(message, command_exchange)


# Retry through the command exchange so queued commands can run first
async def _retry_credit_command(
    message: AbstractIncomingMessage,
    command_exchange: AbstractExchange,
) -> None:
    await asyncio.sleep(2)
    try:
        confirmation = await command_exchange.publish(
            aio_pika.Message(
                body=message.body,
                content_type=message.content_type or "application/json",
                type=message.type,
                message_id=message.message_id,
                correlation_id=message.correlation_id,
                headers=dict(message.headers),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=message.routing_key,
            mandatory=True,
            timeout=5,
        )
        if not isinstance(confirmation, Basic.Ack):
            raise RuntimeError("RabbitMQ did not confirm the credit retry.")
        await message.ack()
    except Exception as error:
        print(f"Credit retry publication failed ({type(error).__name__}); delivery retained.")
        if not message.processed:
            try:
                await message.nack(requeue=True)
            except Exception:
                print("Credit command awaits broker recovery as an unacknowledged delivery.")
