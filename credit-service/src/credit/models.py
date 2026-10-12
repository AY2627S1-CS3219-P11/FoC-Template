import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CreditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    available_credits: int = Field(ge=0, le=9_223_372_036_854_775_807, strict=True)
    reserved_credits: int = Field(ge=0, le=9_223_372_036_854_775_807, strict=True)


class UserCreated(BaseModel):
    event: Literal["UserCreated"]
    user_id: UUID
    created_at: datetime.datetime


class CreditAccountsSyncRequested(BaseModel):
    event: Literal["CreditAccountsSyncRequested"]
