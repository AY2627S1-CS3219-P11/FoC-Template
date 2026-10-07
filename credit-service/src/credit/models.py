import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CreditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    available_credits: int = Field(default=100, ge=0, le=9_223_372_036_854_775_807, strict=True)
    reserved_credits: int = Field(default=0, ge=0, le=9_223_372_036_854_775_807, strict=True)
    created_at: datetime.datetime
    updated_at: datetime.datetime


class UserCreated(BaseModel):
    event: Literal["UserCreated"]
    user_id: UUID
    created_at: datetime.datetime
