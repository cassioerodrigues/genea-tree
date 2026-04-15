# Genea Tree — Backend

API FastAPI da plataforma Genea Tree.

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 · Alembic · PostgreSQL · Redis · Celery.

## Estrutura

```
app/
├── api/v1/     # routers FastAPI
├── core/       # config, segurança, dependências
├── db/         # engine, session, base
├── models/     # SQLAlchemy models
├── schemas/    # Pydantic schemas
├── services/   # lógica de negócio
└── workers/    # tasks Celery
alembic/        # migrations
tests/          # pytest
```

## Rodando localmente

Via Docker Compose (recomendado):

```bash
cp .env.example .env
docker compose --env-file .env -f docker/docker-compose.yml up --build
```

A API fica em `http://localhost/health` (via Caddy).

Sem Docker:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

`GET /health` deve retornar `{"status": "ok"}`.

## Qualidade

```bash
ruff check .
ruff format --check .
pytest
```
