from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from common.config_manager import settings
from orders.bootstrap import initialize_order_service
from orders.views import router as order_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with initialize_order_service():
        yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(order_router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "order-service",
    }
