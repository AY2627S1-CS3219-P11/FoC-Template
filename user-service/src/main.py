from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from common.config_manager import settings
from auth.views import router as authentication_router


app = FastAPI(title=settings.app_name)


@app.exception_handler(RequestValidationError)
async def invalid_request_handler(_request, _exception):
    return JSONResponse(status_code=422, content={"message": "Invalid request."})


app.include_router(authentication_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)
