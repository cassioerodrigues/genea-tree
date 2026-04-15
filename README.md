# Genea Tree

Plataforma web para criação, gestão e enriquecimento de árvores genealógicas. Ver `doc/Product Requirements.md` para o produto e `doc/Technical Specification.md` para a arquitetura.

## Stack

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy + Celery
- **Frontend:** React + TypeScript + Vite + React Flow
- **Dados:** PostgreSQL 16 + Redis 7
- **Infra:** Docker Compose + Caddy + GitHub Actions

## Layout do monorepo

```
backend/    # API FastAPI
frontend/   # SPA React (scaffold na Fase 2)
docker/     # docker-compose + Caddyfile
doc/        # PRD e Technical Specification
.github/    # workflows CI
```

## Status

**Fase 1 em andamento** — fundação (setup, auth, CRUD pessoas/relacionamentos). Ver issues com label `phase-1`.
