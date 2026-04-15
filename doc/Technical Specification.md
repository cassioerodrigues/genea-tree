# Documento Técnico — Plataforma de Árvore Genealógica

## 1. Objetivo

Este documento descreve a arquitetura, stack tecnológico, estrutura de dados, APIs, fluxos de integração e requisitos de infraestrutura necessários para implementar a plataforma definida no documento de Requisitos do Produto. Todas as tecnologias sugeridas são **gratuitas e open source**.

---

## 2. Visão Geral da Arquitetura

Arquitetura em camadas, com separação clara entre frontend (SPA) e backend (API REST), persistência relacional + grafo lógico, e um módulo assíncrono de enriquecimento.

```
┌────────────────────────────────────────────────────────┐
│  Navegador (SPA React + Vite)                          │
│  - Visualização de árvore (D3 / react-flow)            │
│  - Formulários, busca, gestão de sugestões             │
└──────────────┬─────────────────────────────────────────┘
               │ HTTPS / JSON (REST + WebSocket)
┌──────────────▼─────────────────────────────────────────┐
│  API Backend (FastAPI + Python 3.12)                   │
│  - Autenticação JWT                                    │
│  - CRUD pessoas/relações/sugestões                     │
│  - Importação/Exportação GEDCOM                        │
│  - Validação de conflitos                              │
└─────┬────────────────────────────┬─────────────────────┘
      │                            │
┌─────▼────────────┐      ┌────────▼────────────────────┐
│ PostgreSQL 16    │      │ Redis 7 (cache + broker)    │
│ - Dados núcleo   │      │ - Celery queue              │
│ - JSONB p/ flex. │      │ - Cache de consultas        │
└──────────────────┘      └────────┬────────────────────┘
                                   │
                          ┌────────▼────────────────────┐
                          │ Celery Workers              │
                          │ - Geração de sugestões      │
                          │ - Detecção de duplicatas    │
                          │ - Parsing GEDCOM            │
                          └─────────────────────────────┘
```

---

## 3. Stack Tecnológica (100% Gratuita)

### 3.1 Backend (Python)

| Componente | Tecnologia | Justificativa |
|---|---|---|
| Linguagem | **Python 3.12** | Requisito do cliente |
| Framework Web | **FastAPI** | Async nativo, tipagem forte, OpenAPI automático |
| ORM | **SQLAlchemy 2.0** + **Alembic** | Maduro, suporte JSONB, migrations |
| Validação | **Pydantic v2** | Integração direta com FastAPI |
| Autenticação | **python-jose** + **passlib[bcrypt]** | JWT + hashing seguro |
| Tarefas assíncronas | **Celery** + **Redis** | Padrão Python para jobs em background |
| Servidor WSGI/ASGI | **Uvicorn** + **Gunicorn** | Produção robusta |
| Testes | **pytest** + **httpx** | Ecossistema padrão |
| Parsing GEDCOM | **python-gedcom** ou **ged4py** | Import/Export do formato padrão genealogia |
| Fuzzy matching | **rapidfuzz** | Detecção de duplicatas por nome |

### 3.2 Frontend

**Escolha: React 18 + TypeScript + Vite**

Justificativa: comunidade massiva, maior oferta de libs para visualização de grafos/árvores, TypeScript garante robustez, Vite traz DX moderna.

| Componente | Tecnologia |
|---|---|
| Framework | **React 18** + **TypeScript** |
| Build/Dev | **Vite** |
| UI kit | **shadcn/ui** + **Tailwind CSS** |
| Roteamento | **React Router v6** |
| Estado servidor | **TanStack Query (React Query)** |
| Estado cliente | **Zustand** |
| Formulários | **React Hook Form** + **Zod** |
| Visualização árvore | **React Flow** (primário) ou **D3.js** (custom) |
| HTTP client | **Axios** |

### 3.3 Persistência

| Uso | Tecnologia |
|---|---|
| Banco principal | **PostgreSQL 16** (relacional + JSONB + CTE recursiva para travessia de árvore) |
| Cache / broker | **Redis 7** |
| Arquivos (exports, uploads GEDCOM) | **MinIO** (S3-compatível, self-hosted) ou sistema de arquivos local |

> **Decisão:** PostgreSQL é suficiente. Não é necessário banco de grafos dedicado (Neo4j) no MVP — CTEs recursivas cobrem travessias. Reavaliar se a base ultrapassar ~1M de indivíduos por usuário.

### 3.4 Infraestrutura e DevOps

| Componente | Tecnologia |
|---|---|
| Containerização | **Docker** + **Docker Compose** |
| Reverse proxy | **Caddy** (HTTPS automático via Let's Encrypt) ou **Nginx** |
| CI/CD | **GitHub Actions** (free tier) |
| Observabilidade | **Prometheus** + **Grafana** + **Loki** (stack gratuita) |
| Erros | **GlitchTip** (alternativa open source ao Sentry) |
| Versionamento | **Git** + **GitHub** |

### 3.5 Hospedagem Gratuita (opções)

- **Fly.io** — tier gratuito com Postgres
- **Render** — tier gratuito
- **Railway** — créditos iniciais
- **Oracle Cloud Free Tier** — VM ARM 24GB RAM gratuita permanente (recomendado para produção séria gratuita)
- **Supabase** — Postgres gerenciado gratuito (alternativa para DB)

---

## 4. Modelo de Dados

### 4.1 Entidades principais (PostgreSQL)

```sql
-- Usuários
users (
  id UUID PK,
  email TEXT UNIQUE,
  password_hash TEXT,
  created_at TIMESTAMPTZ,
  settings JSONB
)

-- Árvores (um usuário pode ter múltiplas)
trees (
  id UUID PK,
  owner_id UUID FK users,
  name TEXT,
  visibility TEXT CHECK (visibility IN ('private','shared','public')),
  created_at TIMESTAMPTZ
)

-- Indivíduos
persons (
  id UUID PK,
  tree_id UUID FK trees,
  full_name TEXT NOT NULL,
  gender TEXT,              -- nullable
  birth_date DATE,          -- nullable (data exata)
  birth_date_approx TEXT,   -- ex: "c. 1890", "Q1 1900"
  birth_place TEXT,
  death_date DATE,
  death_date_approx TEXT,
  death_place TEXT,
  notes TEXT,
  extra JSONB,              -- campos adicionais flexíveis
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
)

-- Relacionamentos (aresta do grafo)
relationships (
  id UUID PK,
  tree_id UUID FK trees,
  person_a_id UUID FK persons,
  person_b_id UUID FK persons,
  rel_type TEXT CHECK (rel_type IN ('parent','spouse')),
  -- 'parent': person_a é pai/mãe de person_b
  -- 'spouse': cônjuges (bidirecional)
  start_date DATE,          -- p/ casamentos
  end_date DATE,
  metadata JSONB,
  UNIQUE(tree_id, person_a_id, person_b_id, rel_type)
)

-- Sugestões
suggestions (
  id UUID PK,
  tree_id UUID FK trees,
  person_id UUID FK persons,
  kind TEXT CHECK (kind IN ('possible_relative','historical_record','possible_duplicate')),
  description TEXT,
  source TEXT,
  confidence REAL,          -- 0.0 a 1.0
  payload JSONB,            -- dados sugeridos
  status TEXT CHECK (status IN ('pending','accepted','rejected','snoozed')),
  snooze_until TIMESTAMPTZ,
  created_at TIMESTAMPTZ
)

-- Versões/conflitos (4.7)
data_versions (
  id UUID PK,
  person_id UUID FK persons,
  field TEXT,               -- ex: 'birth_date'
  value JSONB,
  source TEXT,
  confidence REAL,
  is_primary BOOLEAN,
  created_at TIMESTAMPTZ
)

-- Auditoria (preparação p/ colaboração 4.9)
audit_log (
  id BIGSERIAL PK,
  user_id UUID,
  tree_id UUID,
  entity TEXT,
  entity_id UUID,
  action TEXT,
  diff JSONB,
  created_at TIMESTAMPTZ
)
```

### 4.2 Travessia de árvore (exemplo)

```sql
-- Ancestrais de uma pessoa até 5 gerações
WITH RECURSIVE ancestors AS (
  SELECT p.*, 0 AS depth
    FROM persons p WHERE p.id = :root
  UNION ALL
  SELECT p.*, a.depth + 1
    FROM ancestors a
    JOIN relationships r ON r.person_b_id = a.id AND r.rel_type = 'parent'
    JOIN persons p ON p.id = r.person_a_id
   WHERE a.depth < 5
)
SELECT * FROM ancestors;
```

---

## 5. API REST

Base: `/api/v1`. Autenticação via `Authorization: Bearer <JWT>`.

### 5.1 Autenticação
- `POST /auth/register` — cria conta
- `POST /auth/login` — retorna JWT
- `POST /auth/refresh` — renova token
- `GET  /auth/me`

### 5.2 Árvores
- `GET    /trees` / `POST /trees`
- `GET    /trees/{id}` / `PATCH` / `DELETE`

### 5.3 Pessoas
- `GET    /trees/{tid}/persons` — lista com filtros (`?q=`, `?place=`, `?year_from=`, `?year_to=`)
- `POST   /trees/{tid}/persons`
- `GET    /persons/{id}` / `PATCH` / `DELETE`
- `GET    /persons/{id}/tree?depth=N` — sub-árvore centralizada

### 5.4 Relacionamentos
- `POST   /relationships`
- `DELETE /relationships/{id}`
- `PATCH  /relationships/{id}`

### 5.5 Sugestões
- `GET    /persons/{id}/suggestions`
- `POST   /suggestions/{id}/accept`
- `POST   /suggestions/{id}/reject`
- `POST   /suggestions/{id}/snooze` (body: `{ until: ISO8601 }`)

### 5.6 Import/Export
- `POST   /trees/{tid}/import` (multipart, GEDCOM 5.5.1) → retorna `job_id`
- `GET    /jobs/{job_id}` — status
- `GET    /trees/{tid}/export?format=gedcom|json` → download

### 5.7 Conflitos
- `GET    /persons/{id}/conflicts`
- `POST   /persons/{id}/conflicts/{field}/resolve`

---

## 6. Módulo de Enriquecimento (4.5)

Workers Celery executam tarefas assíncronas:

1. **on_person_created / on_person_updated** → dispara análise
2. **detect_duplicates** — compara nome (rapidfuzz), datas de nascimento próximas, localidade. Gera sugestão `possible_duplicate` com score.
3. **suggest_relatives** — heurísticas sobre sobrenome + localidade + datas compatíveis dentro da mesma árvore.
4. **historical_records** — integração opcional (fase 2) com fontes abertas:
   - **FamilySearch API** (gratuita, requer registro)
   - **WikiTree API** (aberta)
   - **Wikidata SPARQL** (totalmente aberta)

Cada sugestão grava `source`, `confidence` e `payload`. Nunca aplica automaticamente (regra 6 do PRD).

---

## 7. Validação de Conflitos (4.7)

Regras executadas no `PATCH /persons/{id}`:

- `death_date >= birth_date`
- Idade máxima plausível (< 120 anos)
- Pai/mãe deve nascer antes do filho (diferença ≥ 12 anos como aviso)
- Cônjuge com data de casamento após nascimento de ambos

Ao detectar conflito: criar registro em `data_versions` em vez de sobrescrever, marcar `is_primary = false` no novo, retornar `409 Conflict` com detalhes.

---

## 8. Visualização da Árvore (Frontend)

- **React Flow** com layout customizado (algoritmo dagre ou elkjs) para posicionar gerações.
- Nós renderizam card com foto/nome/datas.
- Carregamento incremental: API devolve subárvore com `depth` configurável, frontend pede mais ao expandir.
- Virtualização: apenas nós visíveis no viewport são renderizados.
- Controles: zoom, pan, minimap, centralizar em indivíduo, expandir/colapsar ramo.

---

## 9. Segurança

- JWT com expiração curta (15min) + refresh token rotacionado
- Senha: bcrypt cost ≥ 12
- CORS restrito aos domínios do frontend
- Rate limiting: **slowapi** (FastAPI) — 60 req/min por IP
- HTTPS obrigatório (Caddy automatiza)
- Validação estrita via Pydantic em todo endpoint
- Logs sem PII; auditoria em tabela dedicada
- Backups diários automatizados do Postgres (`pg_dump` + cron)
- Isolamento multi-tenant por `tree_id` em toda query (enforcement em camada de serviço)

---

## 10. Estrutura de Diretórios (sugerida)

```
genea-tree/
├── backend/
│   ├── app/
│   │   ├── api/v1/            # routers FastAPI
│   │   ├── core/              # config, security, deps
│   │   ├── db/                # engine, session, base
│   │   ├── models/            # SQLAlchemy
│   │   ├── schemas/           # Pydantic
│   │   ├── services/          # lógica de negócio
│   │   ├── workers/           # tasks Celery
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── features/ (persons, tree, suggestions, auth)
│   │   ├── hooks/
│   │   ├── pages/
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── docker/
│   ├── docker-compose.yml
│   └── Caddyfile
├── .github/workflows/
└── doc/
```

---

## 11. Docker Compose (núcleo)

Serviços: `api`, `worker`, `postgres`, `redis`, `frontend`, `caddy`. Volumes persistentes para `postgres_data` e `redis_data`. Variáveis sensíveis via `.env`.

---

## 12. Roadmap de Implementação

### Fase 1 — Fundação (2–3 semanas)
- Setup repo, Docker Compose, CI
- Auth (registro/login/JWT)
- CRUD pessoas + relacionamentos
- Migrations Alembic

### Fase 2 — Visualização (2 semanas)
- Endpoint de subárvore
- Frontend React Flow
- Navegação e centralização

### Fase 3 — Busca e Filtros (1 semana)
- Índices Postgres (GIN em `full_name`, trigram)
- UI de busca

### Fase 4 — Import/Export (1–2 semanas)
- Parser GEDCOM
- Jobs Celery
- Export JSON/GEDCOM

### Fase 5 — Sugestões (2 semanas)
- Detecção de duplicatas
- Sugestão de parentes
- UI de aceitar/rejeitar/adiar

### Fase 6 — Conflitos e Versões (1 semana)
- Validações
- UI de resolução

### Fase 7 — Observabilidade e Hardening (1 semana)
- Prometheus/Grafana/Loki
- Rate limiting, backups, testes E2E

### Fase 8 (futuro) — Colaboração
- Convites, permissões granulares, audit log exposto

---

## 13. Estimativas de Capacidade

- Indivíduos por árvore (alvo MVP): até **50.000** com performance fluida
- Consulta de subárvore profundidade 5: < 200ms com índices corretos
- Carga inicial GEDCOM de 10k pessoas: < 30s em worker

---

## 14. Requisitos para Produção Mínima

- VM 2 vCPU / 4 GB RAM / 40 GB SSD (Oracle Free Tier atende)
- Domínio próprio + DNS (Cloudflare free)
- Backup offsite semanal (cron + `rclone` para qualquer storage gratuito)

---

## 15. Considerações Finais

A stack proposta equilibra maturidade, produtividade e custo zero. Nenhum componente exige licença paga nem tier comercial obrigatório. A arquitetura é modular o bastante para substituir peças (ex: Postgres → Supabase, React Flow → D3) sem reescrita estrutural.
