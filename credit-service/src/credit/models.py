import datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, Json, JsonValue, model_validator


class CreditOperation(StrEnum):
    RESERVE = "RESERVE"
    RELEASE = "RELEASE"
    TRANSFER = "TRANSFER"


class CreditAuditAction(StrEnum):
    INITIAL_ALLOCATION = "INITIAL_ALLOCATION"
    RESERVE = "RESERVE"
    RELEASE = "RELEASE"
    TRANSFER = "TRANSFER"


class CreditReservationStatus(StrEnum):
    RESERVED = "RESERVED"
    RELEASED = "RELEASED"
    TRANSFERRED = "TRANSFERRED"


class CreditOperationOutcome(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    REJECTED = "REJECTED"


class CreditRejectionReason(StrEnum):
    INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"
    RESERVATION_CONFLICT = "RESERVATION_CONFLICT"
    INVALID_OPERATION = "INVALID_OPERATION"


class MessageType(StrEnum):
    USER_CREATED = "UserCreated"
    CREDIT_ACCOUNTS_SYNC_REQUESTED = "CreditAccountsSyncRequested"
    CREDIT_OPERATION_RESULT = "CreditOperationResult"


class ExchangeName(StrEnum):
    USER_EVENTS = "user_events"
    CREDIT_COMMANDS = "credit_commands"
    CREDIT_EVENTS = "credit_events"


class QueueName(StrEnum):
    CREDIT_USER_CREATED = "credit_user_created"
    CREDIT_ACCOUNTS_SYNC_REQUESTED = "credit_accounts_sync_requested"
    CREDIT_COMMANDS = "credit_service_commands_queue"


class RoutingKey(StrEnum):
    USER_CREATED = "user.created"
    CREDIT_ACCOUNTS_SYNC_REQUESTED = "credit.accounts.sync.requested"
    CREDIT_RESERVE = "credit.reserve"
    CREDIT_RELEASE = "credit.release"
    CREDIT_TRANSFER = "credit.transfer"
    CREDIT_OPERATION_RESULT = "credit.operation.result"


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
    action: CreditAuditAction
    amount: int = Field(ge=1, le=MAX_CREDITS, strict=True)
    created_at: datetime.datetime


class CreditReservationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: UUID
    user_id: UUID
    amount: int = Field(ge=1, le=MAX_CREDITS, strict=True)
    status: CreditReservationStatus
    recipient_user_id: UUID | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class UserCreated(BaseModel):
    event: Literal[MessageType.USER_CREATED]
    user_id: UUID
    created_at: datetime.datetime


class CreditAccountsSyncRequested(BaseModel):
    event: Literal[MessageType.CREDIT_ACCOUNTS_SYNC_REQUESTED]


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


class CreditOperationResult(BaseModel):
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


class StoredCreditOutcome(BaseModel):
    """Store the command for retry checks; publish only the result."""

    command: dict[str, JsonValue]
    result: CreditOperationResult


class CreditOutboxResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: UUID
    payload: Json[StoredCreditOutcome]
    published_at: datetime.datetime | None = None
