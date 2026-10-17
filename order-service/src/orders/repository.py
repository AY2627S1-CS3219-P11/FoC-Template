from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from orders.models import (
    COMMAND_MODELS,
    COMMAND_ROUTING_KEYS,
    CreditCommand,
    CreditOperation,
    CreditOperationOutcome,
    CreditOperationResult,
    CreditReservationStatus,
    ReleaseCreditCommand,
    ReserveCreditCommand,
    TransferCreditCommand,
)
from orders.orm_models import CreditCommandOutbox, CreditCommandResult, ErrandRequest, Status


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


async def get_open_orders(session: AsyncSession,) -> list[ErrandRequest]:
    result = await session.execute(
        select(ErrandRequest)
        .where(
            ErrandRequest.status == Status.OPEN,
            ErrandRequest.expires_at > func.clock_timestamp(),
        ).order_by(ErrandRequest.created_at.desc())
    )

    return list(result.scalars().all())


async def get_order_by_id(session:AsyncSession, order_id: UUID) -> ErrandRequest | None:
    return await session.get(ErrandRequest, order_id)


async def get_requested_orders(session: AsyncSession, requester_id: UUID) -> list[ErrandRequest]:
    result = await session.execute(
        select(ErrandRequest)
        .where(ErrandRequest.requester_id == requester_id)
        .order_by(ErrandRequest.created_at.desc()))

    return list(result.scalars().all())


async def get_assigned_orders(session: AsyncSession, courier_id: UUID,) -> list[ErrandRequest]:
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
        routing_key=COMMAND_ROUTING_KEYS[command.operation],
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


async def apply_credit_result(session: AsyncSession, result: CreditOperationResult) -> None:
    # apply correlated outcome, consumer commits before acknowledging
    pending = await session.scalar(
        select(CreditCommandOutbox)
        .where(CreditCommandOutbox.id == result.request_id)
        .with_for_update()
        .execution_options(populate_existing=True))

    if pending is None:
        raise ValueError("Credit result has no matching Order command")
    
    command = COMMAND_MODELS[pending.routing_key].model_validate(pending.payload)
    expected = result.model_dump(include=set(type(command).model_fields))

    if (pending.id != command.request_id or pending.order_id != result.order_id
        or command.operation != result.operation or command.model_dump() != expected):

        raise ValueError("Credit result does not match the original command")

    payload = result.model_dump(mode="json")
    saved_result = await session.get(CreditCommandResult, result.request_id)

    if saved_result is not None:
        if saved_result.payload != payload:
            raise ValueError("Credit returned a different outcome for the same request")
        return

    order = await session.scalar(
        select(ErrandRequest).where(ErrandRequest.id == result.order_id)
        .with_for_update().execution_options(populate_existing=True))

    if order is None:
        raise ValueError("Credit result references an unknown order")

    if result.operation == CreditOperation.RESERVE and (command.requester_id != order.requester_id
                                                        or command.amount != order.credits):
        raise ValueError("Credit reservation does not match the order")

    if result.operation == CreditOperation.TRANSFER and command.courier_id != order.courier_id:
        raise ValueError("Credit transfer does not match the assigned courier")

    # The receipt and order transition commit together. Missing receipts let
    # the publisher detect and recover operations whose replies were lost.
    session.add(CreditCommandResult(request_id=result.request_id, payload=payload))

    if result.outcome == CreditOperationOutcome.REJECTED:
        pending.last_error = f"Credit {result.operation} rejected: {result.reason}"
        if result.operation == CreditOperation.RESERVE and order.status == Status.PENDING:
            order.status = Status.REJECTED
            order.updated_at = await session.scalar(select(func.clock_timestamp()))
        return

    reservation = result.reservation
    expected_status = {
        CreditOperation.RESERVE: CreditReservationStatus.RESERVED,
        CreditOperation.RELEASE: CreditReservationStatus.RELEASED,
        CreditOperation.TRANSFER: CreditReservationStatus.TRANSFERRED,
    }[result.operation]
    if (reservation.user_id != order.requester_id or reservation.amount != order.credits
        or reservation.status != expected_status
        or (result.operation == CreditOperation.TRANSFER and reservation.recipient_user_id != order.courier_id)):
        raise ValueError("Credit result contains unexpected reservation details")

    # guard against duplicate/late results
    if result.operation == CreditOperation.RESERVE and order.status == Status.PENDING:
        now = await session.scalar(select(func.clock_timestamp()))
        order.status = Status.OPEN
        order.expires_at = now + timedelta(minutes=15)
        order.updated_at = now
    elif result.operation == CreditOperation.TRANSFER and order.status == Status.RECEIVED:
        order.status = Status.COMPLETED
        order.updated_at = await session.scalar(select(func.clock_timestamp()))
    pending.last_error = None


async def get_transition_error(session: AsyncSession, 
                                order_id: UUID, user_id: UUID, action: str,):
    order = await get_order_by_id(session, order_id)

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    if action in {"accept", "cancel", "receive"}:
        if action == "accept" and order.requester_id == user_id:
            raise HTTPException(status_code=403, detail="Cannot accept your own order")
        if action in {"cancel", "receive"} and order.requester_id != user_id:
            raise HTTPException(status_code=403, detail="Only the requester can update this order")
    elif order.courier_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Only the assigned courier can update this order",
        )

    action_description = {
        "accept": "accepted",
        "pick": "picked up",
        "deliver": "delivered",
        "cancel": "cancelled",
        "receive": "marked as received",
    }.get(action, action)
    raise HTTPException(
        status_code=409,
        detail=f"Order cannot be {action_description} in its current state",
    )
