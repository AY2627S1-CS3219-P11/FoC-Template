from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


from orders.orm_models import ErrandRequest, Status


async def get_open_orders(session: AsyncSession,) -> list[ErrandRequest]:
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(ErrandRequest)
        .where(
            ErrandRequest.status == Status.OPEN,
            ErrandRequest.expires_at > now,
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

async def accept_order(session: AsyncSession, order_id: UUID, 
                       courier_id: UUID,) -> ErrandRequest | None:
    now = datetime.now(timezone.utc)

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
        .where(
            ErrandRequest.id == order_id,
            ErrandRequest.status == Status.ACCEPTED,
            ErrandRequest.courier_id == courier_id,)
        .values(
            status=Status.PICKED_UP,
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

# if theres an issue between order state
async def get_transition_error(session: AsyncSession, 
                                order_id: UUID, user_id: UUID, action: str,):
    order = await get_order_by_id(session, order_id)

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    if action == "accept":
        if order.requester_id == user_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot accept your own order",
            )

    else:
        if order.courier_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Only the assigned courier can update this order",
            )

    raise HTTPException(
        status_code=409,
        detail=f"Order cannot be {action}ed in its current state",
    )