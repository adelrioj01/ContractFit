# Repository ownership

Use these boundaries to assign bounded workers. A worker edits only its assigned paths; changes to
the coordinated contract surface return to the orchestrator before implementation continues.

## Path owners

| Owner | May edit | Responsibility |
| --- | --- | --- |
| Frontend | `frontend/**`, `backend/src/contractfit/static/**`, `backend/tests/test_dashboard_static.py` | Browser presentation, accessibility, and client-side use of an unchanged HTTP contract. The FastAPI-served dashboard remains frontend-owned even though packaging places it under `backend/`. |
| Backend | `backend/src/contractfit/**` except `static/**`, `backend/migrations/**`, focused tests under `backend/tests/**` | Domain rules, API orchestration, storage adapters, workers, provider adapters, and persistence. Backend workers own only the focused tests named in their brief. |
| Integration/QA | `.github/workflows/**`, `compose.yaml`, `scripts/**`, `docs/evaluations/**`, cross-boundary tests under `backend/tests/**`, and repository verification documentation | Contract verification, end-to-end and tenant-isolation coverage, migrations checks, quality gates, and release evidence. This owner starts read-only unless the brief explicitly permits edits. |
| Orchestrator | `AGENTS.md`, shared documentation under `docs/**`, and the coordinated contract surface below | Architecture decisions, assignment, shared-contract approval, sequential integration, complete verification, and handoff. |

Documentation outside this file may be assigned to the owner of the behavior it describes. Fixtures
and samples follow the owner of the test or workflow that consumes them.

## Coordinated contract surface

No frontend or backend worker changes these interfaces independently:

- HTTP paths and request/response models in `backend/src/contractfit/api.py`.
- Shared domain and identity models in `backend/src/contractfit/domain.py`,
  `backend/src/contractfit/auth.py`, and feature model modules imported by the API or store.
- `ContractFitStore` in `backend/src/contractfit/store.py` and every adapter that implements it,
  including `backend/src/contractfit/sql_store.py`.
- SQLAlchemy records in `backend/src/contractfit/persistence_models.py` and Alembic migrations.
- Runtime wiring in `backend/src/contractfit/main.py`, `backend/src/contractfit/runtime.py`, and
  deployment or CI configuration.

A proposed contract change needs an architecture decision or an explicit orchestrator-approved
brief that names all affected callers, adapters, migrations, tests, and frontend consumers. Freeze
that contract before parallel implementation; integrate contract changes before dependent work.

## Worker verification

Each worker runs the narrow tests, Ruff checks, and Mypy checks that cover its assigned files and
reports exact commands and results. The orchestrator then reviews the combined diff and runs from
the repository root:

```powershell
./scripts/verify.ps1
```

When persistence changes, also run the applicable Alembic and PostgreSQL checks documented in
`.github/workflows/ci.yml`. A known failing check is not accepted as new baseline evidence: record
the exact test names and failure signatures and show that they match the pre-change run.

## Integration stop condition

Stop integration and return ownership to the orchestrator if a change crosses an assigned path,
alters the coordinated contract surface, needs a migration not named in the brief, overlaps another
worker's uncommitted edits, weakens organization isolation, or creates a new verification failure.
Do not resolve a cross-owner conflict by expanding the worker's scope.

Organization-owned relevance feedback is integrated across the API, store protocol, memory and SQL
adapters, migration, dashboard and focused tests described by
[ADR 0018](decisions/0018-organization-owned-relevance-feedback.md). Future feedback changes remain
a coordinated backend, frontend and integration surface rather than an independently owned file.
