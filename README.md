# Genea Tree

Plataforma web para criação, gestão e enriquecimento de árvores genealógicas. Ver `doc/Product Requirements.md` para o produto e `doc/Technical Specification.md` para a arquitetura.

## Stack

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy 2.0 async + Alembic + Celery
- **Frontend:** React + TypeScript + Vite + React Flow (scaffold na Fase 2)
- **Dados:** PostgreSQL 16 + Redis 7
- **Infra:** Docker Compose + Caddy + GitHub Actions

## Layout do monorepo

```
backend/    # API FastAPI + models + migrations
frontend/   # SPA React (scaffold na Fase 2)
docker/     # docker-compose + Caddyfile
doc/        # PRD e Technical Specification
.github/    # workflows CI
```

## Rodando localmente

```bash
cp .env.example .env
docker compose --env-file .env -f docker/docker-compose.yml up --build
```

Serviços: `api` (FastAPI em :8000), `postgres` (:5432), `redis` (:6379), `worker` (Celery), `caddy` (reverse proxy).

Verifique a API:

```bash
curl http://localhost/health
# {"status":"ok","version":"0.1.0"}
```

## Migrations

Aplicar o schema no Postgres:

```bash
docker compose --env-file .env -f docker/docker-compose.yml exec api alembic upgrade head
```

Gerar nova migration após alterar models:

```bash
docker compose --env-file .env -f docker/docker-compose.yml exec api \
  alembic revision --autogenerate -m "descrição"
```

## Funcionalidades implementadas

- **#1** Estrutura de monorepo (`backend/`, `frontend/`, `docker/`, `.github/`) e `pyproject.toml` com ruff, pytest e mypy.
- **#2** Stack Docker Compose: `api`, `worker`, `postgres:16`, `redis:7`, `caddy` com volumes e healthchecks.
- **#3** Bootstrap FastAPI — `GET /health` retorna `{status, version}`, CORS configurável via env, logging estruturado em JSON e configuração via Pydantic Settings.
- **#4** Camada de persistência — SQLAlchemy 2.0 async com asyncpg, `AsyncSessionLocal` + dependência `get_db`, Alembic configurado (async `env.py`, naming convention nas constraints).
- **#5** Modelos core — `User`, `Tree`, `Person`, `Relationship` seguindo Tech Spec §4.1, com UNIQUE em `(tree_id, person_a_id, person_b_id, rel_type)`, CHECKs em `visibility` e `rel_type`, índices em FKs e migration inicial.
- **#6** `POST /api/v1/auth/register` — cria conta com e-mail único e senha bcrypt (custo 12).
- **#7** `POST /api/v1/auth/login` — autentica e emite par de tokens JWT (access 15 min, refresh 30 d).
- **#8** `POST /api/v1/auth/refresh` — rotaciona refresh token com revogação do anterior (proteção a replay).
- **#9** Middleware JWT (`get_current_user`) + `GET /api/v1/auth/me`. Rate limiting via slowapi (10 req/min auth, 60 req/min global).
- **#10** CRUD Pessoas com filtros (`q`, `place`, `year_from`, `year_to`) e isolamento por árvore.
- **#11** CRUD Relacionamentos com validação de tipo (`parent`/`spouse`), proteção contra auto-relacionamento e pessoa de outra árvore.
- **#12** Suite de testes pytest-asyncio — 32 testes, 95% de cobertura (greenlet concurrency).
- **#13** Workflow CI GitHub Actions — jobs `lint` (ruff), `test` (postgres+redis services) e `build` (docker build).
- **#14** Dockerfile multi-stage com usuário não-root e HEALTHCHECK; Caddyfile com auto-TLS e cabeçalhos de segurança.

## Status

**Fase 1 concluída** — autenticação JWT, CRUD de pessoas e relacionamentos, 32 testes com 95% de cobertura, CI e hardening de infra. Issues concluídas: #1–#14.
