from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from common.config_manager import settings
from credit.bootstrap import initialize_credit_service
from credit.views import router as credit_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with initialize_credit_service() as resources:
        app.state.rmq_connection = resources.connection
        app.state.rmq_channel = resources.channel
        app.state.user_exchange = resources.user_exchange
        yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "credit-service"}


@app.exception_handler(RequestValidationError)
async def invalid_request_handler(
    _request: Request, _exception: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"message": "Invalid request."})


@app.exception_handler(Exception)
async def unexpected_error_handler(
    _request: Request, _exception: Exception,
) -> JSONResponse:
    return JSONResponse(status_code=500, content={"message": "Internal server error."})


app.include_router(credit_router)
