import asyncio
import logging
from datetime import datetime, timedelta, timezone

import aio_pika
from aio_pika.abc import AbstractExchange
from pamqp.commands import Basic
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from common.config_manager import settings
from orders.models import COMMAND_MODELS
from orders.repository import find_pending_credit_command


logger = logging.getLogger("uvicorn.error")


async def publish_outbox_messages(session_factory: async_sessionmaker[AsyncSession], exchange: AbstractExchange,) -> None:
    while True:
        try:
            attempted = await publish_next_outbox_message(session_factory, exchange)

            if not attempted:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Order outbox publisher failed")
            await asyncio.sleep(2)


async def publish_next_outbox_message(session_factory: async_sessionmaker[AsyncSession], exchange: AbstractExchange,) -> bool:
    async with session_factory.begin() as session:
        outbox_message = await find_pending_credit_command(
            session, settings.credit_result_timeout_seconds,)
        
        if outbox_message is None:
            return False

        replay = outbox_message.published_at is not None

        try:
            command = COMMAND_MODELS[outbox_message.routing_key].model_validate(outbox_message.payload)

            if command.request_id != outbox_message.id or command.order_id != outbox_message.order_id:
                raise ValueError("Outbox payload does not match its stored identifiers")
            
            confirmation = await exchange.publish(
                aio_pika.Message(
                    body=command.model_dump_json().encode("utf-8"),
                    content_type="application/json",
                    type=outbox_message.routing_key,
                    message_id=str(command.request_id),
                    correlation_id=str(command.request_id),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,),
                routing_key=outbox_message.routing_key,
                mandatory=True,
                timeout=5,
            )
            if not isinstance(confirmation, Basic.Ack):
                raise RuntimeError("RabbitMQ did not confirm credit command publication")
            
        except Exception as error:
            outbox_message.attempts += 1
            delay_seconds = 2 ** min(outbox_message.attempts, 8)
            outbox_message.available_at = datetime.now(timezone.utc) + timedelta(
                seconds=delay_seconds,
            )
            outbox_message.last_error = f"{type(error).__name__}: {error}"[:2000]
            logger.warning(
                "Could not publish order outbox message %s; retrying in %s seconds",
                outbox_message.id,
                delay_seconds,
                exc_info=True,
            )
        else:
            # Replaying an unresolved request asks Credit for its saved
            # outcome, request ID prevents another credit action
            outbox_message.published_at = await session.scalar(select(func.clock_timestamp()))
            outbox_message.last_error = None
            logger.info(
                "%s credit command %s for order %s (%s)",
                "Replayed unresolved" if replay else "Published",
                outbox_message.id, outbox_message.order_id, outbox_message.routing_key,
            )
    return True
