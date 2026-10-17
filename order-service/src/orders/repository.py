from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from orders.orm_models import CreditCommandOutbox, ErrandRequest, Status


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
        
    await session.commit()
    return order


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
