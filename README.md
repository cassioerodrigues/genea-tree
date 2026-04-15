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

## Status

**Fase 1 em andamento** — fundação (setup, auth, CRUD pessoas/relacionamentos). Issues concluídas: #1, #2, #3, #4, #5. Próximas: auth (#6–#9), CRUD (#10, #11), testes (#12), CI (#13), Dockerfile hardening (#14).
