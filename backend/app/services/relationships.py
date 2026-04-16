import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.person import Person
from app.models.relationship import Relationship
from app.schemas.relationship import RelationshipCreate, RelationshipUpdate


class RelationshipNotFound(Exception):
    pass


class DuplicateRelationship(Exception):
    pass


class InvalidRelationship(Exception):
    pass


async def _ensure_same_tree(
    session: AsyncSession,
    tree_id: uuid.UUID,
    person_a_id: uuid.UUID,
    person_b_id: uuid.UUID,
) -> None:
    if person_a_id == person_b_id:
        raise InvalidRelationship()
    stmt = select(Person.id).where(
        Person.tree_id == tree_id, Person.id.in_([person_a_id, person_b_id])
    )
    result = await session.execute(stmt)
    ids = {row[0] for row in result.all()}
    if len(ids) != 2:
        raise InvalidRelationship()


async def create_relationship(session: AsyncSession, data: RelationshipCreate) -> Relationship:
    await _ensure_same_tree(session, data.tree_id, data.person_a_id, data.person_b_id)
    rel = Relationship(
        tree_id=data.tree_id,
        person_a_id=data.person_a_id,
        person_b_id=data.person_b_id,
        rel_type=data.rel_type,
        start_date=data.start_date,
        end_date=data.end_date,
        metadata_=data.metadata_,
    )
    session.add(rel)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateRelationship() from exc
    await session.refresh(rel)
    return rel


async def get_relationship(session: AsyncSession, relationship_id: uuid.UUID) -> Relationship:
    rel = await session.get(Relationship, relationship_id)
    if rel is None:
        raise RelationshipNotFound()
    return rel


async def update_relationship(
    session: AsyncSession, rel: Relationship, data: RelationshipUpdate
) -> Relationship:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(rel, key, value)
    await session.commit()
    await session.refresh(rel)
    return rel


async def delete_relationship(session: AsyncSession, rel: Relationship) -> None:
    await session.delete(rel)
    await session.commit()
