from fastapi import APIRouter


router = APIRouter(tags=["Credit"])


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "credit-service"}
