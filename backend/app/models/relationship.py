import uuid
from datetime import date
from typing import Any

from sqlalchemy import CheckConstraint, Column, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        CheckConstraint("rel_type IN ('parent','spouse')", name="rel_type_allowed"),
        UniqueConstraint(
            "tree_id", "person_a_id", "person_b_id", "rel_type", name="relationship_unique"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tree_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rel_type: Mapped[str] = mapped_column(String(16), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = Column("metadata", JSONB, nullable=True)
