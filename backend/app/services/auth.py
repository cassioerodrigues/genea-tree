import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    REFRESH_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenPair, UserCreate


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class InvalidRefreshToken(Exception):
    pass


async def register_user(session: AsyncSession, data: UserCreate) -> User:
    existing = await session.scalar(select(User).where(User.email == data.email))
    if existing is not None:
        raise EmailAlreadyRegistered()
    user = User(email=data.email, password_hash=hash_password(data.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentials()
    return user


async def issue_token_pair(session: AsyncSession, user: User) -> TokenPair:
    access = create_access_token(str(user.id))
    refresh, jti = create_refresh_token(str(user.id))
    expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days)
    session.add(RefreshToken(user_id=user.id, jti=jti, expires_at=expires_at))
    await session.commit()
    return TokenPair(access_token=access, refresh_token=refresh)


async def rotate_refresh_token(session: AsyncSession, token: str) -> TokenPair:
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise InvalidRefreshToken() from exc
    if payload.get("type") != REFRESH_TYPE:
        raise InvalidRefreshToken()
    jti = payload.get("jti")
    sub = payload.get("sub")
    if not jti or not sub:
        raise InvalidRefreshToken()

    record = await session.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
    if record is None or record.revoked:
        raise InvalidRefreshToken()

    record.revoked = True
    user = await session.get(User, uuid.UUID(sub))
    if user is None:
        raise InvalidRefreshToken()
    await session.flush()
    return await issue_token_pair(session, user)
