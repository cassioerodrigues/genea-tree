import httpx
import pytest


@pytest.mark.asyncio
async def test_register_returns_201(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@example.com"
    assert "id" in body


@pytest.mark.asyncio
async def test_register_rejects_duplicate(client: httpx.AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_rejects_short_password(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "short"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: httpx.AsyncClient, registered_user: dict[str, str]) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


@pytest.mark.asyncio
async def test_login_wrong_password(
    client: httpx.AsyncClient, registered_user: dict[str, str]
) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "wrong-password"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates(client: httpx.AsyncClient, registered_user: dict[str, str]) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    refresh = login.json()["refresh_token"]

    ok = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert ok.status_code == 200
    new_pair = ok.json()
    assert new_pair["refresh_token"] != refresh

    # Usar o token antigo deve falhar (revogado)
    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert reuse.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_token(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user(
    auth_client: httpx.AsyncClient, registered_user: dict[str, str]
) -> None:
    resp = await auth_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == registered_user["email"]


@pytest.mark.asyncio
async def test_me_rejects_refresh_token(
    client: httpx.AsyncClient, registered_user: dict[str, str]
) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    refresh = login.json()["refresh_token"]
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_garbage_token(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not.a.jwt.token"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_rejected(
    client: httpx.AsyncClient, registered_user: dict[str, str]
) -> None:
    """Pass an access token (wrong type) to /refresh — must fail."""
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    access = login.json()["access_token"]
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_email_uniqueness(client: httpx.AsyncClient) -> None:
    """Register twice with same email — second must return 409."""
    data = {"email": "uniqueness@example.com", "password": "password123"}
    r1 = await client.post("/api/v1/auth/register", json=data)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/auth/register", json=data)
    assert r2.status_code == 409
