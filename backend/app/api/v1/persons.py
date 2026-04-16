import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_tree_for_user
from app.db.session import get_db
from app.models.tree import Tree
from app.models.user import User
from app.schemas.person import PersonCreate, PersonRead, PersonUpdate
from app.services.persons import (
    PersonNotFound,
    create_person,
    delete_person,
    get_person,
    list_persons,
    update_person,
)

tree_router = APIRouter(prefix="/trees/{tree_id}/persons", tags=["persons"])
person_router = APIRouter(prefix="/persons", tags=["persons"])


@tree_router.get("", response_model=list[PersonRead])
async def list_tree_persons(
    tree: Tree = Depends(get_tree_for_user),
    session: AsyncSession = Depends(get_db),
    q: str | None = Query(default=None),
    place: str | None = Query(default=None),
    year_from: int | None = Query(default=None),
    year_to: int | None = Query(default=None),
) -> list[PersonRead]:
    persons = await list_persons(
        session, tree.id, q=q, place=place, year_from=year_from, year_to=year_to
    )
    return [PersonRead.model_validate(p) for p in persons]


@tree_router.post("", response_model=PersonRead, status_code=status.HTTP_201_CREATED)
async def create_tree_person(
    payload: PersonCreate,
    tree: Tree = Depends(get_tree_for_user),
    session: AsyncSession = Depends(get_db),
) -> PersonRead:
    person = await create_person(session, tree.id, payload)
    return PersonRead.model_validate(person)


async def _user_tree_ids(session: AsyncSession, user: User) -> list[uuid.UUID]:
    stmt = select(Tree.id).where(Tree.owner_id == user.id)
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


@person_router.get("/{person_id}", response_model=PersonRead)
async def retrieve_person(
    person_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PersonRead:
    tree_ids = await _user_tree_ids(session, current_user)
    try:
        person = await get_person(session, person_id, tree_ids)
    except PersonNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="person_not_found"
        ) from exc
    return PersonRead.model_validate(person)


@person_router.patch("/{person_id}", response_model=PersonRead)
async def patch_person(
    person_id: uuid.UUID,
    payload: PersonUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PersonRead:
    tree_ids = await _user_tree_ids(session, current_user)
    try:
        person = await get_person(session, person_id, tree_ids)
    except PersonNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="person_not_found"
        ) from exc
    updated = await update_person(session, person, payload)
    return PersonRead.model_validate(updated)


@person_router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy_person(
    person_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    tree_ids = await _user_tree_ids(session, current_user)
    try:
        person = await get_person(session, person_id, tree_ids)
    except PersonNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="person_not_found"
        ) from exc
    await delete_person(session, person)
