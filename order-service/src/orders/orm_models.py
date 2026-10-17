from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum as SQLEnum,  ForeignKey, Integer, Text, func, text
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

    pickup_notes: Mapped[str | None] = mapped_column(Text, nullable=True,)

    credits: Mapped[int] = mapped_column(Integer, nullable=False,)

    status: Mapped[Status] = mapped_column(
        SQLEnum(Status, name="request_status", 
                values_callable=lambda enum: [e.value for e in enum],),
        nullable=False,
        default="'text'",
    )

    courier_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=False,
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