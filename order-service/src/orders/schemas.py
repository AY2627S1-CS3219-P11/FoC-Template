from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from orders.orm_models import Status

class OrderItem(BaseModel):
    name: str
    quantity: int = Field(ge=1)

class CreateOrderRequest(BaseModel):
    supplier_id: UUID
    items: list[OrderItem] = Field(min_length=1)
    pickup_notes: str | None = None
    credits: int = Field(ge=1)

class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    requester_id: UUID
    supplier_id: UUID
    items: list[OrderItem]
    pickup_notes: str | None
    credits: int
    status: Status
    courier_id: UUID | None
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    updated_at: datetime