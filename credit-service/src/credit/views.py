from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import AuthenticatedUser
from common.db import get_session
from credit.exceptions import CreditNotFoundError
from credit.models import CreditAuditLogResponse, CreditResponse
from credit.service import get_credit_audit_logs, get_current_credit_balance


router = APIRouter(prefix="/credits", tags=["Credit"])


@router.get("/current")
async def get_current_credits(
    user: AuthenticatedUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CreditResponse:
    try:
        return await get_current_credit_balance(user.user_id, session)
    except CreditNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None


@router.get("/credit-audit-logs")
async def get_current_credit_audit_logs(
    user: AuthenticatedUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[CreditAuditLogResponse]:
    return await get_credit_audit_logs(user.user_id, session)
