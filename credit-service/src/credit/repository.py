from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from common.config_manager import settings
from credit.models import CreditResponse, UserCreated
from credit.orm_models import Credit


async def find_credit_account_by_user_id(
    session: AsyncSession, user_id: UUID,
) -> CreditResponse | None:
    account = await session.get(Credit, user_id)
    if account is None:
        return None
    return CreditResponse.model_validate(account)


async def create_credit_account(session: AsyncSession, event: UserCreated) -> None:
    statement = insert(Credit).values(
        user_id=event.user_id,
        available_credits=settings.initial_credit_allocation,
        reserved_credits=0,
        created_at=event.created_at,
        updated_at=event.created_at,
    ).on_conflict_do_nothing(index_elements=[Credit.user_id])
    await session.execute(statement)
    await session.commit()
