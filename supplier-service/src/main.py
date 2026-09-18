import csv
import datetime
import os
from collections.abc import AsyncIterator, Iterable, Iterator
from contextlib import asynccontextmanager
from enum import Enum
from functools import lru_cache
from itertools import islice
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

import httpx
from fastapi import Cookie, Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Category(str, Enum):
    Food = "Food"
    Shopping = "Shopping"
    Printing = "Printing"
    Food_Coffee = "Food/Coffee"


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str]
    category: Mapped[Category]
    building: Mapped[str]
    floor: Mapped[int]
    description: Mapped[str]
    lattitude: Mapped[float]
    longitude: Mapped[float]
    startingTime: Mapped[datetime.time]
    closingTime: Mapped[datetime.time]
    imageUrl: Mapped[str | None]
    is_active: Mapped[bool] = mapped_column(default=True)


@lru_cache
def get_engine() -> AsyncEngine:
    """Create and reuse the service's asynchronous PostgreSQL connection pool."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set")

    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    """Provide one asynchronous database session per request."""
    session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with session_factory() as session:
        yield session


class SupplierCsvRow(BaseModel):
    """Validated representation of a supplier row in the seed CSV."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(validation_alias="Name")
    category: Category = Field(validation_alias="Type")
    building: str = Field(validation_alias="Building")
    floor: int = Field(validation_alias="Floor")
    description: str = Field(validation_alias="Location Description")
    lattitude: float = Field(validation_alias="Latitude")
    longitude: float = Field(validation_alias="Longitude")
    startingTime: datetime.time = Field(validation_alias="StartingTime")
    closingTime: datetime.time = Field(validation_alias="ClosingTime")
    imageUrl: str | None = Field(validation_alias="ImageURL")

    @field_validator("startingTime", "closingTime", mode="before")
    @classmethod
    def parse_csv_time(cls, value: str) -> datetime.time:
        return datetime.datetime.strptime(value.strip(), "%H%Mhrs").time()

    @field_validator("imageUrl", mode="before")
    @classmethod
    def blank_image_url_is_none(cls, value: str) -> str | None:
        return value.strip() or None

    def to_supplier(self) -> Supplier:
        return Supplier(**self.model_dump())


def supplier_records(csv_path: Path) -> Iterator[Supplier]:
    """Validate CSV rows and convert them to Supplier entities."""
    with csv_path.open(newline="", encoding="cp1252") as file:
        for line_number, row in enumerate(csv.DictReader(file), start=2):
            try:
                yield SupplierCsvRow.model_validate(row).to_supplier()
            except ValidationError as error:
                raise ValueError(
                    f"Invalid supplier CSV data on line {line_number}"
                ) from error


def batches(records: Iterable[Supplier], size: int = 1_000) -> Iterator[list[Supplier]]:
    """Split an iterable into lists of at most ``size`` records."""
    iterator = iter(records)
    while batch := list(islice(iterator, size)):
        yield batch


async def seed_database_from_csv(engine: AsyncEngine, csv_path: Path) -> None:
    if not csv_path.is_file():
        print(f"Seed CSV not found at {csv_path}, skipping seeding")
        return

    async with engine.begin() as connection:
        table_exists = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).has_table(
                Supplier.__tablename__
            )
        )
        if table_exists:
            print("Suppliers table already exists, skipping seeding")
            return

        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        for batch in batches(supplier_records(csv_path)):
            session.add_all(batch)
        await session.commit()
    print("Successfully seeded database from CSV file")


@asynccontextmanager
async def lifespan(app: FastAPI):
    csv_path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "csv"
        / "supplier-seed-data.csv"
    )
    engine = get_engine()
    await seed_database_from_csv(engine, csv_path)
    yield
    await engine.dispose()


app = FastAPI(title="Supplier Service", lifespan=lifespan)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "supplier-service"}


class SupplierResponse(BaseModel):
    """Public JSON representation of a supplier database record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category: Category
    building: str
    floor: int
    lattitude: float
    longitude: float
    description: str
    startingTime: datetime.time
    closingTime: datetime.time
    imageUrl: str | None

    @classmethod
    def parse(cls, supplier: Supplier) -> "SupplierResponse":
        return cls.model_validate(supplier)


@app.get("/suppliers")
async def get_suppliers(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[SupplierResponse]:
    try:
        suppliers = await session.scalars(
            select(Supplier).where(Supplier.is_active)
        )
        return [SupplierResponse.parse(supplier) for supplier in suppliers.all()]
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


class AuthenticatedUser(BaseModel):
    user_id: UUID
    role: str


async def get_user_service_client() -> AsyncIterator[httpx.AsyncClient]:
    base_url = os.environ.get("USER_SERVICE_URL", "http://127.0.0.1:5005")
    async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
        yield client


async def get_user(
    client: Annotated[httpx.AsyncClient, Depends(get_user_service_client)],
    access_token: Annotated[str | None, Cookie()] = None,
) -> AuthenticatedUser:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token found. Please sign in.",
        )

    try:
        response = await client.get(
            "/authentication/sessions/current",
            headers={"Cookie": f"access_token={access_token}"},
        )
    except httpx.RequestError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable.",
        ) from error

    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please sign in.",
        )
    if not response.is_success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable.",
        )

    try:
        return AuthenticatedUser.model_validate(response.json())
    except (ValueError, ValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication returned an invalid response.",
        ) from error


def require_admin(user: AuthenticatedUser) -> None:
    if user.role not in {"admin", "admin_manager"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


class SupplierCreate(BaseModel):
    name: str
    category: Category
    building: str
    floor: int
    description: str
    lattitude: float
    longitude: float
    startingTime: datetime.time
    closingTime: datetime.time
    imageUrl: str | None = None

    def to_supplier(self) -> Supplier:
        return Supplier(**self.model_dump())


@app.post("/suppliers", status_code=status.HTTP_201_CREATED)
async def create_supplier(
    user: Annotated[AuthenticatedUser, Depends(get_user)],
    create: SupplierCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SupplierResponse:
    require_admin(user)

    try:
        supplier = create.to_supplier()
        session.add(supplier)
        await session.commit()
        await session.refresh(supplier)
        return SupplierResponse.parse(supplier)
    except Exception as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create supplier",
        ) from error


class SupplierUpdate(BaseModel):
    name: str | None = None
    category: Category | None = None
    building: str | None = None
    floor: int | None = None
    lattitude: float | None = None
    longitude: float | None = None
    description: str | None = None
    startingTime: datetime.time | None = None
    closingTime: datetime.time | None = None
    imageUrl: str | None = None


@app.patch("/suppliers/{id}")
async def update_supplier(
    id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_user)],
    update: SupplierUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SupplierResponse:
    require_admin(user)

    try:
        supplier = await session.scalar(select(Supplier).where(Supplier.id == id))
        if not supplier or not supplier.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found",
            )

        for key, value in update.model_dump(exclude_unset=True).items():
            setattr(supplier, key, value)

        await session.commit()
        await session.refresh(supplier)
        return SupplierResponse.parse(supplier)
    except HTTPException:
        raise
    except Exception as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update supplier",
        ) from error


@app.delete("/suppliers/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    require_admin(user)

    try:
        supplier = await session.scalar(select(Supplier).where(Supplier.id == id))
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found",
            )

        supplier.is_active = False
        await session.commit()
    except HTTPException:
        raise
    except Exception as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete supplier",
        ) from error
