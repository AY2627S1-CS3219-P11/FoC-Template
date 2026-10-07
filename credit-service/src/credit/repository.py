from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from credit.models import UserCreated
from credit.orm_models import Credit


async def create_credit_account(session: AsyncSession, event: UserCreated) -> None:
    statement = insert(Credit).values(
        user_id=event.user_id,
        available_credits=100,
        reserved_credits=0,
        created_at=event.created_at,
        updated_at=event.created_at,
    ).on_conflict_do_nothing(index_elements=[Credit.user_id])
    await session.execute(statement)
    await session.commit()
