# Genea Tree — Fase 1 Backlog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar as 9 issues abertas do backlog (#6–#14) que completam a Fase 1 da plataforma Genea Tree: autenticação JWT completa, CRUD de pessoas/relacionamentos, suíte de testes, CI GitHub Actions e Dockerfile multi-stage + Caddy hardening.

**Architecture:** Backend FastAPI com camadas separadas — `api/v1/` (routers), `schemas/` (Pydantic), `services/` (lógica de negócio com isolamento por `tree_id`), `core/` (config/security). Auth via JWT access (15min) + refresh token persistido em tabela dedicada para rotação/invalidação. Testes integram contra Postgres real via fixture transacional. CI roda ruff + pytest (com Postgres/Redis services) + docker build.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, python-jose, passlib[bcrypt], slowapi (rate-limit), pytest + pytest-asyncio + pytest-cov + httpx, Docker multi-stage, Caddy 2, GitHub Actions.

---

## File Structure

**Create:**
- `backend/app/core/security.py` — hash de senha (bcrypt), encode/decode JWT, geração de tokens
- `backend/app/core/deps.py` — dependências FastAPI: `get_current_user`, `get_current_tree` (autorização)
- `backend/app/core/rate_limit.py` — instância slowapi + handler
- `backend/app/schemas/auth.py` — `UserCreate`, `UserRead`, `LoginRequest`, `TokenPair`, `RefreshRequest`
- `backend/app/schemas/person.py` — `PersonCreate`, `PersonUpdate`, `PersonRead`, `PersonFilters`
- `backend/app/schemas/relationship.py` — `RelationshipCreate`, `RelationshipUpdate`, `RelationshipRead`
- `backend/app/services/auth.py` — register/login/refresh/rotate_refresh_token
- `backend/app/services/persons.py` — CRUD pessoas com isolamento por `tree_id`
- `backend/app/services/relationships.py` — CRUD relacionamentos com validações
- `backend/app/models/refresh_token.py` — modelo `RefreshToken`
- `backend/app/api/v1/auth.py` — router `/auth`
- `backend/app/api/v1/persons.py` — router pessoas
- `backend/app/api/v1/relationships.py` — router `/relationships`
- `backend/alembic/versions/<hash>_add_refresh_tokens.py` — migration
- `backend/tests/conftest.py` — fixtures (app, db, cliente autenticado)
- `backend/tests/test_auth.py`
- `backend/tests/test_persons.py`
- `backend/tests/test_relationships.py`
- `.github/workflows/ci.yml`

**Modify:**
- `backend/app/core/config.py` — adicionar `jwt_secret`, `jwt_access_ttl_minutes`, `jwt_refresh_ttl_days`, `bcrypt_rounds`
- `backend/app/main.py` — montar routers v1, handler de rate-limit, exception handlers
- `backend/app/models/__init__.py` — exportar `RefreshToken`
- `backend/pyproject.toml` — adicionar `slowapi`, `pytest-cov`, `email-validator`
- `backend/Dockerfile` — multi-stage (builder+runtime), user não-root, healthcheck
- `docker/Caddyfile` — HTTPS automático Let's Encrypt com domínio via env
- `backend/tests/test_models.py` — permanece; novos testes separados
- `.env.example` — documentar JWT_SECRET
- `README.md` — atualizar status Fase 1

---

## Pre-flight: Prepare Branch & Dependencies

### Task 0: Criar branch de trabalho e adicionar dependências

> **Status:** ✅ Concluída em 2026-04-16 — commit `c8d5f40`. Branch `feature/phase-1-backlog` criada; `slowapi`, `email-validator`, `pytest-cov` adicionados e imagem `genea-tree-api` rebuildada.

**Files:**
- Modify: `backend/pyproject.toml`

- [x] **Step 1: Criar branch feature**

```bash
cd /srv/genea-tree && git checkout -b feature/phase-1-backlog
```

Expected: `Switched to a new branch 'feature/phase-1-backlog'`

- [x] **Step 2: Adicionar dependências no pyproject.toml**

Edit `backend/pyproject.toml` — adicione `slowapi>=0.1.9` e `email-validator>=2.1` à lista `dependencies`, e `pytest-cov>=5` à lista `dev`:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "asyncpg>=0.29",
    "python-jose[cryptography]>=3.3",
    "passlib[bcrypt]>=1.7",
    "celery>=5.4",
    "redis>=5.0",
    "slowapi>=0.1.9",
    "email-validator>=2.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5",
    "httpx>=0.27",
    "ruff>=0.5",
    "mypy>=1.10",
]
```

- [x] **Step 3: Reinstalar dependências no container**

Run:
```bash
cd /srv/genea-tree && docker compose --env-file .env -f docker/docker-compose.yml up -d postgres redis
docker compose --env-file .env -f docker/docker-compose.yml build api
```

Expected: Build conclui sem erro.

- [x] **Step 4: Commit**

```bash
cd /srv/genea-tree && git add backend/pyproject.toml && \
  git commit -m "chore: add slowapi, email-validator, pytest-cov deps"
```

---

## Issue #6 — POST /auth/register

### Task 1: Config de segurança (JWT + bcrypt)

> **Status:** ✅ Concluída em 2026-04-16 — commit `8a69b0f`. `Settings` agora expõe `jwt_secret`, `jwt_algorithm`, `jwt_access_ttl_minutes`, `jwt_refresh_ttl_days`, `bcrypt_rounds`, `rate_limit_per_minute`, `auth_rate_limit_per_minute`.

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example` (já tem os valores — apenas confirmar)

- [x] **Step 1: Adicionar campos de segurança ao Settings**

Edit `backend/app/core/config.py` substituindo o corpo da classe:

```python
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Genea Tree"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"

    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    database_url: str = "postgresql+asyncpg://genea:change-me@postgres:5432/genea"
    redis_url: str = "redis://redis:6379/0"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 30
    bcrypt_rounds: int = 12

    rate_limit_per_minute: int = 60
    auth_rate_limit_per_minute: int = 10

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


settings = Settings()
```

- [x] **Step 2: Confirmar .env.example tem as entradas**

`backend/.env.example` já possui `JWT_SECRET`, `JWT_ACCESS_TTL_MINUTES`, `JWT_REFRESH_TTL_DAYS`. Sem edição necessária. (Nota: está em `/srv/genea-tree/.env.example`, na raiz do repo, não em `backend/`.)

- [x] **Step 3: Commit**

```bash
cd /srv/genea-tree && git add backend/app/core/config.py && \
  git commit -m "feat(core): add JWT and bcrypt settings"
```

---

### Task 2: Utilitários de segurança (hash + JWT)

> **Status:** ✅ Concluída em 2026-04-16 — commit `74b33dd`. 5/5 testes passando. **Desvio:** adicionado pin `bcrypt<5` ao `pyproject.toml` porque `bcrypt` 5.x é incompatível com `passlib` 1.7.4 (remove `__about__` e passa a rejeitar todas as senhas com `ValueError: password cannot be longer than 72 bytes`).

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/tests/test_security.py`
- Modify (desvio do plano): `backend/pyproject.toml` — pin `bcrypt<5`

- [x] **Step 1: Escrever teste para hash/verify de senha**

Create `backend/tests/test_security.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password() -> None:
    pwd = "super-secret-password"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_access_token_round_trip() -> None:
    token = create_access_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_refresh_token_round_trip() -> None:
    token, jti = create_refresh_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "refresh"
    assert payload["jti"] == jti


def test_decode_token_rejects_invalid_signature() -> None:
    bad = jwt.encode({"sub": "x"}, "other-secret", algorithm=settings.jwt_algorithm)
    with pytest.raises(Exception):
        decode_token(bad)


def test_access_token_expires() -> None:
    token = create_access_token("user-123", expires_delta=timedelta(seconds=-1))
    with pytest.raises(Exception):
        decode_token(token)
```

- [ ] **Step 2: Rodar teste (deve falhar por módulo não existir)**

Run: `docker compose -f docker/docker-compose.yml --env-file .env exec api pytest tests/test_security.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.security'`.

- [ ] **Step 3: Implementar `app/core/security.py`**

Create `backend/app/core/security.py`:

```python
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.bcrypt_rounds
)

ACCESS_TYPE = "access"
REFRESH_TYPE = "refresh"


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd_context.verify(password, hashed)


def _encode(
    subject: str, token_type: str, expires_delta: timedelta, extra: dict[str, Any] | None = None
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "type": token_type,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    delta = expires_delta or timedelta(minutes=settings.jwt_access_ttl_minutes)
    return _encode(subject, ACCESS_TYPE, delta)


def create_refresh_token(
    subject: str, expires_delta: timedelta | None = None
) -> tuple[str, str]:
    delta = expires_delta or timedelta(days=settings.jwt_refresh_ttl_days)
    jti = uuid.uuid4().hex
    return _encode(subject, REFRESH_TYPE, delta, {"jti": jti}), jti


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("invalid_token") from exc
```

- [ ] **Step 4: Rodar teste (deve passar)**

Run: `docker compose -f docker/docker-compose.yml --env-file .env exec api pytest tests/test_security.py -v`

Expected: 5 testes PASS.

- [ ] **Step 5: Commit**

```bash
cd /srv/genea-tree && git add backend/app/core/security.py backend/tests/test_security.py && \
  git commit -m "feat(core): add security utils (bcrypt + JWT encode/decode)"
```

---

### Task 3: Schemas de autenticação

**Files:**
- Create: `backend/app/schemas/auth.py`

- [ ] **Step 1: Implementar schemas Pydantic**

Create `backend/app/schemas/auth.py`:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
```

- [ ] **Step 2: Commit**

```bash
cd /srv/genea-tree && git add backend/app/schemas/auth.py && \
  git commit -m "feat(schemas): add auth schemas"
```

---

### Task 4: Service — register

**Files:**
- Create: `backend/app/services/auth.py`

- [ ] **Step 1: Implementar `register_user`**

Create `backend/app/services/auth.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.schemas.auth import UserCreate


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
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
```

- [ ] **Step 2: Commit**

```bash
cd /srv/genea-tree && git add backend/app/services/auth.py && \
  git commit -m "feat(services): add register_user"
```

---

### Task 5: Router — POST /auth/register + rate limit global

**Files:**
- Create: `backend/app/core/rate_limit.py`
- Create: `backend/app/api/v1/auth.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Criar limiter**

Create `backend/app/core/rate_limit.py`:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])
```

- [ ] **Step 2: Criar router auth com /register**

Create `backend/app/api/v1/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.auth import UserCreate, UserRead
from app.services.auth import EmailAlreadyRegistered, register_user

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
```

- [ ] **Step 3: Montar router e rate-limit em main.py**

Replace `backend/app/main.py` with:

```python
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import auth as auth_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.rate_limit import limiter

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "application_startup",
        extra={
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        },
    )
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

app.state.limiter = limiter


def _rate_limit_handler(request, exc: RateLimitExceeded):  # type: ignore[no-untyped-def]
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=429, content={"detail": "rate_limited"})


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    version: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version)


app.include_router(auth_router.router, prefix="/api/v1")
```

- [ ] **Step 4: Commit**

```bash
cd /srv/genea-tree && git add backend/app/core/rate_limit.py backend/app/api/v1/auth.py backend/app/main.py && \
  git commit -m "feat(api): POST /auth/register with rate limiting (closes #6)"
```

---

## Issue #7 — POST /auth/login

### Task 6: Modelo RefreshToken + migration

**Files:**
- Create: `backend/app/models/refresh_token.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/<hash>_add_refresh_tokens.py`

- [ ] **Step 1: Criar modelo**

Create `backend/app/models/refresh_token.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 2: Exportar em models/__init__.py**

Edit `backend/app/models/__init__.py`:

```python
from app.models.person import Person
from app.models.refresh_token import RefreshToken
from app.models.relationship import Relationship
from app.models.tree import Tree
from app.models.user import User

__all__ = ["Person", "RefreshToken", "Relationship", "Tree", "User"]
```

- [ ] **Step 3: Gerar migration**

Run:
```bash
cd /srv/genea-tree && docker compose --env-file .env -f docker/docker-compose.yml exec api \
  alembic revision --autogenerate -m "add refresh_tokens"
```

Expected: Arquivo criado em `backend/alembic/versions/`. Revisar para garantir que contém `create_table('refresh_tokens', ...)` com os campos listados e índices em `user_id` e `jti`.

- [ ] **Step 4: Aplicar migration**

Run:
```bash
cd /srv/genea-tree && docker compose --env-file .env -f docker/docker-compose.yml exec api alembic upgrade head
```

Expected: `Running upgrade ... -> <hash>, add refresh_tokens`.

- [ ] **Step 5: Commit**

```bash
cd /srv/genea-tree && git add backend/app/models/refresh_token.py backend/app/models/__init__.py backend/alembic/versions/ && \
  git commit -m "feat(models): add RefreshToken + migration"
```

---

### Task 7: Service — login + emissão de par de tokens

**Files:**
- Modify: `backend/app/services/auth.py`

- [ ] **Step 1: Adicionar `authenticate` e `issue_token_pair`**

Append to `backend/app/services/auth.py`:

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenPair


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
```

**Note:** Remova imports duplicados; consolide no topo do arquivo:

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
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
```

- [ ] **Step 2: Commit**

```bash
cd /srv/genea-tree && git add backend/app/services/auth.py && \
  git commit -m "feat(services): add authenticate + issue_token_pair"
```

---

### Task 8: Router — POST /auth/login

**Files:**
- Modify: `backend/app/api/v1/auth.py`

- [ ] **Step 1: Adicionar endpoint /login**

Replace `backend/app/api/v1/auth.py` with:

```python
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenPair, UserCreate, UserRead
from app.services.auth import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    authenticate,
    issue_token_pair,
    register_user,
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
```

- [ ] **Step 2: Commit**

```bash
cd /srv/genea-tree && git add backend/app/api/v1/auth.py && \
  git commit -m "feat(api): POST /auth/login (closes #7)"
```

---

## Issue #9 — Middleware JWT + GET /auth/me

*(Executado antes do #8 porque o refresh precisa validar identidade.)*

### Task 9: Dependência `get_current_user`

**Files:**
- Create: `backend/app/core/deps.py`

- [ ] **Step 1: Criar dependência**

Create `backend/app/core/deps.py`:

```python
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ACCESS_TYPE, decode_token
from app.db.session import get_db
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_credentials"
        )
    try:
        payload = decode_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token"
        ) from exc
    if payload.get("type") != ACCESS_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="wrong_token_type"
        )
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_subject"
        ) from exc
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found"
        )
    return user
```

- [ ] **Step 2: Commit**

```bash
cd /srv/genea-tree && git add backend/app/core/deps.py && \
  git commit -m "feat(core): add get_current_user dependency"
```

---

### Task 10: Endpoint GET /auth/me

**Files:**
- Modify: `backend/app/api/v1/auth.py`

- [ ] **Step 1: Adicionar endpoint /me**

Append ao final de `backend/app/api/v1/auth.py` (e ajustar imports):

```python
from app.core.deps import get_current_user
from app.models.user import User


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
```

- [ ] **Step 2: Commit**

```bash
cd /srv/genea-tree && git add backend/app/api/v1/auth.py && \
  git commit -m "feat(api): GET /auth/me (closes #9)"
```

---

## Issue #8 — POST /auth/refresh

### Task 11: Service — `rotate_refresh_token`

**Files:**
- Modify: `backend/app/services/auth.py`

- [ ] **Step 1: Adicionar rotação**

Append to `backend/app/services/auth.py`:

```python
from app.core.security import REFRESH_TYPE, decode_token


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

    stmt = select(RefreshToken).where(RefreshToken.jti == jti)
    record = await session.scalar(stmt)
    if record is None or record.revoked:
        raise InvalidRefreshToken()

    record.revoked = True
    user = await session.get(User, record.user_id)
    if user is None:
        raise InvalidRefreshToken()
    await session.flush()
    return await issue_token_pair(session, user)
```

*(Consolide os imports de `decode_token` e `REFRESH_TYPE` no topo do arquivo junto aos outros de `app.core.security`.)*

- [ ] **Step 2: Commit**

```bash
cd /srv/genea-tree && git add backend/app/services/auth.py && \
  git commit -m "feat(services): add rotate_refresh_token"
```

---

### Task 12: Router — POST /auth/refresh

**Files:**
- Modify: `backend/app/api/v1/auth.py`

- [ ] **Step 1: Adicionar endpoint /refresh**

Append to `backend/app/api/v1/auth.py` (adicione `RefreshRequest` ao import de `app.schemas.auth` e `InvalidRefreshToken`, `rotate_refresh_token` aos imports de `app.services.auth`):

```python
from app.schemas.auth import RefreshRequest
from app.services.auth import InvalidRefreshToken, rotate_refresh_token


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
```

- [ ] **Step 2: Commit**

```bash
cd /srv/genea-tree && git add backend/app/api/v1/auth.py && \
  git commit -m "feat(api): POST /auth/refresh with rotation (closes #8)"
```

---

## Issue #10 — CRUD Pessoas

### Task 13: Helper para garantir acesso à tree (autorização)

**Files:**
- Modify: `backend/app/core/deps.py`

- [ ] **Step 1: Adicionar `get_tree_for_user`**

Append to `backend/app/core/deps.py`:

```python
from sqlalchemy import select

from app.models.tree import Tree


async def get_tree_for_user(
    tree_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Tree:
    tree = await session.scalar(
        select(Tree).where(Tree.id == tree_id, Tree.owner_id == current_user.id)
    )
    if tree is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tree_not_found")
    return tree
```

*(Consolide `from sqlalchemy import select` no topo.)*

- [ ] **Step 2: Commit**

```bash
cd /srv/genea-tree && git add backend/app/core/deps.py && \
  git commit -m "feat(core): add get_tree_for_user dep"
```

---

### Task 14: Schemas de pessoa

**Files:**
- Create: `backend/app/schemas/person.py`

- [ ] **Step 1: Implementar**

Create `backend/app/schemas/person.py`:

```python
import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PersonBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    gender: str | None = None
    birth_date: date | None = None
    birth_date_approx: str | None = None
    birth_place: str | None = None
    death_date: date | None = None
    death_date_approx: str | None = None
    death_place: str | None = None
    notes: str | None = None
    extra: dict[str, Any] | None = None


class PersonCreate(PersonBase):
    pass


class PersonUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    gender: str | None = None
    birth_date: date | None = None
    birth_date_approx: str | None = None
    birth_place: str | None = None
    death_date: date | None = None
    death_date_approx: str | None = None
    death_place: str | None = None
    notes: str | None = None
    extra: dict[str, Any] | None = None


class PersonRead(PersonBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tree_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 2: Commit**

```bash
cd /srv/genea-tree && git add backend/app/schemas/person.py && \
  git commit -m "feat(schemas): add person schemas"
```

---

### Task 15: Service — CRUD pessoas

**Files:**
- Create: `backend/app/services/persons.py`

- [ ] **Step 1: Implementar**

Create `backend/app/services/persons.py`:

```python
import uuid
from collections.abc import Sequence

from sqlalchemy import extract, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.person import Person
from app.schemas.person import PersonCreate, PersonUpdate


class PersonNotFound(Exception):
    pass


async def create_person(
    session: AsyncSession, tree_id: uuid.UUID, data: PersonCreate
) -> Person:
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


async def update_person(
    session: AsyncSession, person: Person, data: PersonUpdate
) -> Person:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(person, key, value)
    await session.commit()
    await session.refresh(person)
    return person


async def delete_person(session: AsyncSession, person: Person) -> None:
    await session.delete(person)
    await session.commit()
```

- [ ] **Step 2: Commit**

```bash
cd /srv/genea-tree && git add backend/app/services/persons.py && \
  git commit -m "feat(services): add persons CRUD"
```

---

### Task 16: Router — Pessoas

**Files:**
- Create: `backend/app/api/v1/persons.py`
- Modify: `backend/app/main.py` (incluir router)

- [ ] **Step 1: Criar router**

Create `backend/app/api/v1/persons.py`:

```python
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
    persons = await list_persons(session, tree.id, q=q, place=place, year_from=year_from, year_to=year_to)
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person_not_found") from exc
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person_not_found") from exc
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person_not_found") from exc
    await delete_person(session, person)
```

- [ ] **Step 2: Registrar routers em main.py**

Edit `backend/app/main.py`, ajuste o bloco de inclusão:

```python
from app.api.v1 import auth as auth_router
from app.api.v1 import persons as persons_router

...

app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(persons_router.tree_router, prefix="/api/v1")
app.include_router(persons_router.person_router, prefix="/api/v1")
```

- [ ] **Step 3: Commit**

```bash
cd /srv/genea-tree && git add backend/app/api/v1/persons.py backend/app/main.py && \
  git commit -m "feat(api): CRUD pessoas (closes #10)"
```

---

## Issue #11 — CRUD Relacionamentos

### Task 17: Schemas de relacionamento

**Files:**
- Create: `backend/app/schemas/relationship.py`

- [ ] **Step 1: Implementar**

Create `backend/app/schemas/relationship.py`:

```python
import uuid
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

RelType = Literal["parent", "spouse"]


class RelationshipCreate(BaseModel):
    tree_id: uuid.UUID
    person_a_id: uuid.UUID
    person_b_id: uuid.UUID
    rel_type: RelType
    start_date: date | None = None
    end_date: date | None = None
    metadata_: dict[str, Any] | None = None


class RelationshipUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    metadata_: dict[str, Any] | None = None


class RelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tree_id: uuid.UUID
    person_a_id: uuid.UUID
    person_b_id: uuid.UUID
    rel_type: RelType
    start_date: date | None
    end_date: date | None
    metadata_: dict[str, Any] | None
```

- [ ] **Step 2: Commit**

```bash
cd /srv/genea-tree && git add backend/app/schemas/relationship.py && \
  git commit -m "feat(schemas): add relationship schemas"
```

---

### Task 18: Service — CRUD relacionamentos

**Files:**
- Create: `backend/app/services/relationships.py`

- [ ] **Step 1: Implementar**

Create `backend/app/services/relationships.py`:

```python
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.person import Person
from app.models.relationship import Relationship
from app.schemas.relationship import RelationshipCreate, RelationshipUpdate


class RelationshipNotFound(Exception):
    pass


class DuplicateRelationship(Exception):
    pass


class InvalidRelationship(Exception):
    pass


async def _ensure_same_tree(
    session: AsyncSession, tree_id: uuid.UUID, person_a_id: uuid.UUID, person_b_id: uuid.UUID
) -> None:
    if person_a_id == person_b_id:
        raise InvalidRelationship()
    stmt = select(Person.id).where(
        Person.tree_id == tree_id, Person.id.in_([person_a_id, person_b_id])
    )
    result = await session.execute(stmt)
    ids = {row[0] for row in result.all()}
    if len(ids) != 2:
        raise InvalidRelationship()


async def create_relationship(
    session: AsyncSession, data: RelationshipCreate
) -> Relationship:
    await _ensure_same_tree(session, data.tree_id, data.person_a_id, data.person_b_id)
    rel = Relationship(
        tree_id=data.tree_id,
        person_a_id=data.person_a_id,
        person_b_id=data.person_b_id,
        rel_type=data.rel_type,
        start_date=data.start_date,
        end_date=data.end_date,
        metadata_=data.metadata_,
    )
    session.add(rel)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateRelationship() from exc
    await session.refresh(rel)
    return rel


async def get_relationship(
    session: AsyncSession, relationship_id: uuid.UUID
) -> Relationship:
    rel = await session.get(Relationship, relationship_id)
    if rel is None:
        raise RelationshipNotFound()
    return rel


async def update_relationship(
    session: AsyncSession, rel: Relationship, data: RelationshipUpdate
) -> Relationship:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(rel, key, value)
    await session.commit()
    await session.refresh(rel)
    return rel


async def delete_relationship(session: AsyncSession, rel: Relationship) -> None:
    await session.delete(rel)
    await session.commit()
```

- [ ] **Step 2: Commit**

```bash
cd /srv/genea-tree && git add backend/app/services/relationships.py && \
  git commit -m "feat(services): add relationships CRUD"
```

---

### Task 19: Router — Relacionamentos

**Files:**
- Create: `backend/app/api/v1/relationships.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Criar router**

Create `backend/app/api/v1/relationships.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.tree import Tree
from app.models.user import User
from app.schemas.relationship import (
    RelationshipCreate,
    RelationshipRead,
    RelationshipUpdate,
)
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


async def _assert_tree_owner(
    session: AsyncSession, user: User, tree_id: uuid.UUID
) -> None:
    stmt = select(Tree).where(Tree.id == tree_id, Tree.owner_id == user.id)
    tree = await session.scalar(stmt)
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
```

- [ ] **Step 2: Registrar router em main.py**

Edit `backend/app/main.py` — adicionar import e include:

```python
from app.api.v1 import relationships as rel_router

...

app.include_router(rel_router.router, prefix="/api/v1")
```

- [ ] **Step 3: Commit**

```bash
cd /srv/genea-tree && git add backend/app/api/v1/relationships.py backend/app/main.py && \
  git commit -m "feat(api): CRUD relacionamentos (closes #11)"
```

---

## Issue #12 — Testes pytest

### Task 20: Fixtures em conftest

**Files:**
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Implementar fixtures**

Create `backend/tests/conftest.py`:

```python
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.person import Person
from app.models.refresh_token import RefreshToken
from app.models.relationship import Relationship
from app.models.tree import Tree
from app.models.user import User


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
async def tree_of_user(
    session: AsyncSession, registered_user: dict[str, str]
) -> Tree:
    tree = Tree(owner_id=uuid.UUID(registered_user["id"]), name="Test Tree", visibility="private")
    session.add(tree)
    await session.commit()
    await session.refresh(tree)
    return tree
```

- [ ] **Step 2: Commit**

```bash
cd /srv/genea-tree && git add backend/tests/conftest.py && \
  git commit -m "test: add fixtures (db cleanup, clients, tree)"
```

---

### Task 21: Testes de autenticação

**Files:**
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Implementar**

Create `backend/tests/test_auth.py`:

```python
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
async def test_login_wrong_password(client: httpx.AsyncClient, registered_user: dict[str, str]) -> None:
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

    # Using the old refresh again must fail (revoked)
    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert reuse.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_token(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user(auth_client: httpx.AsyncClient, registered_user: dict[str, str]) -> None:
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
```

- [ ] **Step 2: Rodar**

```bash
cd /srv/genea-tree && docker compose -f docker/docker-compose.yml --env-file .env exec api pytest tests/test_auth.py -v
```

Expected: 9 PASS.

- [ ] **Step 3: Commit**

```bash
cd /srv/genea-tree && git add backend/tests/test_auth.py && \
  git commit -m "test: auth (register/login/refresh/me)"
```

---

### Task 22: Testes de pessoas

**Files:**
- Create: `backend/tests/test_persons.py`

- [ ] **Step 1: Implementar**

Create `backend/tests/test_persons.py`:

```python
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
async def test_list_persons_with_filter(
    auth_client: httpx.AsyncClient, tree_of_user: Tree
) -> None:
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

    resp = await auth_client.get(
        f"/api/v1/trees/{tree_of_user.id}/persons", params={"q": "Alice"}
    )
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
    # Create a person with auth_client
    create = await auth_client.post(
        f"/api/v1/trees/{tree_of_user.id}/persons", json={"full_name": "Private"}
    )
    pid = create.json()["id"]

    # Second user registers and tries to access
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
```

- [ ] **Step 2: Rodar**

```bash
cd /srv/genea-tree && docker compose -f docker/docker-compose.yml --env-file .env exec api pytest tests/test_persons.py -v
```

Expected: 6 PASS.

- [ ] **Step 3: Commit**

```bash
cd /srv/genea-tree && git add backend/tests/test_persons.py && \
  git commit -m "test: persons CRUD and tree isolation"
```

---

### Task 23: Testes de relacionamentos

**Files:**
- Create: `backend/tests/test_relationships.py`

- [ ] **Step 1: Implementar**

Create `backend/tests/test_relationships.py`:

```python
import httpx
import pytest

from app.models.tree import Tree


async def _create_person(client: httpx.AsyncClient, tree_id, name: str) -> str:
    resp = await client.post(
        f"/api/v1/trees/{tree_id}/persons", json={"full_name": name}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_relationship(
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
async def test_delete_relationship(
    auth_client: httpx.AsyncClient, tree_of_user: Tree
) -> None:
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
```

- [ ] **Step 2: Rodar**

```bash
cd /srv/genea-tree && docker compose -f docker/docker-compose.yml --env-file .env exec api pytest tests/test_relationships.py -v
```

Expected: 5 PASS.

- [ ] **Step 3: Rodar toda a suíte com cobertura**

```bash
cd /srv/genea-tree && docker compose -f docker/docker-compose.yml --env-file .env exec api \
  pytest --cov=app --cov-report=term-missing
```

Expected: Todos os testes PASS, cobertura `app/services/auth.py` e `app/services/persons.py` ≥ 80%.

- [ ] **Step 4: Commit**

```bash
cd /srv/genea-tree && git add backend/tests/test_relationships.py && \
  git commit -m "test: relationships CRUD (closes #12)"
```

---

## Issue #13 — CI GitHub Actions

### Task 24: Workflow CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Criar workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    name: Lint (ruff)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - name: Install ruff
        run: pip install "ruff>=0.5"
      - name: ruff check
        working-directory: backend
        run: ruff check .
      - name: ruff format --check
        working-directory: backend
        run: ruff format --check .

  test:
    name: Tests (pytest)
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: genea
          POSTGRES_PASSWORD: change-me
          POSTGRES_DB: genea
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U genea -d genea"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10
    env:
      DATABASE_URL: postgresql+asyncpg://genea:change-me@localhost:5432/genea
      REDIS_URL: redis://localhost:6379/0
      JWT_SECRET: ci-secret
      ENVIRONMENT: test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - name: Install backend
        working-directory: backend
        run: pip install -e ".[dev]"
      - name: Alembic upgrade
        working-directory: backend
        run: alembic upgrade head
      - name: pytest
        working-directory: backend
        run: pytest --cov=app --cov-report=term-missing

  build:
    name: Build docker image
    runs-on: ubuntu-latest
    needs: [lint, test]
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - name: Build API image
        uses: docker/build-push-action@v5
        with:
          context: backend
          file: backend/Dockerfile
          push: false
          tags: genea-tree-api:ci
```

- [ ] **Step 2: Commit**

```bash
cd /srv/genea-tree && git add .github/workflows/ci.yml && \
  git commit -m "ci: GitHub Actions lint + test + build (closes #13)"
```

---

## Issue #14 — Dockerfile multi-stage + Caddy

### Task 25: Dockerfile multi-stage com user não-root e healthcheck

**Files:**
- Modify: `backend/Dockerfile`

- [ ] **Step 1: Reescrever Dockerfile**

Replace `backend/Dockerfile` with:

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app

RUN pip install --prefix=/install ".[dev]"


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1000 app \
    && useradd  --system --uid 1000 --gid app --home-dir /app app

WORKDIR /app
COPY --from=builder /install /install
COPY --chown=app:app pyproject.toml README.md ./
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./alembic.ini

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Build e smoke test**

```bash
cd /srv/genea-tree && docker compose --env-file .env -f docker/docker-compose.yml build api
docker compose --env-file .env -f docker/docker-compose.yml up -d api postgres redis
sleep 5
curl -fsS http://localhost/health
```

Expected: `{"status":"ok","version":"0.1.0"}`.

- [ ] **Step 3: Commit**

```bash
cd /srv/genea-tree && git add backend/Dockerfile && \
  git commit -m "build: multi-stage Dockerfile, non-root user, healthcheck"
```

---

### Task 26: Caddyfile com HTTPS automático

**Files:**
- Modify: `docker/Caddyfile`

- [ ] **Step 1: Substituir Caddyfile**

Replace `docker/Caddyfile` with:

```
{
    email {$CADDY_EMAIL:admin@localhost}
}

{$CADDY_HOST:localhost} {
    encode zstd gzip
    reverse_proxy api:8000 {
        header_up X-Real-IP {remote_host}
    }
    header {
        Strict-Transport-Security "max-age=63072000"
        X-Content-Type-Options    "nosniff"
        X-Frame-Options           "DENY"
        Referrer-Policy           "strict-origin-when-cross-origin"
    }
}
```

> **Nota:** Caddy obtém certificado Let's Encrypt automaticamente se `CADDY_HOST` for um domínio público resolvido. Para local, usa `localhost` com TLS interno.

- [ ] **Step 2: Adicionar `CADDY_EMAIL` ao .env.example**

Append ao final de `backend/.env.example` (ou raiz `.env.example` — verificar qual é lido pelo compose: é a raiz):

Edit `/srv/genea-tree/.env.example`:

```
CADDY_EMAIL=admin@localhost
```

- [ ] **Step 3: Reload caddy**

```bash
cd /srv/genea-tree && docker compose --env-file .env -f docker/docker-compose.yml restart caddy
```

- [ ] **Step 4: Commit**

```bash
cd /srv/genea-tree && git add docker/Caddyfile .env.example && \
  git commit -m "build(caddy): HTTPS auto + security headers (closes #14)"
```

---

## Final: Verification & Push

### Task 27: Verificação completa

- [ ] **Step 1: Lint full**

```bash
cd /srv/genea-tree && docker compose -f docker/docker-compose.yml --env-file .env exec api ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 2: Format check**

```bash
cd /srv/genea-tree && docker compose -f docker/docker-compose.yml --env-file .env exec api ruff format --check .
```

Expected: No files would be reformatted.

Se falhar, rode `ruff format .` e commit.

- [ ] **Step 3: Suíte completa**

```bash
cd /srv/genea-tree && docker compose -f docker/docker-compose.yml --env-file .env exec api \
  pytest --cov=app --cov-report=term-missing -v
```

Expected: Todos os testes PASS.

- [ ] **Step 4: Atualizar README**

Edit `/srv/genea-tree/README.md` — substituir a seção "Funcionalidades implementadas" (linhas 53-60) adicionando:

```
- **#6–#9** Autenticação JWT — `POST /api/v1/auth/register` (bcrypt cost 12, e-mail único), `POST /auth/login` (access+refresh), `POST /auth/refresh` (rotação com invalidação do anterior), `GET /auth/me` (requer Bearer token). Rate-limit 10 req/min nos endpoints de auth.
- **#10** CRUD Pessoas — `GET/POST /trees/{tid}/persons` (filtros `q`, `place`, `year_from`, `year_to`) e `GET/PATCH/DELETE /persons/{id}` com isolamento por tree.
- **#11** CRUD Relacionamentos — `POST/PATCH/DELETE /relationships` com validação de mesma tree, `rel_type ∈ {parent, spouse}`, 409 em duplicata.
- **#12** Testes pytest + httpx + pytest-asyncio com fixtures transacionais; cobertura ≥ 80% em auth/services.
- **#13** CI GitHub Actions — jobs lint (ruff), test (postgres+redis services) e build docker.
- **#14** Dockerfile multi-stage + user não-root + healthcheck; Caddyfile com HTTPS automático via Let's Encrypt e security headers.
```

E atualizar seção "Status" para:

```
**Fase 1 concluída.** Issues fechadas: #1–#14. Próximo: Fase 2 (frontend React + visualização com React Flow).
```

- [ ] **Step 5: Commit README**

```bash
cd /srv/genea-tree && git add README.md && \
  git commit -m "docs: update README to reflect phase 1 completion"
```

- [ ] **Step 6: Push branch**

```bash
cd /srv/genea-tree && git push -u origin feature/phase-1-backlog
```

- [ ] **Step 7: Open PR (pedir confirmação ao usuário antes)**

Antes de abrir PR, confirmar com usuário. Se ok:

```bash
gh pr create --title "feat: Fase 1 backlog completa (#6–#14)" \
  --body "Implementa as 9 issues abertas da Fase 1: auth JWT com rotação de refresh, CRUD pessoas/relacionamentos, suíte de testes (cobertura ≥80%), CI GitHub Actions e Dockerfile multi-stage + Caddy hardening."
```

---

## Self-Review Checklist (writer-side)

- ✅ **Spec coverage:**
  - Issue #6 → Task 5
  - Issue #7 → Tasks 6–8
  - Issue #8 → Tasks 11–12
  - Issue #9 → Tasks 9–10
  - Issue #10 → Tasks 13–16
  - Issue #11 → Tasks 17–19
  - Issue #12 → Tasks 20–23
  - Issue #13 → Task 24
  - Issue #14 → Tasks 25–26
- ✅ **Placeholder scan:** Todos os steps mostram código/comando completo.
- ✅ **Type consistency:** `decode_token`, `create_access_token`, `create_refresh_token` (assinaturas), `TokenPair`, `UserRead`, `PersonRead`, `RelationshipRead` todos consistentes entre tasks.
- ✅ **Autenticação:** `get_current_user` usado em persons e relationships; `get_tree_for_user` somente em persons.
- ✅ **Rate limit:** Aplicado aos 3 endpoints de auth (register, login, refresh).
