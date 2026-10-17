from fastapi import FastAPI

from common.config_manager import settings
from orders.views import router as order_router

app = FastAPI(title=settings.app_name)
app.include_router(order_router)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "order-service",
    }