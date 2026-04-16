import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PersonBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    gender: str | None = None
    birth_date: date | None = None
    birth_date_approx: str | None = None
    birth_place: str | None = None
    death_date: date | None = None
    death_date_approx: str | None = None
    death_place: str | None = None
    notes: str | None = None
    extra: dict[str, Any] | None = None


class PersonCreate(PersonBase):
    pass


class PersonUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    gender: str | None = None
    birth_date: date | None = None
    birth_date_approx: str | None = None
    birth_place: str | None = None
    death_date: date | None = None
    death_date_approx: str | None = None
    death_place: str | None = None
    notes: str | None = None
    extra: dict[str, Any] | None = None


class PersonRead(PersonBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tree_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
