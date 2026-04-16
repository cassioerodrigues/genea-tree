import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.tree import Tree
from app.models.user import User
from app.schemas.relationship import RelationshipCreate, RelationshipRead, RelationshipUpdate
from app.services.relationships import (
    DuplicateRelationship,
    InvalidRelationship,
    RelationshipNotFound,
    create_relationship,
    delete_relationship,
    get_relationship,
    update_relationship,
)

router = APIRouter(prefix="/relationships", tags=["relationships"])


async def _assert_tree_owner(session: AsyncSession, user: User, tree_id: uuid.UUID) -> None:
    tree = await session.scalar(select(Tree).where(Tree.id == tree_id, Tree.owner_id == user.id))
    if tree is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tree_not_found")


@router.post("", response_model=RelationshipRead, status_code=status.HTTP_201_CREATED)
async def create_rel(
    payload: RelationshipCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RelationshipRead:
    await _assert_tree_owner(session, current_user, payload.tree_id)
    try:
        rel = await create_relationship(session, payload)
    except InvalidRelationship as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_relationship"
        ) from exc
    except DuplicateRelationship as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="duplicate_relationship"
        ) from exc
    return RelationshipRead.model_validate(rel)


@router.patch("/{relationship_id}", response_model=RelationshipRead)
async def update_rel(
    relationship_id: uuid.UUID,
    payload: RelationshipUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RelationshipRead:
    try:
        rel = await get_relationship(session, relationship_id)
    except RelationshipNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="relationship_not_found"
        ) from exc
    await _assert_tree_owner(session, current_user, rel.tree_id)
    updated = await update_relationship(session, rel, payload)
    return RelationshipRead.model_validate(updated)


@router.delete("/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rel(
    relationship_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        rel = await get_relationship(session, relationship_id)
    except RelationshipNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="relationship_not_found"
        ) from exc
    await _assert_tree_owner(session, current_user, rel.tree_id)
    await delete_relationship(session, rel)
