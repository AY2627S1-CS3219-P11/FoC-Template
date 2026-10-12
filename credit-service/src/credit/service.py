from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from credit.exceptions import CreditNotFoundError
from credit.models import CreditResponse
from credit.repository import find_credit_account_by_user_id


async def get_current_credit_balance(user_id: UUID, session: AsyncSession) -> CreditResponse:
    account = await find_credit_account_by_user_id(session, user_id)
    if account is None:
        raise CreditNotFoundError("Credit account not found.")
    return account
