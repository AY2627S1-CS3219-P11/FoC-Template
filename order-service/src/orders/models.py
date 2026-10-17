
from datetime import datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


MAX_CREDITS = 9_223_372_036_854_775_807


class CreditOperation(StrEnum):
    RESERVE = "RESERVE"
    RELEASE = "RELEASE"
    TRANSFER = "TRANSFER"


class CreditOperationOutcome(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    REJECTED = "REJECTED"


class CreditReservationStatus(StrEnum):
    RESERVED = "RESERVED"
    RELEASED = "RELEASED"
    TRANSFERRED = "TRANSFERRED"


class CreditRejectionReason(StrEnum):
    INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"
    RESERVATION_CONFLICT = "RESERVATION_CONFLICT"
    INVALID_OPERATION = "INVALID_OPERATION"


class ExchangeName(StrEnum):
    CREDIT_COMMANDS = "credit_commands"
    CREDIT_EVENTS = "credit_events"


class RoutingKey(StrEnum):
    CREDIT_RESERVE = "credit.reserve"
    CREDIT_RELEASE = "credit.release"
    CREDIT_TRANSFER = "credit.transfer"
    CREDIT_OPERATION_RESULT = "credit.operation.result"


class ReserveCreditCommand(BaseModel):
    request_id: UUID
    order_id: UUID
    requester_id: UUID
    amount: int = Field(ge=1, le=MAX_CREDITS, strict=True)

    @property
    def operation(self) -> CreditOperation:
        return CreditOperation.RESERVE


class ReleaseCreditCommand(BaseModel):
    request_id: UUID
    order_id: UUID

    @property
    def operation(self) -> CreditOperation:
        return CreditOperation.RELEASE


class TransferCreditCommand(BaseModel):
    request_id: UUID
    order_id: UUID
    courier_id: UUID

    @property
    def operation(self) -> CreditOperation:
        return CreditOperation.TRANSFER


type CreditCommand = ReserveCreditCommand | ReleaseCreditCommand | TransferCreditCommand


COMMAND_MODELS = {
    RoutingKey.CREDIT_RESERVE: ReserveCreditCommand,
    RoutingKey.CREDIT_RELEASE: ReleaseCreditCommand,
    RoutingKey.CREDIT_TRANSFER: TransferCreditCommand,
}

COMMAND_ROUTING_KEYS = {
    CreditOperation.RESERVE: RoutingKey.CREDIT_RESERVE,
    CreditOperation.RELEASE: RoutingKey.CREDIT_RELEASE,
    CreditOperation.TRANSFER: RoutingKey.CREDIT_TRANSFER,
}


class CreditReservationResult(BaseModel):
    order_id: UUID
    user_id: UUID
    amount: int = Field(ge=1, le=MAX_CREDITS, strict=True)
    status: CreditReservationStatus
    recipient_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class CreditOperationResult(BaseModel):
    event: Literal["CreditOperationResult"] = "CreditOperationResult"
    request_id: UUID
    order_id: UUID
    operation: CreditOperation
    outcome: CreditOperationOutcome
    requester_id: UUID | None = None
    courier_id: UUID | None = None
    amount: int | None = Field(default=None, ge=1, le=MAX_CREDITS, strict=True)
    reservation: CreditReservationResult | None = None
    reason: CreditRejectionReason | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.outcome == CreditOperationOutcome.SUCCEEDED:
            if self.reservation is None or self.reason is not None:
                raise ValueError("A successful outcome requires a reservation result only.")
            if self.reservation.order_id != self.order_id:
                raise ValueError("The reservation must belong to the outcome's order.")
        elif self.reason is None or self.reservation is not None:
            raise ValueError("A rejected outcome requires a rejection reason only.")
        return self
