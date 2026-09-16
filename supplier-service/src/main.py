import csv
import datetime
import os
from collections.abc import Iterable, Iterator
from contextlib import asynccontextmanager
from enum import Enum
from functools import lru_cache
from itertools import islice
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


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
        """Create the ORM entity after this CSV row has been validated."""
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
            session.add_all(batch)
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
    def parse(cls, supplier: Supplier) -> SupplierResponse:
        return cls.model_validate(supplier)

@app.get("/suppliers")
def get_suppliers() -> list[SupplierResponse]:
    try:
        with Session(get_engine()) as session:
            query = select(Supplier).where(Supplier.is_active)
            suppliers = session.scalars(query).all()
            return [SupplierResponse.parse(s) for s in suppliers]
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

def get_user():
    return {"isAdmin":True}


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


@app.post(
    "/suppliers",
    status_code=status.HTTP_201_CREATED,
)
def create_supplier(
    user: Annotated[dict, Depends(get_user)],
    create: SupplierCreate,
) -> SupplierResponse:
    if not user.get("isAdmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        with Session(get_engine()) as session:
            supplier = create.to_supplier()
            session.add(supplier)

            session.commit()
            session.refresh(supplier)
            return SupplierResponse.parse(supplier)
    except HTTPException:
        raise
    except Exception as error:
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
def update_supplier(
    id: UUID,
    user: Annotated[dict, Depends(get_user)],
    update: SupplierUpdate
) -> SupplierResponse:
    if not user.get("isAdmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        with Session(get_engine()) as session:
            query = select(Supplier).where(Supplier.id == id)
            supplier = session.scalars(query).one_or_none()
            if not supplier:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, 
                    detail="Supplier not found"
                )

            if not supplier.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, 
                    detail="Supplier is not active"
                )

            # exclude_unset=True ignores fields omitted in the request
            update_data = update.model_dump(exclude_unset=True)
            
            for key, value in update_data.items():
                setattr(supplier, key, value)

            session.commit()
            session.refresh(supplier)
            return SupplierResponse.parse(supplier)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update supplier",
        ) from error


@app.delete("/suppliers/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(
    id: UUID,
    user: Annotated[dict, Depends(get_user)],
) -> None:
    if not user.get("isAdmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        with Session(get_engine()) as session:
            query = select(Supplier).where(Supplier.id == id)
            supplier = session.scalars(query).one_or_none()
            if not supplier:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, 
                    detail="Supplier not found"
                )

            supplier.is_active = False
            session.commit()
            return None
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete supplier",
        ) from error
