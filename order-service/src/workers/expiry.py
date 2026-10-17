import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from orders.repository import expire_orders


logger = logging.getLogger("uvicorn.error")


async def expiry_worker(session_factory: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            async with session_factory() as session:
                expired_ids = await expire_orders(session)
            if expired_ids:
                logger.info("Expired %d orders", len(expired_ids))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Expiry worker failed")
        await asyncio.sleep(10)
