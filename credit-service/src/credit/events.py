import asyncio
from contextlib import suppress
from uuid import uuid4

import aio_pika
from aio_pika.abc import AbstractExchange, AbstractIncomingMessage
from pamqp.commands import Basic
from pydantic import ValidationError
from sqlalchemy.exc import (
    DBAPIError,
    InterfaceError,
    OperationalError,
    TimeoutError as PoolTimeoutError,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from common.config_manager import settings
from credit.exceptions import (
    CreditConsistencyError,
    CreditNotFoundError,
    CreditReservationNotFoundError,
    CreditRequestConflictError,
)
from credit.models import (
    CreditAccountsSyncRequested,
    CreditCommandFailureReason,
    MessageHeader,
    MessageType,
    QueueName,
    ReleaseCreditCommand,
    ReserveCreditCommand,
    RoutingKey,
    TransferCreditCommand,
    UserCreated,
    CreditCommand,
    CreditOperationResult,
    CreditOperationOutcome,
    CreditRejectionReason,
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
    failed_exchange: AbstractExchange,
    result_exchange: AbstractExchange,
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
    except CreditRequestConflictError:
        print(
            f"Credit request {credit_command.request_id} reused for another command; "
            "message rejected without requeue."
        )
        await message.reject(requeue=False)
    except Exception as error:
        print(
            f"Credit {credit_command.operation} {credit_command.request_id} "
            f"processing failed ({type(error).__name__})."
        )
        await _retry_or_retain_credit_command(
            message, command_exchange, failed_exchange, result_exchange, credit_command, error,
        )
    else:
        try:
            await message.ack()
            print(f"Credit {outcome.operation} {outcome.request_id}: {outcome.outcome}.")
        except Exception as error:
            print(
                f"Credit {outcome.request_id} committed; acknowledgement failed "
                f"({type(error).__name__})."
            )
            if not message.processed:
                with suppress(Exception):
                    await message.nack(requeue=True)


def _is_temporary_credit_failure(error: Exception) -> bool:
    if isinstance(error, (
        CreditNotFoundError, CreditReservationNotFoundError, PoolTimeoutError, TimeoutError,
    )):
        return True
    if not isinstance(error, DBAPIError):
        return False

    sqlstate = getattr(error.orig, "sqlstate", None)
    if error.connection_invalidated:
        return True
    if sqlstate is None:
        return isinstance(error, (OperationalError, InterfaceError))
    return sqlstate.startswith("08") or sqlstate in {
        "40001", "40P01", "55P03", "57P01", "57P02", "57P03", "53300",
    }


# retry temporary gaps within the limit else retain the command for review
async def _retry_or_retain_credit_command(
        message: AbstractIncomingMessage,
        command_exchange: AbstractExchange,
        failed_exchange: AbstractExchange,
        result_exchange: AbstractExchange,
        credit_command: CreditCommand,
        error: Exception,
) -> None:
    headers = dict(message.headers)
    retry_count = message.headers.get(MessageHeader.RETRY_COUNT, 0)
    temporary = _is_temporary_credit_failure(error)
    reason = None

    if temporary and type(retry_count) is int and 0 <= retry_count < settings.credit_command_max_retries:
        await asyncio.sleep(2)
        headers[MessageHeader.RETRY_COUNT] = retry_count + 1
        exchange, routing_key = command_exchange, message.routing_key
    else:
        if not temporary:
            reason = (
                CreditCommandFailureReason.INCONSISTENT_CREDITS
                if isinstance(error, CreditConsistencyError)
                else CreditCommandFailureReason.NON_RETRYABLE_ERROR
            )
        elif type(retry_count) is not int or retry_count < 0:
            reason = CreditCommandFailureReason.INVALID_RETRY_METADATA
        else:
            reason = CreditCommandFailureReason.RETRIES_EXHAUSTED

        headers[MessageHeader.ORIGINAL_ROUTING_KEY] = message.routing_key
        headers[MessageHeader.FAILURE_REASON] = reason
        headers[MessageHeader.ERROR_TYPE] = type(error).__name__
        exchange, routing_key = failed_exchange, QueueName.CREDIT_FAILED_COMMANDS

        # Send failure event to Order since the command will not be processed
        outcome = CreditOperationResult(
            **credit_command.model_dump(),
            operation=credit_command.operation,
            outcome=CreditOperationOutcome.REJECTED,
            reason=CreditRejectionReason.INVALID_OPERATION,
        )
        try:
            await result_exchange.publish(
                aio_pika.Message(
                    body=outcome.model_dump_json().encode("utf-8"),
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=RoutingKey.CREDIT_OPERATION_RESULT,
                mandatory=True,
                timeout=5,
            )
        except Exception as pub_error:
            print(f"Could not publish failure event to Order service: {type(pub_error).__name__}")

    try:
        confirmation = await exchange.publish(
            aio_pika.Message(
                body=message.body,
                content_type=message.content_type or "application/json",
                type=message.type,
                message_id=message.message_id,
                correlation_id=message.correlation_id,
                headers=headers,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
            mandatory=True,
            timeout=5,
        )
        if not isinstance(confirmation, Basic.Ack):
            raise RuntimeError("RabbitMQ did not confirm the credit command handoff.")
        await message.ack()
        if reason is not None:
            print(f"Credit command retained in {QueueName.CREDIT_FAILED_COMMANDS} ({reason}).")
    except Exception as error:
        print(f"Credit command handoff failed ({type(error).__name__}); delivery retained.")
        if not message.processed:
            with suppress(Exception):
                await message.nack(requeue=True)
