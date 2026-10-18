from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from orders.models import (
    CreditCommand,
    ReleaseCreditCommand,
    ReserveCreditCommand,
    TransferCreditCommand,
)
from orders.orm_models import (
    CreditCommandOutbox,
    CreditCommandResult,
    ErrandRequest,
    Status,
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


async def create_order(session: AsyncSession, requester_id: UUID, supplier_id: UUID, supplier_snapshot: dict, 
                       items: list[dict], pickup_notes: str | None, credits: int,) -> ErrandRequest:
    now = await session.scalar(select(func.clock_timestamp()))

    order = ErrandRequest(
        id=uuid4(),
        requester_id=requester_id,
        supplier_id=supplier_id,
        supplier_snapshot=supplier_snapshot,
        items=items,
        pickup_notes=pickup_notes,
        credits=credits,
        status=Status.PENDING,
        courier_id=None,
        created_at=now,
        expires_at=now + timedelta(minutes=15),
        updated_at=now,)
    
    session.add(order)
    await session.flush()
    add_credit_command(session, ReserveCreditCommand(
        request_id=uuid4(), order_id=order.id, requester_id=requester_id, amount=credits,))
    
    await session.commit()
    await session.refresh(order)
    return order


async def accept_order(session: AsyncSession, order_id: UUID, 
                        courier_id: UUID,) -> ErrandRequest | None:
    
    locked_id = await session.scalar(
        select(ErrandRequest.id)
        .where(ErrandRequest.id == order_id)
        .with_for_update())
    
    if locked_id is None:
        await session.commit()
        return None
    
    now = func.statement_timestamp()

    stmt = (update(ErrandRequest)
            .where(ErrandRequest.id == order_id,
                    ErrandRequest.status == Status.OPEN,
                    ErrandRequest.expires_at > now,
                    ErrandRequest.courier_id.is_(None),
                    ErrandRequest.requester_id != courier_id,)
            .values(status=Status.ACCEPTED,
                    courier_id=courier_id,
                    accepted_at=now,
                    updated_at=now,)
            .returning(ErrandRequest))

    result = await session.execute(stmt)
    order = result.scalar_one_or_none()

    await session.commit()

    return order


async def pickup_order(session: AsyncSession, order_id: UUID,
                        courier_id: UUID,) -> ErrandRequest | None:
    now = datetime.now(timezone.utc)

    stmt = (
        update(ErrandRequest)
        .where(ErrandRequest.id == order_id,
               ErrandRequest.status == Status.ACCEPTED,
               ErrandRequest.courier_id == courier_id,)
        .values(status=Status.PICKED_UP,
                updated_at=now,)
        .returning(ErrandRequest))

    result = await session.execute(stmt)
    order = result.scalar_one_or_none()

    await session.commit()

    return order


async def deliver_order(session: AsyncSession, order_id: UUID,
                         courier_id: UUID,) -> ErrandRequest | None:
    now = datetime.now(timezone.utc)

    stmt = (
        update(ErrandRequest)
        .where(
            ErrandRequest.id == order_id,
            ErrandRequest.status == Status.PICKED_UP,
            ErrandRequest.courier_id == courier_id,)
        .values(
            status=Status.DELIVERED,
            updated_at=now,)
        .returning(ErrandRequest))

    result = await session.execute(stmt)
    order = result.scalar_one_or_none()

    await session.commit()

    return order


async def cancel_order(session: AsyncSession, order_id: UUID, requester_id: UUID,) -> ErrandRequest | None:
    now = datetime.now(timezone.utc)
    stmt = (
        update(ErrandRequest)
        .where(ErrandRequest.id == order_id,
               ErrandRequest.requester_id == requester_id,
               ErrandRequest.status == Status.OPEN,)
        .values(status=Status.CANCELLED, updated_at=now)
        .returning(ErrandRequest))
    
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()
    if order is not None:
        add_credit_command(session, ReleaseCreditCommand(request_id=uuid4(), order_id=order.id))

    await session.commit()
    return order


async def receive_order(session: AsyncSession, order_id: UUID, requester_id: UUID,) -> ErrandRequest | None:
    now = datetime.now(timezone.utc)

    stmt = (
        update(ErrandRequest)
        .where(ErrandRequest.id == order_id,
               ErrandRequest.requester_id == requester_id,
               ErrandRequest.status == Status.DELIVERED,
               ErrandRequest.courier_id.is_not(None),)
        .values(status=Status.RECEIVED, updated_at=now)
        .returning(ErrandRequest))
    
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()
    if order is not None:
        add_credit_command(session, TransferCreditCommand(
            request_id=uuid4(), order_id=order.id, courier_id=order.courier_id,))

    await session.commit()
    return order


def add_credit_command(session: AsyncSession, command: CreditCommand) -> None:
    session.add(CreditCommandOutbox(
        id=command.request_id,
        order_id=command.order_id,
        routing_key=command.routing_key,
        payload=command.model_dump(mode="json"),))


async def expire_orders(session: AsyncSession) -> list[UUID]:
    result = await session.execute(
        update(ErrandRequest)
        .where(ErrandRequest.status == Status.OPEN,
               ErrandRequest.expires_at <= func.clock_timestamp())
        .values(status=Status.EXPIRED, updated_at=func.clock_timestamp())
        .returning(ErrandRequest.id))

    expired_ids = list(result.scalars())

    for order_id in expired_ids:
        add_credit_command(session, ReleaseCreditCommand(request_id=uuid4(), order_id=order_id))
    await session.commit()
    return expired_ids
