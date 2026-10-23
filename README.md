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

This repository contains the project foundation: domain models, health endpoint, local infrastructure, CI, architectural boundaries, and an implementation roadmap. Opportunity ingestion and matching are the next milestone.

## License

MIT
