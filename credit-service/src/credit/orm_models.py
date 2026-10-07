from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, text
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
