from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgresUUID


class Base(DeclarativeBase):
    pass


class Status(str, Enum):
    OPEN = "open"
    ACCEPTED = "accepted"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"
    RECEIVED = "received"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PENDING = "pending"
    REJECTED = "rejected"
    

class ErrandRequest(Base):
    __tablename__ = "errand_requests"

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=text("gen_random_uuid()"),
    )

    requester_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=False,
    )

    supplier_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=False,
    )

    items: Mapped[list | dict] = mapped_column(JSONB, nullable=False,)

    supplier_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    pickup_notes: Mapped[str | None] = mapped_column(Text, nullable=True,)

    credits: Mapped[int] = mapped_column(BigInteger, nullable=False,)

    status: Mapped[Status] = mapped_column(
        SQLEnum(Status, name="request_status", 
                values_callable=lambda enum: [e.value for e in enum],),
        nullable=False,
        default=Status.PENDING,
    )

    courier_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.clock_timestamp(),
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, 
            default=text("(clock_timestamp() + interval '15 minutes')"),
    )

    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.clock_timestamp(),
    )


    __table_args__ = (
        CheckConstraint("credits >= 1", name="errand_requests_credits_check"),
    )


class OrderCreationKey(Base):
    __tablename__ = "order_creation_keys"

    requester_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    order_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("errand_requests.id", ondelete="CASCADE"),
        nullable=False, unique=True,)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class CreditCommandOutbox(Base):
    __tablename__ = "credit_command_outbox"

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    order_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("errand_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    routing_key: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("order_id", "routing_key", name="credit_command_outbox_order_routing_key"),
        Index("credit_command_outbox_pending_idx", "available_at", "created_at"),
    )
