import httpx
import pytest

from app.models.tree import Tree


@pytest.mark.asyncio
async def test_create_person(auth_client: httpx.AsyncClient, tree_of_user: Tree) -> None:
    resp = await auth_client.post(
        f"/api/v1/trees/{tree_of_user.id}/persons",
        json={"full_name": "Alice Doe", "birth_place": "Rio"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["full_name"] == "Alice Doe"
    assert body["tree_id"] == str(tree_of_user.id)


@pytest.mark.asyncio
async def test_list_persons_with_filter(auth_client: httpx.AsyncClient, tree_of_user: Tree) -> None:
    for name, place, birth in [
        ("Alice Doe", "Rio", "1900-01-01"),
        ("Bob Smith", "Sao Paulo", "1950-01-01"),
        ("Alice Brown", "Rio", "2000-01-01"),
    ]:
        r = await auth_client.post(
            f"/api/v1/trees/{tree_of_user.id}/persons",
            json={"full_name": name, "birth_place": place, "birth_date": birth},
        )
        assert r.status_code == 201

    resp = await auth_client.get(f"/api/v1/trees/{tree_of_user.id}/persons", params={"q": "Alice"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = await auth_client.get(
        f"/api/v1/trees/{tree_of_user.id}/persons", params={"place": "Rio"}
    )
    assert len(resp.json()) == 2

    resp = await auth_client.get(
        f"/api/v1/trees/{tree_of_user.id}/persons",
        params={"year_from": 1940, "year_to": 1960},
    )
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_update_person(auth_client: httpx.AsyncClient, tree_of_user: Tree) -> None:
    create = await auth_client.post(
        f"/api/v1/trees/{tree_of_user.id}/persons", json={"full_name": "Old Name"}
    )
    pid = create.json()["id"]
    resp = await auth_client.patch(f"/api/v1/persons/{pid}", json={"full_name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_person(auth_client: httpx.AsyncClient, tree_of_user: Tree) -> None:
    create = await auth_client.post(
        f"/api/v1/trees/{tree_of_user.id}/persons", json={"full_name": "To Delete"}
    )
    pid = create.json()["id"]
    resp = await auth_client.delete(f"/api/v1/persons/{pid}")
    assert resp.status_code == 204
    get_again = await auth_client.get(f"/api/v1/persons/{pid}")
    assert get_again.status_code == 404


@pytest.mark.asyncio
async def test_persons_require_auth(client: httpx.AsyncClient, tree_of_user: Tree) -> None:
    resp = await client.get(f"/api/v1/trees/{tree_of_user.id}/persons")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tree_isolation(
    client: httpx.AsyncClient, auth_client: httpx.AsyncClient, tree_of_user: Tree
) -> None:
    create = await auth_client.post(
        f"/api/v1/trees/{tree_of_user.id}/persons", json={"full_name": "Private"}
    )
    pid = create.json()["id"]

    # Segundo usuário registra e tenta acessar
    await client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "password123"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "password123"},
    )
    other_token = login.json()["access_token"]

    resp = await client.get(
        f"/api/v1/persons/{pid}", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert resp.status_code == 404
