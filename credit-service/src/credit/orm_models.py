from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Text, text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Credit(Base):
    __tablename__ = "credits"

    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True,
    )
    available_credits: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("100"),
    )
    reserved_credits: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "available_credits >= 0", name="credits_available_non_negative",
        ),
        CheckConstraint(
            "reserved_credits >= 0", name="credits_reserved_non_negative",
        ),
    )


class CreditAuditLog(Base):
    __tablename__ = "credit_audit_logs"

    log_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=False,
    )
    recipient_user_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=True,
    )
    order_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=True,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('INITIAL_ALLOCATION', 'RESERVE', 'RELEASE', 'TRANSFER')",
            name="credit_audit_logs_valid_action",
        ),
        CheckConstraint(
            "amount > 0", name="credit_audit_logs_amount_positive",
        ),
        CheckConstraint(
            "(action = 'TRANSFER' AND recipient_user_id IS NOT NULL "
            "AND recipient_user_id <> user_id) "
            "OR (action <> 'TRANSFER' AND recipient_user_id IS NULL)",
            name="credit_audit_logs_valid_recipient",
        ),
        CheckConstraint(
            "(action = 'INITIAL_ALLOCATION' AND order_id IS NULL) "
            "OR (action <> 'INITIAL_ALLOCATION' AND order_id IS NOT NULL)",
            name="credit_audit_logs_valid_order",
        ),
    )
