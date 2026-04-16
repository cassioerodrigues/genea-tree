import uuid
from collections.abc import Sequence

from sqlalchemy import extract, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.person import Person
from app.schemas.person import PersonCreate, PersonUpdate


class PersonNotFound(Exception):
    pass


async def create_person(session: AsyncSession, tree_id: uuid.UUID, data: PersonCreate) -> Person:
    person = Person(tree_id=tree_id, **data.model_dump())
    session.add(person)
    await session.commit()
    await session.refresh(person)
    return person


async def list_persons(
    session: AsyncSession,
    tree_id: uuid.UUID,
    q: str | None = None,
    place: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> Sequence[Person]:
    stmt = select(Person).where(Person.tree_id == tree_id)
    if q:
        stmt = stmt.where(Person.full_name.ilike(f"%{q}%"))
    if place:
        stmt = stmt.where(
            (Person.birth_place.ilike(f"%{place}%")) | (Person.death_place.ilike(f"%{place}%"))
        )
    if year_from is not None:
        stmt = stmt.where(extract("year", Person.birth_date) >= year_from)
    if year_to is not None:
        stmt = stmt.where(extract("year", Person.birth_date) <= year_to)
    result = await session.execute(stmt.order_by(Person.full_name))
    return result.scalars().all()


async def get_person(
    session: AsyncSession, person_id: uuid.UUID, tree_ids: Sequence[uuid.UUID]
) -> Person:
    person = await session.scalar(
        select(Person).where(Person.id == person_id, Person.tree_id.in_(tree_ids))
    )
    if person is None:
        raise PersonNotFound()
    return person


async def update_person(session: AsyncSession, person: Person, data: PersonUpdate) -> Person:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(person, key, value)
    await session.commit()
    await session.refresh(person)
    return person


async def delete_person(session: AsyncSession, person: Person) -> None:
    await session.delete(person)
    await session.commit()
