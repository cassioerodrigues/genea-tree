import uuid
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

RelType = Literal["parent", "spouse"]


class RelationshipCreate(BaseModel):
    tree_id: uuid.UUID
    person_a_id: uuid.UUID
    person_b_id: uuid.UUID
    rel_type: RelType
    start_date: date | None = None
    end_date: date | None = None
    metadata_: dict[str, Any] | None = None


class RelationshipUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    metadata_: dict[str, Any] | None = None


class RelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tree_id: uuid.UUID
    person_a_id: uuid.UUID
    person_b_id: uuid.UUID
    rel_type: RelType
    start_date: date | None
    end_date: date | None
    metadata_: dict[str, Any] | None
