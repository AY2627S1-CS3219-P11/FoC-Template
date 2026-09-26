import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False,)

    user_email: Mapped[str] = mapped_column(Text, unique=True, nullable=False,)

    password_hash: Mapped[str] = mapped_column(Text, nullable=False,)

    user_role: Mapped[str] = mapped_column(Text, nullable=False, default="user")

    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    updated_at: Mapped[datetime.datetime] = mapped_column(
    default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "user_email LIKE '%@%.%'",
            name="valid_user_email",
        ),
        CheckConstraint(
            "user_role IN ('user', 'admin', 'admin_manager')",
            name="valid_user_role",
        ),
    )