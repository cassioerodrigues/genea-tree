# Genea Tree — Backend

API FastAPI da plataforma Genea Tree.

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 async (asyncpg) · Alembic · PostgreSQL 16 · Redis 7 · Celery.

## Estrutura

```
app/
├── api/v1/     # routers FastAPI (a ser preenchido nas issues de auth/CRUD)
├── core/
│   ├── config.py    # Pydantic Settings (.env)
│   └── logging.py   # JSON logging via dictConfig
├── db/
│   ├── base.py      # DeclarativeBase + naming convention
│   └── session.py   # async engine, AsyncSessionLocal, get_db
├── models/     # User, Tree, Person, Relationship
├── schemas/    # Pydantic schemas (próximas issues)
├── services/   # lógica de negócio
├── workers/    # Celery app/tasks
└── main.py     # FastAPI app + lifespan + /health
alembic/
├── env.py              # async runner, usa settings.database_url
├── script.py.mako
└── versions/           # migrations
tests/          # pytest + httpx
```

## Rodando localmente

Via Docker Compose (recomendado — inclui Postgres e Redis):

```bash
cp ../.env.example ../.env
docker compose --env-file ../.env -f ../docker/docker-compose.yml up --build
docker compose --env-file ../.env -f ../docker/docker-compose.yml exec api alembic upgrade head
```

`GET /health` retorna `{"status": "ok", "version": "<app_version>"}`.

## Configuração

Via `.env` (ver `../.env.example`):

| Var | Padrão | Uso |
|---|---|---|
| `APP_VERSION` | `0.1.0` | Reportado em `/health` |
| `ENVIRONMENT` | `development` | Logs/telemetria |
| `LOG_LEVEL` | `INFO` | Nível raiz do logger JSON |
| `CORS_ORIGINS` | `http://localhost:3000` | Lista CSV de origens |
| `DATABASE_URL` | `postgresql+asyncpg://…` | SQLAlchemy async + Alembic |
| `REDIS_URL` | `redis://redis:6379/0` | Celery broker / cache |

## Banco de Dados & Migrations

- `Base = DeclarativeBase` em `app/db/base.py` com `MetaData(naming_convention=…)` para nomes determinísticos de índices e constraints.
- `app/db/session.py` expõe `engine`, `AsyncSessionLocal` e a dependência FastAPI `get_db`.
- Alembic roda com `async_engine_from_config` e importa `app.models` para autogenerate.

Comandos:

```bash
alembic upgrade head                       # aplica migrations
alembic revision --autogenerate -m "..."   # gera nova migration após alterar models
alembic downgrade -1                       # reverte a última
```

## Modelos (Tech Spec §4.1)

- **users** `(id UUID, email unique, password_hash, created_at, settings JSONB)`
- **trees** `(id, owner_id → users, name, visibility CHECK IN ('private','shared','public'), created_at)`
- **persons** `(id, tree_id → trees, full_name NOT NULL, gender, birth_*, death_*, notes, extra JSONB, created_at, updated_at)`
- **relationships** `(id, tree_id, person_a_id, person_b_id, rel_type CHECK IN ('parent','spouse'), start_date, end_date, metadata JSONB)` com `UNIQUE(tree_id, person_a_id, person_b_id, rel_type)`

## Qualidade

Os testes exigem o stack de compose rodando (Postgres real):

```bash
docker compose --env-file ../.env -f ../docker/docker-compose.yml exec api ruff check .
docker compose --env-file ../.env -f ../docker/docker-compose.yml exec api pytest -q
```
