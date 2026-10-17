from collections.abc import Mapping
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import AuthenticatedUser, get_authenticated_user
from common.db import get_session
from common.gateway import get_internal_gateway_client


from orders.repository import (
    accept_order,
    cancel_order,
    create_order,
    deliver_order,
    get_assigned_orders,
    get_open_orders,
    get_order_by_id,
    get_requested_orders,
    get_transition_error,
    pickup_order,
    receive_order,
)
from orders.schemas import CreateOrderRequest, OrderResponse, SupplierSnapshot


router = APIRouter (
    prefix="/orders",
    tags=["Orders"],
    dependencies=[Depends(get_authenticated_user)]
)

Session = Annotated[AsyncSession, Depends(get_session)]

# list all open order
@router.get("/open", response_model=list[OrderResponse])
async def list_open_orders(user: AuthenticatedUser, 
                           session: Session):
    return await get_open_orders(session)

# list all orders requested by user
@router.get("/me/requested", response_model=list[OrderResponse])
async def list_requested_orders(user: AuthenticatedUser, session: Session,):
    return await get_requested_orders(session, user.user_id)

# list all orders assigned to user
@router.get("/me/assigned", response_model=list[OrderResponse])
async def list_assigned_orders(user: AuthenticatedUser, session: Session,):
    return await get_assigned_orders(session, user.user_id)

# list specific order, either requested/assigned
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

# accept an open order
@router.patch("/{order_id}/accept", response_model=OrderResponse)
async def accept_order_endpoint(order_id: UUID, user: AuthenticatedUser, session: Session):
    order = await accept_order(session, order_id, user.user_id)

    if order is None:
        await get_transition_error(session, order_id, user.user_id, "accept")

    return order

# mark accepted order as picked up
@router.patch("/{order_id}/pickup", response_model=OrderResponse,)
async def pickup_order_endpoint(order_id: UUID, user: AuthenticatedUser, session: Session,):
    order = await pickup_order(session, order_id, user.user_id,)

    if order is None:
            await get_transition_error(session, order_id, user.user_id, "pick")

    return order

# mark picked up order as delivered
@router.patch("/{order_id}/deliver", response_model=OrderResponse,)
async def deliver_order_endpoint(order_id: UUID, user: AuthenticatedUser, session: Session,):
    order = await deliver_order(session, order_id, user.user_id,)

    if order is None:
        await get_transition_error(session, order_id, user.user_id, "deliver")

    return order

# order creationg
@router.post("", response_model=OrderResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_order_endpoint(payload: CreateOrderRequest, user: AuthenticatedUser, session: Session, 
                                 client: Annotated[httpx.AsyncClient, Depends(get_internal_gateway_client)],): 
    
    items = [item.model_dump(mode="json") for item in payload.items]

    try:
        response = await client.get("/supplier-api/suppliers")
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supplier service is temporarily unavailable.",
        ) from None

    if not response.is_success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supplier service is temporarily unavailable.",
        )
    try:
        suppliers = response.json()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supplier service returned an invalid response.",
        ) from None
    if not isinstance(suppliers, list) or any(
        not isinstance(supplier, Mapping) or "id" not in supplier
        for supplier in suppliers
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supplier service returned an invalid response.",
        )
    active_supplier = next(
        (
            supplier
            for supplier in suppliers
            if str(supplier["id"]) == str(payload.supplier_id)
        ),
        None,
    )
    if active_supplier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active supplier not found.",
        )
    try:
        supplier_snapshot = SupplierSnapshot.model_validate(active_supplier)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supplier service returned an invalid supplier.",
        ) from None

    order = await create_order(
        session=session,
        requester_id=user.user_id,
        supplier_id=payload.supplier_id,
        supplier_snapshot=supplier_snapshot.model_dump(mode="json"),
        items=items,
        pickup_notes=payload.pickup_notes,
        credits=payload.credits,
    )
    return order


@router.patch("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order_endpoint(order_id: UUID, user: AuthenticatedUser, session: Session,):
    order = await cancel_order(session, order_id, user.user_id)

    if order is None:
        await get_transition_error(session, order_id, user.user_id, "cancel")
    return order


@router.patch("/{order_id}/receive", response_model=OrderResponse)
async def receive_order_endpoint(order_id: UUID, user: AuthenticatedUser, session: Session,):
    order = await receive_order(session, order_id, user.user_id)
    
    if order is None:
        await get_transition_error(session, order_id, user.user_id, "receive")
    return order
