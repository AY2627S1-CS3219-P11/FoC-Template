from datetime import datetime, time
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from orders.orm_models import CreditStatus, Status

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


class DisputeOrderRequest(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


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
    credit_status: CreditStatus
    courier_id: UUID | None
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    progress_due_at: datetime | None
    settlement_due_at: datetime | None
    status_reason: str | None
    updated_at: datetime


class ServerClockResponse(BaseModel):
    server_time: datetime


class OrderAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: UUID
    order_id: UUID
    actor_id: UUID | None = None
    action: Status
    reason: str | None = None
    created_at: datetime