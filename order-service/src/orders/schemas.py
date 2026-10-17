from datetime import datetime, time
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from orders.orm_models import Status


MAX_CREDITS = 9_223_372_036_854_775_807


class OrderItem(BaseModel):
    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    quantity: int = Field(ge=1)


class CreateOrderRequest(BaseModel):
    supplier_id: UUID
    items: list[OrderItem] = Field(min_length=1)
    pickup_notes: str | None = None
    credits: int = Field(ge=1, le=MAX_CREDITS)


class SupplierSnapshot(BaseModel):
    id: UUID
    name: str
    category: str
    building: str
    floor: int
    lattitude: float
    longitude: float
    description: str
    startingTime: time
    closingTime: time
    imageUrl: str | None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    requester_id: UUID
    supplier_id: UUID
    supplier_snapshot: SupplierSnapshot | None
    items: list[OrderItem]
    pickup_notes: str | None
    credits: int
    status: Status
    courier_id: UUID | None
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    updated_at: datetime