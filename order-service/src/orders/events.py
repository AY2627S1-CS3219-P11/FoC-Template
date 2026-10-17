import asyncio
import logging

from aio_pika.abc import AbstractIncomingMessage
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orders.models import CreditOperationOutcome, CreditOperationResult
from orders.repository import apply_credit_result


logger = logging.getLogger("uvicorn.error")


async def consume_credit_result(message: AbstractIncomingMessage, session_factory: async_sessionmaker[AsyncSession],) -> None:
    try:
        result = CreditOperationResult.model_validate_json(message.body)
    except ValidationError:
        logger.warning("Invalid CreditOperationResult; rejecting without requeue")
        await message.reject(requeue=False)
        return

    try:
        async with session_factory.begin() as session:
            await apply_credit_result(session, result)
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
    if result.outcome == CreditOperationOutcome.REJECTED:
        logger.error(
            "Credit %s rejected for order %s, request %s: %s",
            result.operation, result.order_id, result.request_id, result.reason,)
    else:
        logger.info(
            "Processed Credit %s result for order %s, request %s",
            result.operation, result.order_id, result.request_id,)
