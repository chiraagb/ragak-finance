# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

RAGAK is an AI-powered mutual fund intelligence platform for Indian investors. It ingests fund factsheets (PDFs), stores them as vector embeddings in PostgreSQL (pgvector), and answers natural language questions via a LangGraph-orchestrated pipeline using Gemini 2.5 Flash.

---

## Running the Stack

Everything runs via Docker Compose. Always use the project root:

```bash
docker compose up -d --build          # full rebuild + start
docker compose up -d --build backend  # rebuild only backend
docker compose up -d --build worker   # rebuild only worker
docker compose logs backend -f        # stream backend logs
docker compose logs worker -f         # stream worker/Celery logs
docker compose ps                     # check service health
```

Services: `postgres` (5432), `redis` (6379), `backend` (8000), `worker` (Celery), `beat` (Celery Beat), `frontend` (3000).

Backend startup sequence (in docker-compose command): `alembic upgrade head` → `python -m db.seed` → `uvicorn`.

### Local backend development (outside Docker)

```bash
cd backend
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

### Frontend development

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev   # starts on http://localhost:5173
npm run build
```

---

## Architecture

### Request Flow

```
User message (POST /api/chat/sessions/{id}/messages)
  → SSE StreamingResponse
    → LangGraph graph (build_graph in agents/graph.py)
      → intent_detector → fund_resolver → [rag_node | comparison_node | ranking_node | risk_node]
        → context_assembler → response_synthesizer (Gemini via LangChain)
          → token-by-token SSE stream to frontend
```

### LangGraph Graph (`backend/agents/`)

- **`agents/state.py`** — `AgentState` TypedDict is the contract between all nodes. `messages` uses `add_messages` reducer (appends). `rag_chunks` uses `add` reducer (accumulates from parallel nodes). All other fields overwrite.
- **`agents/graph.py`** — builds the graph. `db` (AsyncSession) and `checkpointer` (PostgresSaver) are injected at request time. Nodes that need DB are wrapped via `_wrap_with_db()`.
- **Routing**: `intent_detector` → if `ranking` go to `ranking_node`, if `general` go to `rag_node`, else go to `fund_resolver`. After resolver, `comparison` and `risk_analysis` fan out in parallel via `Send()`.
- **LLM**: Both `intent_detector` and `response_synthesizer` use `ChatGoogleGenerativeAI` from `langchain-google-genai`. To swap models, change `_get_llm()` in each node file.

### PDF Ingestion Pipeline (`backend/processing/`)

Triggered by Celery task `process_document`:

1. `pdf_extractor.py` — PyMuPDF extracts text + tables per page, detects fund name and factsheet month
2. `chunker.py` — financial-aware chunking; detects per-page fund name headings for combined AMC factsheets (e.g. HDFC's 140-page combined PDF), tags each chunk with the correct scheme name
3. `embedder.py` — OpenAI `text-embedding-3-small`, batched at 100 texts
4. `metric_extractor.py` — regex extracts AUM, expense ratio, AAA%, WAM, etc. `extract_metrics_per_scheme()` handles combined factsheets by splitting pages per detected scheme heading
5. Chunks stored in `document_chunks` (pgvector), metrics in `fund_metrics`

### Retrieval (`backend/services/retrieval_service.py`)

Hybrid search: pgvector cosine similarity + PostgreSQL full-text (`to_tsvector`), fused via Reciprocal Rank Fusion (k=60). All SQL parameters that could cause asyncpg type inference errors (fund_ids, embedding vector, section filter) are embedded as SQL literals — never passed as `None` bind parameters.

### Scoring Engine (`backend/services/scoring_engine.py`)

Fully deterministic — no LLM involved. Min-max normalization across all funds, weighted sum per `RankingProfile`. Score breakdown stored as JSONB in `fund_ranking_scores` for explainability. Weights must sum to 1.0 ± 0.001.

### Database

PostgreSQL + pgvector. Async ORM via SQLAlchemy + asyncpg. Alembic for migrations (`backend/db/migrations/versions/`). Current migrations: `0001_initial_schema`, `0002_amc_sources`, `0003_document_content_hash`.

Key tables: `funds`, `document_chunks` (pgvector `embedding vector(1536)`), `fund_metrics`, `ranking_profiles`, `ranking_profile_weights`, `fund_ranking_scores`, `chat_sessions`, `chat_messages`, `amc_sources`.

Seed data (`db/seed.py`): creates pgvector/pg_trgm extensions, seeds 11 metric definitions, 2 system ranking profiles, then imports liquid/money market/overnight funds from MFAPI.in.

### AMC Source Scraping

Users add factsheet PDF URLs in the UI (Documents → AMC Sources tab). Celery task `fetch_amc_source` downloads the PDF and queues `process_document`. Celery Beat runs `fetch_all_amc_sources` on the 1st of each month at 2am IST.

---

## Key Constraints

- **asyncpg + SQLAlchemy `text()`**: Never use `:param::type` syntax or pass `None` as a named parameter — asyncpg cannot infer the type. Build conditional SQL clauses as f-string literals instead (see `retrieval_service.py` for the pattern).
- **LangGraph `astream(stream_mode="updates")`**: yields `dict` chunks `{"node_name": output}`, not tuples. Iterate as `async for chunk in graph.astream(...): for node_name, node_output in chunk.items()`.
- **Combined factsheets**: The chunker and metric extractor both detect per-scheme headings (ALL CAPS lines containing "FUND"/"SCHEME") to tag chunks and extract metrics per scheme within a single PDF.
- **Document deduplication**: Upload endpoint computes SHA-256 of file content and rejects duplicates, returning the existing document record.
- **Embeddings**: OpenAI `text-embedding-3-small` (1536 dims). pgvector IVFFlat index — migrate to HNSW when `document_chunks` exceeds ~50k rows.

---

## Environment Variables

Required in `.env` (see `.env.example`):

| Variable | Purpose |
|---|---|
| `POSTGRES_PASSWORD` | Used by docker-compose to build DB connection strings |
| `REDIS_PASSWORD` | Used by docker-compose for Redis auth |
| `GEMINI_API_KEY` | Gemini 2.5 Flash — intent detection + response synthesis |
| `OPENAI_API_KEY` | Embeddings only (`text-embedding-3-small`) |
| `JWT_SECRET_KEY` | JWT signing |

`DATABASE_URL` and `REDIS_URL` in `.env` are for local development outside Docker. Docker Compose builds its own connection strings from `POSTGRES_PASSWORD`/`REDIS_PASSWORD`.
