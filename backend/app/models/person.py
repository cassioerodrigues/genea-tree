import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tree_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    birth_date_approx: Mapped[str | None] = mapped_column(String(64), nullable=True)
    birth_place: Mapped[str | None] = mapped_column(String(255), nullable=True)
    death_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    death_date_approx: Mapped[str | None] = mapped_column(String(64), nullable=True)
    death_place: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
