import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from functools import partial
from typing import NamedTuple

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractExchange
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from credit.events import consume_user_created


class MessagingResources(NamedTuple):
    connection: AbstractConnection
    channel: AbstractChannel
    user_exchange: AbstractExchange


@asynccontextmanager
async def initialize_messaging(
    rabbitmq_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[MessagingResources]:
    async with AsyncExitStack() as resources:
        connection = None
        for attempt in range(10):
            try:
                connection = await aio_pika.connect_robust(rabbitmq_url, timeout=5)
                break
            except OSError:
                if attempt < 9:
                    await asyncio.sleep(2)

        if connection is None:
            raise RuntimeError("Could not connect to RabbitMQ")
        resources.push_async_callback(connection.close)

        channel = await connection.channel(
            publisher_confirms=True, on_return_raises=True,
        )
        resources.push_async_callback(channel.close)
        user_exchange = await channel.declare_exchange(
            "user_events", aio_pika.ExchangeType.DIRECT, durable=True,
        )
        await channel.set_qos(prefetch_count=1)

        user_created_queue = await channel.declare_queue(
            "credit_user_created", durable=True, exclusive=False,
        )
        await user_created_queue.bind(user_exchange, routing_key="user.created")
        consumer_tag = await user_created_queue.consume(
            partial(consume_user_created, session_factory=session_factory), no_ack=False,
        )
        resources.push_async_callback(user_created_queue.cancel, consumer_tag)

        # Ensure User's queue exists before publishing, even when User is offline.
        sync_request_queue = await channel.declare_queue(
            "credit_accounts_sync_requested", durable=True, exclusive=False,
        )
        await sync_request_queue.bind(
            user_exchange, routing_key="credit.accounts.sync.requested",
        )

        yield MessagingResources(connection, channel, user_exchange)
