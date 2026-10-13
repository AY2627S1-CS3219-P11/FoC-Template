from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from common.config_manager import settings
from credit.models import CreditResponse, UserCreated
from credit.orm_models import Credit, CreditAuditLog, CreditReservation


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


async def lock_credit_accounts(
    session: AsyncSession, user_ids: set[UUID],
) -> dict[UUID, Credit]:
    statement = (
        select(Credit)
        .where(Credit.user_id.in_(user_ids))
        .order_by(Credit.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    accounts = await session.scalars(statement)
    return {account.user_id: account for account in accounts}


async def find_credit_reservation(
    session: AsyncSession, order_id: UUID, *, for_update: bool = False,
) -> CreditReservation | None:
    statement = select(CreditReservation).where(CreditReservation.order_id == order_id)
    if for_update:
        statement = statement.with_for_update()
    return await session.scalar(statement.execution_options(populate_existing=True))


async def insert_credit_reservation(
    session: AsyncSession, order_id: UUID, user_id: UUID, amount: int,
) -> CreditReservation | None:
    statement = (
        insert(CreditReservation)
        .values(order_id=order_id, user_id=user_id, amount=amount, status="RESERVED")
        .on_conflict_do_nothing(index_elements=[CreditReservation.order_id])
        .returning(CreditReservation)
        .execution_options(populate_existing=True)
    )
    return await session.scalar(statement)


async def sum_active_reservations(session: AsyncSession, user_id: UUID) -> int:
    statement = select(func.coalesce(func.sum(CreditReservation.amount), 0)).where(
        CreditReservation.user_id == user_id,
        CreditReservation.status == "RESERVED",
    )
    return int(await session.scalar(statement))


async def find_credit_transfer(
    session: AsyncSession, order_id: UUID,
) -> CreditAuditLog | None:
    statement = select(CreditAuditLog).where(
        CreditAuditLog.order_id == order_id,
        CreditAuditLog.action == "TRANSFER",
    )
    return (await session.scalars(statement)).one_or_none()


def record_credit_transfer(
    session: AsyncSession, reservation: CreditReservation,
    recipient_user_id: UUID, created_at: datetime,
) -> None:
    session.add(CreditAuditLog(
        user_id=reservation.user_id,
        recipient_user_id=recipient_user_id,
        order_id=reservation.order_id,
        action="TRANSFER",
        amount=reservation.amount,
        created_at=created_at,
    ))
