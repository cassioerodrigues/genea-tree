import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tree import Tree


async def _create_person(client: httpx.AsyncClient, tree_id: object, name: str) -> str:
    resp = await client.post(f"/api/v1/trees/{tree_id}/persons", json={"full_name": name})
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


@pytest.mark.asyncio
async def test_create_relationship(auth_client: httpx.AsyncClient, tree_of_user: Tree) -> None:
    a = await _create_person(auth_client, tree_of_user.id, "A")
    b = await _create_person(auth_client, tree_of_user.id, "B")
    resp = await auth_client.post(
        "/api/v1/relationships",
        json={
            "tree_id": str(tree_of_user.id),
            "person_a_id": a,
            "person_b_id": b,
            "rel_type": "parent",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["rel_type"] == "parent"


@pytest.mark.asyncio
async def test_duplicate_relationship_returns_409(
    auth_client: httpx.AsyncClient, tree_of_user: Tree
) -> None:
    a = await _create_person(auth_client, tree_of_user.id, "A")
    b = await _create_person(auth_client, tree_of_user.id, "B")
    body = {
        "tree_id": str(tree_of_user.id),
        "person_a_id": a,
        "person_b_id": b,
        "rel_type": "spouse",
    }
    first = await auth_client.post("/api/v1/relationships", json=body)
    assert first.status_code == 201
    dup = await auth_client.post("/api/v1/relationships", json=body)
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_invalid_rel_type_rejected(
    auth_client: httpx.AsyncClient, tree_of_user: Tree
) -> None:
    a = await _create_person(auth_client, tree_of_user.id, "A")
    b = await _create_person(auth_client, tree_of_user.id, "B")
    resp = await auth_client.post(
        "/api/v1/relationships",
        json={
            "tree_id": str(tree_of_user.id),
            "person_a_id": a,
            "person_b_id": b,
            "rel_type": "sibling",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_self_relationship_rejected(
    auth_client: httpx.AsyncClient, tree_of_user: Tree
) -> None:
    a = await _create_person(auth_client, tree_of_user.id, "A")
    resp = await auth_client.post(
        "/api/v1/relationships",
        json={
            "tree_id": str(tree_of_user.id),
            "person_a_id": a,
            "person_b_id": a,
            "rel_type": "spouse",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_relationship(auth_client: httpx.AsyncClient, tree_of_user: Tree) -> None:
    a = await _create_person(auth_client, tree_of_user.id, "A")
    b = await _create_person(auth_client, tree_of_user.id, "B")
    create = await auth_client.post(
        "/api/v1/relationships",
        json={
            "tree_id": str(tree_of_user.id),
            "person_a_id": a,
            "person_b_id": b,
            "rel_type": "parent",
        },
    )
    rid = create.json()["id"]
    resp = await auth_client.delete(f"/api/v1/relationships/{rid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_update_relationship(auth_client: httpx.AsyncClient, tree_of_user: Tree) -> None:
    a = await _create_person(auth_client, tree_of_user.id, "A")
    b = await _create_person(auth_client, tree_of_user.id, "B")
    create = await auth_client.post(
        "/api/v1/relationships",
        json={
            "tree_id": str(tree_of_user.id),
            "person_a_id": a,
            "person_b_id": b,
            "rel_type": "spouse",
            "start_date": "2000-06-15",
        },
    )
    rid = create.json()["id"]
    resp = await auth_client.patch(f"/api/v1/relationships/{rid}", json={"end_date": "2010-12-01"})
    assert resp.status_code == 200
    assert resp.json()["end_date"] == "2010-12-01"


@pytest.mark.asyncio
async def test_relationship_person_wrong_tree_rejected(
    auth_client: httpx.AsyncClient,
    tree_of_user: Tree,
    session: AsyncSession,
    registered_user: dict[str, str],
) -> None:
    """Person from a different tree cannot be used in the relationship."""
    import uuid

    from app.models.tree import Tree as TreeModel

    other_tree = TreeModel(
        owner_id=uuid.UUID(registered_user["id"]),
        name="Other Tree",
        visibility="private",
    )
    session.add(other_tree)
    await session.commit()
    await session.refresh(other_tree)

    a = await _create_person(auth_client, tree_of_user.id, "A in tree 1")
    # We create person B directly via SQL to avoid tree-scoped routing
    from app.models.person import Person as PersonModel

    person_b = PersonModel(tree_id=other_tree.id, full_name="B in tree 2")
    session.add(person_b)
    await session.commit()
    await session.refresh(person_b)

    resp = await auth_client.post(
        "/api/v1/relationships",
        json={
            "tree_id": str(tree_of_user.id),
            "person_a_id": a,
            "person_b_id": str(person_b.id),
            "rel_type": "parent",
        },
    )
    assert resp.status_code == 400
