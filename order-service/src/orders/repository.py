from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from orders.deadlines import (
    init_window,
    progress_window,
    settlement_window,
)
from orders.models import (
    CreditCommand,
    ReleaseCreditCommand,
    TransferCreditCommand,
)
from orders.orm_models import (
    CreditCommandOutbox,
    CreditCommandResult,
    CreditStatus,
    ErrandRequest,
    Status,
    OrderAuditLog
)


async def find_pending_credit_command(session: AsyncSession, result_timeout_seconds: int,) -> CreditCommandOutbox | None:
    has_result = (select(CreditCommandResult.request_id)
                  .where(CreditCommandResult.request_id == CreditCommandOutbox.id)
                  .exists())
    
    retry_before = func.clock_timestamp() - timedelta(seconds=result_timeout_seconds)

    statement = (
        select(CreditCommandOutbox)
        .where(
            ~has_result,
            CreditCommandOutbox.available_at <= func.clock_timestamp(),
            or_(
                CreditCommandOutbox.published_at.is_(None),
                CreditCommandOutbox.published_at <= retry_before,
            ),)
        .order_by(CreditCommandOutbox.created_at, CreditCommandOutbox.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    
    return await session.scalar(statement)


async def get_open_orders(session: AsyncSession) -> list[ErrandRequest]:
    result = await session.execute(
        select(ErrandRequest)
        .where(
            ErrandRequest.status == Status.OPEN,
            ErrandRequest.expires_at > func.clock_timestamp(),
        )
        .order_by(ErrandRequest.created_at.desc())
    )

    return list(result.scalars().all())


async def get_order_by_id(session:AsyncSession, order_id: UUID) -> ErrandRequest | None:
    return await session.get(ErrandRequest, order_id)


async def get_requested_orders(session: AsyncSession, requester_id: UUID) -> list[ErrandRequest]:
    result = await session.execute(
        select(ErrandRequest)
        .where(ErrandRequest.requester_id == requester_id)
        .order_by(ErrandRequest.created_at.desc())
    )

    return list(result.scalars().all())


async def get_assigned_orders(session: AsyncSession, courier_id: UUID) -> list[ErrandRequest]:
    result = await session.execute(
        select(ErrandRequest)
        .where(ErrandRequest.courier_id == courier_id)
        .order_by(ErrandRequest.created_at.desc())
    )

    return list(result.scalars().all())


async def accept_order(session: AsyncSession, order_id: UUID, 
                        courier_id: UUID,) -> ErrandRequest | None:
    
    if not await _lock_order(session, order_id):
        await session.commit()
        return None
    
    now = (await session.execute(select(func.clock_timestamp()))).scalar_one()

    stmt = (update(ErrandRequest)
            .where(ErrandRequest.id == order_id,
                    ErrandRequest.status == Status.OPEN,
                    ErrandRequest.expires_at > now,
                    ErrandRequest.courier_id.is_(None),
                    ErrandRequest.requester_id != courier_id,)
            .values(status=Status.ACCEPTED,
                    courier_id=courier_id,
                    accepted_at=now,
                    progress_due_at=now + progress_window(),
                    updated_at=now,)
            .returning(ErrandRequest))

    result = await session.execute(stmt)
    order = result.scalar_one_or_none()

    await session.commit()

    return order


async def _lock_order(session: AsyncSession, order_id: UUID) -> bool:
    """Acquire the row lock before sampling the clock for deadline checks."""
    return await session.scalar(
        select(ErrandRequest.id)
        .where(ErrandRequest.id == order_id)
        .with_for_update()
    ) is not None


def record_order_audit_log(
        session: AsyncSession,
        order_id: UUID,
        action: Status,
        actor_id: UUID | None = None,
        reason: str | None = None,
) -> None:
    session.add(OrderAuditLog(
        order_id=order_id,
        actor_id=actor_id,
        action=action.value,
        reason=reason,
    ))


async def get_order_audit_logs(
        session: AsyncSession, order_id: UUID,
) -> list[OrderAuditLog]:
    statement = (
        select(OrderAuditLog)
        .where(OrderAuditLog.order_id == order_id)
        .order_by(OrderAuditLog.created_at.asc(), OrderAuditLog.log_id.asc())
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def accept_order(session: AsyncSession, order_id: UUID, courier_id: UUID) -> ErrandRequest | None:
    if not await _lock_order(session, order_id):
        await session.commit()
        return None

    now = (await session.execute(select(func.clock_timestamp()))).scalar_one()
    stmt = (update(ErrandRequest)
            .where(ErrandRequest.id == order_id, ErrandRequest.status == Status.OPEN,
                   ErrandRequest.expires_at > now, ErrandRequest.courier_id.is_(None),
                   ErrandRequest.requester_id != courier_id)
            .values(status=Status.ACCEPTED, courier_id=courier_id, accepted_at=now,
                    progress_due_at=now + progress_window(), updated_at=now)
            .returning(ErrandRequest))

    result = await session.execute(stmt)
    order = result.scalar_one_or_none()

    if order is not None:
        record_order_audit_log(session, order.id, Status.ACCEPTED, actor_id=courier_id)

    await session.commit()
    return order

async def pickup_order(session: AsyncSession, order_id: UUID,
                        courier_id: UUID,) -> ErrandRequest | None:
    if not await _lock_order(session, order_id):
        await session.commit()
        return None
    now = (await session.execute(select(func.clock_timestamp()))).scalar_one()

    stmt = (
        update(ErrandRequest)
        .where(ErrandRequest.id == order_id,
               ErrandRequest.status == Status.ACCEPTED,
               ErrandRequest.courier_id == courier_id,
               ErrandRequest.progress_due_at > now,)
        .values(status=Status.PICKED_UP,
                progress_due_at=now + progress_window(),
                updated_at=now,)
        .returning(ErrandRequest))

    result = await session.execute(stmt)
    order = result.scalar_one_or_none()

    if order is not None:
        record_order_audit_log(session, order.id, Status.PICKED_UP, actor_id=courier_id)

    await session.commit()

    return order


async def deliver_order(session: AsyncSession, order_id: UUID,
                         courier_id: UUID,) -> ErrandRequest | None:
    if not await _lock_order(session, order_id):
        await session.commit()
        return None
    now = (await session.execute(select(func.clock_timestamp()))).scalar_one()

    stmt = (
        update(ErrandRequest)
        .where(
            ErrandRequest.id == order_id,
            ErrandRequest.status == Status.PICKED_UP,
            ErrandRequest.courier_id == courier_id,
            ErrandRequest.progress_due_at > now,)
        .values(
            status=Status.DELIVERED,
            progress_due_at=now + progress_window(),
            updated_at=now,)
        .returning(ErrandRequest))

    result = await session.execute(stmt)
    order = result.scalar_one_or_none()

    if order is not None:
        record_order_audit_log(session, order.id, Status.DELIVERED, actor_id=courier_id)

    await session.commit()

    return order


async def cancel_order(session: AsyncSession, order_id: UUID, requester_id: UUID,) -> ErrandRequest | None:
    now = func.clock_timestamp()
    stmt = (
        update(ErrandRequest)
        .where(ErrandRequest.id == order_id,
               ErrandRequest.requester_id == requester_id,
               ErrandRequest.status == Status.OPEN,)
        .values(status=Status.CANCELLED, credit_status=CreditStatus.PENDING, updated_at=now)
        .returning(ErrandRequest))
    
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()
    if order is not None:
        add_credit_command(session, ReleaseCreditCommand(request_id=uuid4(), order_id=order.id))
        record_order_audit_log(session, order.id, Status.CANCELLED, actor_id=requester_id)

    await session.commit()
    return order


async def receive_order(session: AsyncSession, order_id: UUID, requester_id: UUID,) -> ErrandRequest | None:
    if not await _lock_order(session, order_id):
        await session.commit()
        return None
    now = (await session.execute(select(func.clock_timestamp()))).scalar_one()

    stmt = (
        update(ErrandRequest)
        .where(ErrandRequest.id == order_id,
               ErrandRequest.requester_id == requester_id,
               ErrandRequest.status == Status.DELIVERED,
               ErrandRequest.courier_id.is_not(None),
               ErrandRequest.progress_due_at > now,)
        .values(status=Status.RECEIVED, credit_status=CreditStatus.PENDING,
                progress_due_at=None, settlement_due_at=now + settlement_window(), updated_at=now)
        .returning(ErrandRequest))
    
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()
    if order is not None:
        assert order.courier_id is not None  # Required by the UPDATE predicate.
        add_credit_command(session, TransferCreditCommand(
            request_id=uuid4(), order_id=order.id, courier_id=order.courier_id,))
        record_order_audit_log(session, order.id, Status.RECEIVED, actor_id=requester_id)

    await session.commit()
    return order


def add_credit_command(session: AsyncSession, command: CreditCommand) -> None:
    session.add(CreditCommandOutbox(
        id=command.request_id,
        order_id=command.order_id,
        routing_key=command.routing_key,
        payload=command.model_dump(mode="json"),))


async def dispute_order(
    session: AsyncSession, order_id: UUID, actor_id: UUID, reason: str,
) -> ErrandRequest | None:
    """Freeze fulfilment or a rejected settlement; retries preserve the first reason."""
    order = await session.scalar(
        select(ErrandRequest).where(ErrandRequest.id == order_id)
        .with_for_update().execution_options(populate_existing=True)
    )
    if order is None or actor_id not in (order.requester_id, order.courier_id):
        await session.commit()
        return None
    if order.status == Status.DISPUTED:
        await session.commit()
        return order
    eligible = order.status in (Status.ACCEPTED, Status.PICKED_UP, Status.DELIVERED)
    eligible |= order.status == Status.RECEIVED and order.credit_status == CreditStatus.REJECTED
    if not eligible:
        await session.commit()
        return None
    order.status = Status.DISPUTED
    order.status_reason = reason
    order.updated_at = (await session.execute(select(func.clock_timestamp()))).scalar_one()

    record_order_audit_log(session, order.id, Status.DISPUTED, actor_id=actor_id, reason=reason)

    await session.commit()
    return order


async def expire_initializing_orders(session: AsyncSession) -> list[UUID]:
    """Stop exposing stale requests; reservation replay continues until reconciled.

    Do not release yet: Credit may not have created the reservation. A late
    reservation success queues its compensating release in credit_results.
    """
    reason = ("Credit reservation was not confirmed within the initialization deadline. "
              "Any delayed reservation will be refunded automatically.")
    result = await session.execute(
        update(ErrandRequest)
        .where(ErrandRequest.status == Status.INIT,
               ErrandRequest.created_at + init_window() <= func.clock_timestamp())
        .values(status=Status.EXPIRED, status_reason=reason, updated_at=func.clock_timestamp())
        .returning(ErrandRequest.id)
    )
    expired_ids = list(result.scalars())

    for order_id in expired_ids:
        record_order_audit_log(session, order_id, Status.EXPIRED, reason=reason)

    await session.commit()
    return expired_ids


async def dispute_overdue_orders(session: AsyncSession) -> list[UUID]:
    """Freeze stalled fulfilment or settlement without cancelling credit commands.

    PostgreSQL rechecks predicates after competing updates. A delayed settlement
    result may still update credit_status, but cannot exit DISPUTED.
    """
    reason = "The deadline for fulfilment or credit settlement was exceeded."
    result = await session.execute(
        update(ErrandRequest)
        .where(or_(
            and_(ErrandRequest.status.in_((Status.ACCEPTED, Status.PICKED_UP, Status.DELIVERED)),
                 ErrandRequest.progress_due_at <= func.clock_timestamp()),
            and_(ErrandRequest.status == Status.RECEIVED,
                 ErrandRequest.credit_status == CreditStatus.PENDING,
                 ErrandRequest.settlement_due_at <= func.clock_timestamp()),
        ))
        .values(status=Status.DISPUTED, status_reason=reason, updated_at=func.clock_timestamp())
        .returning(ErrandRequest.id)
    )
    disputed_ids = list(result.scalars())

    for order_id in disputed_ids:
        record_order_audit_log(session, order_id, Status.DISPUTED, reason=reason)

    await session.commit()
    return disputed_ids


async def expire_orders(session: AsyncSession) -> list[UUID]:
    reason = "No courier accepted the order within the time limit."
    result = await session.execute(
        update(ErrandRequest)
        .where(ErrandRequest.status == Status.OPEN, ErrandRequest.expires_at <= func.clock_timestamp())
        .values(status=Status.EXPIRED, credit_status=CreditStatus.PENDING,
                status_reason=reason, updated_at=func.clock_timestamp())
        .returning(ErrandRequest.id)
    )

    expired_ids = list(result.scalars())

    for order_id in expired_ids:
        add_credit_command(session, ReleaseCreditCommand(request_id=uuid4(), order_id=order_id))
        record_order_audit_log(session, order_id, Status.EXPIRED, reason=reason)

    await session.commit()
    return expired_ids


def record_order_audit_log(
    session: AsyncSession,
    order_id: UUID,
    action: Status,
    actor_id: UUID | None = None,
    reason: str | None = None,
) -> None:
    session.add(OrderAuditLog(
        order_id=order_id,
        actor_id=actor_id,
        action=action.value,
        reason=reason,
    ))

async def get_order_audit_logs(
    session: AsyncSession, order_id: UUID,
) -> list[OrderAuditLog]:
    statement = (
        select(OrderAuditLog)
        .where(OrderAuditLog.order_id == order_id)
        .order_by(OrderAuditLog.created_at.asc(), OrderAuditLog.log_id.asc())
    )
    result = await session.execute(statement)
    return list(result.scalars().all())