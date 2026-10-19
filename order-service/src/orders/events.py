import asyncio
import logging

from aio_pika.abc import AbstractIncomingMessage
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orders.credit_results import (
    handle_release_result,
    handle_reservation_result,
    handle_transfer_result,
)
from orders.models import (
    CreditOperation,
    CreditResult,
)

logger = logging.getLogger("uvicorn.error")


async def consume_credit_result(
    message: AbstractIncomingMessage,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        result = CreditResult.model_validate_json(message.body)
    except ValidationError:
        logger.warning("Invalid CreditOperationResult; rejecting without requeue")
        await message.reject(requeue=False)
        return

    try:
        async with session_factory.begin() as session:
            match result.operation:
                case CreditOperation.RESERVE:
                    await handle_reservation_result(session, result)
                case CreditOperation.RELEASE:
                    await handle_release_result(session, result)
                case CreditOperation.TRANSFER:
                    await handle_transfer_result(session, result)
    except ValueError as error:
        logger.warning("Credit result %s rejected: %s", result.request_id, error)
        await message.reject(requeue=False)
        return
    except Exception:
        logger.exception("Credit result %s failed; retrying", result.request_id)
        await asyncio.sleep(2)
        await message.nack(requeue=True)
        return

    await message.ack()
    logger.info(
        "Credit reply processed and acknowledged: request=%s order=%s operation=%s",
        result.request_id,
        result.order_id,
        result.operation,
    )
