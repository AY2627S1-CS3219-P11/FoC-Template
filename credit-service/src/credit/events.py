import asyncio
from uuid import uuid4

import aio_pika
from aio_pika.abc import AbstractExchange, AbstractIncomingMessage, AbstractChannel
from pamqp.commands import Basic
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from credit.models import CreditAccountsSyncRequested, UserCreated, ReleaseCreditCommand, ReserveCreditCommand, TransferCreditCommand
from credit.service import create_credit_account, release_credits, reserve_credits,transfer_credits
from credit.exceptions import CreditNotFoundError, CreditReservationConflictError, CreditReservationNotFoundError, InsufficientCreditsError

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



async def consume_reserve_credit(
    message: AbstractIncomingMessage,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        command = ReserveCreditCommand.model_validate_json(message.body)
    except ValidationError:
        print("Invalid ReserveCreditCommand payload; message rejected without requeue.")
        await message.reject(requeue=False)
        return

    try:
        async with session_factory() as session:
            await reserve_credits(
                session=session,
                order_id=command.order_id,
                requester_id=command.requester_id,
                amount=command.amount,
            )
        await message.ack()
    except (InsufficientCreditsError, CreditReservationConflictError, CreditNotFoundError, ValueError) as error:
        print(f"Reserve credit rejected due to domain validation ({type(error).__name__}): {error}")
        await message.reject(requeue=False)
    except Exception as error:
        print(f"Reserve credit failed ({type(error).__name__}); message will be requeued for retry.")
        await asyncio.sleep(2)
        try:
            await message.nack(requeue=True)
        except Exception:
            print("Could not requeue ReserveCreditCommand; delivery awaits broker recovery.")


async def consume_release_credit(
    message: AbstractIncomingMessage,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        command = ReleaseCreditCommand.model_validate_json(message.body)
    except ValidationError:
        print("Invalid ReleaseCreditCommand payload; message rejected without requeue.")
        await message.reject(requeue=False)
        return

    try:
        async with session_factory() as session:
            await release_credits(session=session, order_id=command.order_id)
        await message.ack()
    except (CreditReservationNotFoundError, CreditReservationConflictError, CreditNotFoundError) as error:
        print(f"Release credit rejected due to domain error ({type(error).__name__}): {error}")
        await message.reject(requeue=False)
    except Exception as error:
        print(f"Release credit failed ({type(error).__name__}); message will be requeued for retry.")
        await asyncio.sleep(2)
        try:
            await message.nack(requeue=True)
        except Exception:
            print("Could not requeue ReleaseCreditCommand; delivery awaits broker recovery.")


async def consume_transfer_credit(
    message: AbstractIncomingMessage,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        command = TransferCreditCommand.model_validate_json(message.body)
    except ValidationError:
        print("Invalid TransferCreditCommand payload; message rejected without requeue.")
        await message.reject(requeue=False)
        return

    try:
        async with session_factory() as session:
            await transfer_credits(
                session=session,
                order_id=command.order_id,
                courier_id=command.courier_id,
            )
        await message.ack()
    except (CreditReservationNotFoundError, CreditReservationConflictError, CreditNotFoundError, ValueError) as error:
        print(f"Transfer credit rejected due to domain validation ({type(error).__name__}): {error}")
        await message.reject(requeue=False)
    except Exception as error:
        print(f"Transfer credit failed ({type(error).__name__}); message will be requeued for retry.")
        await asyncio.sleep(2)
        try:
            await message.nack(requeue=True)
        except Exception:
            print("Could not requeue TransferCreditCommand; delivery awaits broker recovery.")


async def setup_credit_command_consumers(
    channel: AbstractChannel,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    exchange = await channel.declare_exchange(
        name="credit_commands",
        type=aio_pika.ExchangeType.DIRECT,
        durable=True,
    )

    queue = await channel.declare_queue("credit_service_commands_queue", durable=True)

    routing_key_map = {
        "credit.reserve": consume_reserve_credit,
        "credit.release": consume_release_credit,
        "credit.transfer": consume_transfer_credit,
    }

    for routing_key in routing_key_map:
        await queue.bind(exchange, routing_key=routing_key)

    async def on_message(message: AbstractIncomingMessage) -> None:
        handler = routing_key_map.get(message.routing_key)
        if handler:
            await handler(message, session_factory)
        else:
            print(f"Unhandled routing key '{message.routing_key}'; rejecting without requeue.")
            await message.reject(requeue=False)

    await queue.consume(on_message)
    print("Registered listeners for credit.reserve, credit.release, and credit.transfer.")