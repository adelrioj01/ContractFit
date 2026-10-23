# ContractFit

ContractFit helps facilities-service contractors find government opportunities they can realistically pursue. It extracts solicitation requirements with source evidence, applies deterministic eligibility checks, and ranks opportunities against a company's capabilities.

## Initial vertical

The first release focuses on small and midsize contractors in:

- Janitorial and custodial services
- HVAC and building maintenance
- Landscaping and groundskeeping
- Pest control
- Electrical and plumbing services
- General facilities maintenance

This narrow starting point gives the matching system a coherent vocabulary and evaluation set. The architecture can later support additional contractor industries.

## Product principles

- **Evidence before answers:** every extracted requirement must point to its source document and location.
- **Rules before guesses:** deadlines, certifications, geography, set-asides, and hard eligibility constraints use deterministic checks.
- **AI where it adds value:** language models handle extraction, normalization, semantic matching, and explanations.
- **Human review for high-impact decisions:** ContractFit supports bid/no-bid decisions; it does not make them autonomously.
- **Evaluation from day one:** extraction accuracy, citation validity, ranking quality, latency, and cost are measured.

## Architecture

- FastAPI service in `backend/`
- PostgreSQL with pgvector for structured data and semantic retrieval
- Redis for caching and future background jobs
- Next.js dashboard planned in `frontend/`
- Docker Compose for a reproducible local environment
- CI for linting, type checks, and tests

See [architecture.md](docs/architecture.md) for the system design and [roadmap.md](docs/roadmap.md) for delivery milestones.

## Run locally

Requirements: Docker Desktop and Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

Then verify the API:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok","service":"contractfit-api"}
```

## Backend development

With Python 3.12 and [uv](https://docs.astral.sh/uv/) installed:

```bash
cd backend
uv sync --dev
uv run pytest
uv run ruff check .
uv run mypy src
```

## Current status

This repository now contains a working vertical-slice MVP:

- A realistic facilities-contractor profile and editable profile API
- Plain-text solicitation ingestion with evidence-preserving requirement extraction
- Deterministic deadline, territory, set-aside, certification, and capacity gates
- Hybrid fit scoring with an optional local Ollama model and an offline fallback
- An explainable ranked-opportunity dashboard at `http://localhost:8000`
- A labeled evaluation set measuring extraction recall, citation validity, and eligibility accuracy

Useful API routes:

- `POST /api/opportunities/import-text`
- `GET /api/opportunities`
- `GET /api/matches`
- `GET /api/evaluation`
- `POST /api/demo/reset`

The default `AI_PROVIDER=offline` makes development deterministic. To exercise local-model
scoring, run Ollama, download the configured model, and set `AI_PROVIDER=ollama` in `.env`.
The matching service falls back safely if the local model is unavailable.

## Persistence

Docker Compose runs the API with `STORAGE_BACKEND=postgres`. On startup, the container applies
Alembic migrations and then launches FastAPI. Direct `uv run` development defaults to the
in-memory adapter unless `STORAGE_BACKEND=postgres` is configured.

Create a future migration after changing SQLAlchemy records:

```bash
cd backend
uv run alembic revision --autogenerate -m "describe the schema change"
uv run alembic upgrade head
```

## License

MIT
