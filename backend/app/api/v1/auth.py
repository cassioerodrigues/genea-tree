from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair, UserCreate, UserRead
from app.services.auth import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidRefreshToken,
    authenticate,
    issue_token_pair,
    register_user,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(f"{settings.auth_rate_limit_per_minute}/minute")
async def register(
    request: Request,
    payload: UserCreate,
    session: AsyncSession = Depends(get_db),
) -> UserRead:
    try:
        user = await register_user(session, payload)
    except EmailAlreadyRegistered as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email_already_registered"
        ) from exc
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenPair)
@limiter.limit(f"{settings.auth_rate_limit_per_minute}/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenPair:
    try:
        user = await authenticate(session, payload.email, payload.password)
    except InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials"
        ) from exc
    return await issue_token_pair(session, user)


@router.post("/refresh", response_model=TokenPair)
@limiter.limit(f"{settings.auth_rate_limit_per_minute}/minute")
async def refresh(
    request: Request,
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenPair:
    try:
        return await rotate_refresh_token(session, payload.refresh_token)
    except InvalidRefreshToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh_token"
        ) from exc


@router.get("/me", response_model=UserRead)
async def me(session: AsyncSession = Depends(get_db)) -> UserRead:
    # Placeholder — will be replaced once get_current_user dep is created (Task 9)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not_yet")
