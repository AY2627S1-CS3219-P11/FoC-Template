from typing import Annotated
from uuid import UUID 

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from common.db import get_session
from auth.dependencies import AuthenticatedUser, get_authenticated_user

from orders.repository import (get_open_orders, 
                               get_requested_orders, 
                               get_assigned_orders, 
                               get_order_by_id,
                               accept_order,
                               pickup_order,
                               deliver_order,
                               get_transition_error,)
from orders.schemas import OrderResponse


router = APIRouter (
    prefix="/orders",
    tags=["Orders"],
    dependencies=[Depends(get_authenticated_user)]
)

Session = Annotated[AsyncSession, Depends(get_session)]

@router.get("/open", response_model=list[OrderResponse])
async def list_open_orders(user: AuthenticatedUser, 
                           session:Annotated[AsyncSession, Depends(get_session)],):
    return await get_open_orders(session)

@router.get("/me/requested", response_model=list[OrderResponse])
async def list_requested_orders(user: AuthenticatedUser, session: Session,):
    return await get_requested_orders(session, user.user_id)

@router.get("/me/assigned", response_model=list[OrderResponse])
async def list_assigned_orders(user: AuthenticatedUser, session: Session,):
    return await get_assigned_orders(session, user.user_id)

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: UUID, user: AuthenticatedUser, session: Session):
    order = await get_order_by_id(session, order_id)

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )
    if user.user_id not in (order.requester_id, order.courier_id,):
        raise HTTPException(
            status_code=403,
            detail="Not allowed to view this order",
        )

    return order

@router.patch("/{order_id}/accept", response_model=OrderResponse)
async def accept_order_endpoint(order_id: UUID, user: AuthenticatedUser, session: Session):
    order = await accept_order(session, order_id, user.user_id)

    if order is None:
        await get_transition_error(session, order_id, user.user_id, "accept")

    return order

@router.patch("/{order_id}/pickup", response_model=OrderResponse,)
async def pickup_order_endpoint(order_id: UUID, user: AuthenticatedUser, session: Session,):
    order = await pickup_order(session, order_id, user.user_id,)

    if order is None:
            await get_transition_error(session, order_id, user.user_id, "pick")

    return order

@router.patch("/{order_id}/deliver", response_model=OrderResponse,)
async def deliver_order_endpoint(order_id: UUID, user: AuthenticatedUser, session: Session,):
    order = await deliver_order(session, order_id, user.user_id,)

    if order is None:
        await get_transition_error(session, order_id, user.user_id, "deliver")

    return order