import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orders.repository import (
    dispute_overdue_orders,
    expire_initializing_orders,
    expire_orders,
)

logger = logging.getLogger("uvicorn.error")


async def expiry_worker(session_factory: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            async with session_factory() as session:
                initializing_ids = await expire_initializing_orders(session)
                expired_ids = await expire_orders(session)
                expired_ids.extend(initializing_ids)
                disputed_ids = await dispute_overdue_orders(session)
            if disputed_ids:
                logger.info("Disputed %d overdue orders", len(disputed_ids))
            if expired_ids:
                logger.info("Expired %d orders", len(expired_ids))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Expiry worker failed")
        await asyncio.sleep(10)
