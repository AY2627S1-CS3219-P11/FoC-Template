from enum import StrEnum
from typing import ClassVar, Self
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


class CreditResult(BaseModel):
    request_id: UUID
    order_id: UUID
    operation: CreditOperation
    outcome: CreditOperationOutcome
    reason: CreditRejectionReason | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.outcome == CreditOperationOutcome.SUCCEEDED:
            if self.reason is not None:
                raise ValueError("A successful outcome cannot have a rejection reason.")
        elif self.reason is None:
            raise ValueError("A rejected outcome requires a rejection reason.")
        return self
