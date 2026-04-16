import uuid
from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

# Disable rate limiting for the entire test session — must run before app import
from app.core.rate_limit import limiter as _limiter  # noqa: E402

_limiter.enabled = False

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.person import Person  # noqa: E402
from app.models.refresh_token import RefreshToken  # noqa: E402
from app.models.relationship import Relationship  # noqa: E402
from app.models.tree import Tree  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _clean_db() -> AsyncIterator[None]:
    """Limpa tabelas em ordem reversa de FK antes de cada teste."""
    async with AsyncSessionLocal() as session:
        for model in (RefreshToken, Relationship, Person, Tree, User):
            await session.execute(model.__table__.delete())
        await session.commit()
    yield


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as s:
        yield s


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def registered_user(client: httpx.AsyncClient) -> dict[str, str]:
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "password123"
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return {"email": email, "password": password, "id": resp.json()["id"]}


@pytest_asyncio.fixture
async def auth_client(
    client: httpx.AsyncClient, registered_user: dict[str, str]
) -> AsyncIterator[httpx.AsyncClient]:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert resp.status_code == 200, resp.text
    access = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {access}"})
    yield client


@pytest_asyncio.fixture
async def tree_of_user(session: AsyncSession, registered_user: dict[str, str]) -> Tree:
    tree = Tree(
        owner_id=uuid.UUID(registered_user["id"]),
        name="Test Tree",
        visibility="private",
    )
    session.add(tree)
    await session.commit()
    await session.refresh(tree)
    return tree
