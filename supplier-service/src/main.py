import csv
import datetime
import os
from collections.abc import Iterable, Iterator
from contextlib import asynccontextmanager
from enum import Enum
from functools import lru_cache
from itertools import islice
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import create_engine, insert, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass

class SupplierType(str, Enum):
    Food = "Food"
    Shopping = "Shopping"
    Printing = "Printing"
    Food_Coffee = "Food/Coffee"


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str]
    supplierType: Mapped[SupplierType]
    building: Mapped[str]
    floor: Mapped[int]
    description: Mapped[str]
    lattitude: Mapped[float]
    longitude: Mapped[float]
    startingTime: Mapped[datetime.time]
    closingTime: Mapped[datetime.time]
    imageUrl: Mapped[str | None]


class SupplierResponse(BaseModel):
    """Public JSON representation of a supplier database record."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    supplierType: SupplierType
    building: str
    floor: int
    description: str
    lattitude: float
    longitude: float
    startingTime: datetime.time
    closingTime: datetime.time
    imageUrl: str | None


class SuppliersResponse(BaseModel):
    suppliers: list[SupplierResponse]


@lru_cache
def get_engine() -> Engine:
    """Create and reuse the service's PostgreSQL connection pool."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set")

    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )


class SupplierCsvRow(BaseModel):
    """Validated representation of a supplier row in the seed CSV."""
    # automatically remove whitespace and trimming
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(validation_alias="Name")
    supplierType: SupplierType = Field(validation_alias="Type")
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


def supplier_records(csv_path: Path) -> Iterator[dict[str, object]]:
    """Validate CSV rows and convert them to Supplier insert records."""
    with csv_path.open(newline="", encoding="cp1252") as file:
        for line_number, row in enumerate(csv.DictReader(file), start=2):
            try:
                yield SupplierCsvRow.model_validate(row).model_dump()
            except ValidationError as error:
                raise ValueError(
                    f"Invalid supplier CSV data on line {line_number}"
                ) from error


def batches(records: Iterable[dict[str, object]], size: int = 1_000):
    """
    Splits an iterable into iterables of lists
    """
    # overkill for this project; but I find it much cleaner
    iterator = iter(records)
    while batch := list(islice(iterator, size)):
        yield batch

def seed_database_from_csv(engine: Engine, csv_path: Path) -> None:
    if not csv_path.is_file():
        print(f"Seed CSV not found at {csv_path}, skipping seeding")
        return

    # Seed exactly once when this service creates its suppliers table.
    if inspect(engine).has_table(Supplier.__tablename__):
        print("Suppliers table already exists, skipping seeding")
        return

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for batch in batches(supplier_records(csv_path)):
            session.execute(insert(Supplier), batch)
        session.commit()
    print("Successfully seeded database from CSV file")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Resolve from this module, rather than the process working directory.
    csv_path = Path(__file__).resolve().parent.parent / "data" / "csv" / "supplier-seed-data.csv"
    seed_database_from_csv(get_engine(), csv_path)
    yield

app = FastAPI(title="Supplier Service", lifespan=lifespan)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "supplier-service"}


@app.get("/suppliers", response_model=SuppliersResponse)
def get_suppliers() -> SuppliersResponse:
    try:
        with Session(get_engine()) as session:
            suppliers = session.scalars(select(Supplier)).all()
            return SuppliersResponse(suppliers=suppliers)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
