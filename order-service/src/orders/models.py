from datetime import datetime
from enum import StrEnum
from typing import ClassVar, Literal, Self
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
    routing_key: ClassVar[RoutingKey] = RoutingKey.CREDIT_RESERVE

    request_id: UUID
    order_id: UUID
    requester_id: UUID
    amount: int = Field(ge=1, le=MAX_CREDITS, strict=True)


class ReleaseCreditCommand(BaseModel):
    routing_key: ClassVar[RoutingKey] = RoutingKey.CREDIT_RELEASE

    request_id: UUID
    order_id: UUID


class TransferCreditCommand(BaseModel):
    routing_key: ClassVar[RoutingKey] = RoutingKey.CREDIT_TRANSFER

    request_id: UUID
    order_id: UUID
    courier_id: UUID


type CreditCommand = ReserveCreditCommand | ReleaseCreditCommand | TransferCreditCommand


class CreditReservationResult(BaseModel):
    order_id: UUID
    user_id: UUID
    amount: int = Field(ge=1, le=MAX_CREDITS, strict=True)
    status: CreditReservationStatus
    recipient_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class CreditResult(BaseModel):
    event: Literal["CreditOperationResult"] = "CreditOperationResult"
    request_id: UUID
    order_id: UUID
    operation: CreditOperation
    # Credit echoes operation-specific command fields in the same wire envelope.
    requester_id: UUID | None = None
    courier_id: UUID | None = None
    amount: int | None = Field(default=None, ge=1, le=MAX_CREDITS, strict=True)
    outcome: CreditOperationOutcome
    reservation: CreditReservationResult | None = None
    reason: CreditRejectionReason | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.operation == CreditOperation.RESERVE:
            if self.requester_id is None or self.amount is None:
                raise ValueError("A reserve reply requires requester_id and amount.")
        elif self.operation == CreditOperation.TRANSFER and self.courier_id is None:
            raise ValueError("A transfer reply requires courier_id.")

        if self.outcome == CreditOperationOutcome.SUCCEEDED:
            if self.reservation is None or self.reason is not None:
                raise ValueError(
                    "A successful outcome requires a reservation result only."
                )
            if self.reservation.order_id != self.order_id:
                raise ValueError("The reservation must belong to the outcome's order.")
            match self.operation:
                case CreditOperation.RESERVE:
                    expected_status = CreditReservationStatus.RESERVED
                case CreditOperation.RELEASE:
                    expected_status = CreditReservationStatus.RELEASED
                case CreditOperation.TRANSFER:
                    expected_status = CreditReservationStatus.TRANSFERRED
            if self.reservation.status != expected_status:
                raise ValueError(
                    "Reservation status does not match the successful operation."
                )
        elif self.reason is None or self.reservation is not None:
            raise ValueError("A rejected outcome requires a rejection reason only.")
        return self
