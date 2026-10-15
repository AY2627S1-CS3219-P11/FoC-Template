import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MAX_CREDITS = 9_223_372_036_854_775_807


class CreditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    available_credits: int = Field(ge=0, le=MAX_CREDITS, strict=True)
    reserved_credits: int = Field(ge=0, le=MAX_CREDITS, strict=True)


class CreditAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: UUID
    user_id: UUID
    recipient_user_id: UUID | None = None
    order_id: UUID | None = None
    action: Literal["INITIAL_ALLOCATION", "RESERVE", "RELEASE", "TRANSFER"]
    amount: int = Field(ge=1, le=MAX_CREDITS, strict=True)
    created_at: datetime.datetime


class CreditReservationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: UUID
    user_id: UUID
    amount: int = Field(ge=1, le=MAX_CREDITS, strict=True)
    status: Literal["RESERVED", "RELEASED", "TRANSFERRED"]
    recipient_user_id: UUID | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class UserCreated(BaseModel):
    event: Literal["UserCreated"]
    user_id: UUID
    created_at: datetime.datetime


class CreditAccountsSyncRequested(BaseModel):
    event: Literal["CreditAccountsSyncRequested"]


class ReserveCreditCommand(BaseModel):
    order_id: UUID
    requester_id: UUID
    amount: int = Field(ge=1, le=MAX_CREDITS, strict=True)


class ReleaseCreditCommand(BaseModel):
    order_id: UUID


class TransferCreditCommand(BaseModel):
    order_id: UUID
    courier_id: UUID