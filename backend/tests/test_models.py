import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.session import AsyncSessionLocal
from app.models import Person, Relationship, Tree, User


@pytest.mark.asyncio
async def test_crud_and_unique_relationship() -> None:
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:8]
        user = User(email=f"test-{suffix}@example.com", password_hash="x")
        session.add(user)
        await session.flush()

        tree = Tree(owner_id=user.id, name="Family", visibility="private")
        session.add(tree)
        await session.flush()

        p_a = Person(tree_id=tree.id, full_name="Alice")
        p_b = Person(tree_id=tree.id, full_name="Bob")
        session.add_all([p_a, p_b])
        await session.flush()

        rel = Relationship(
            tree_id=tree.id, person_a_id=p_a.id, person_b_id=p_b.id, rel_type="parent"
        )
        session.add(rel)
        await session.flush()

        result = await session.execute(select(Person).where(Person.tree_id == tree.id))
        assert len(result.scalars().all()) == 2

        dup = Relationship(
            tree_id=tree.id, person_a_id=p_a.id, person_b_id=p_b.id, rel_type="parent"
        )
        session.add(dup)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
