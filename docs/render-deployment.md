# Minimal Render demonstration

This is a prepared deployment, not a published service. Creating the Blueprint provisions
paid resources: obtain explicit approval before applying it or transmitting any secrets.
Use only synthetic data; the seeded demo accounts have public credentials. Registration is
also public. Do not upload customer material or treat this instance as a production service.

## Resources and budget

[render.yaml](../render.yaml) runs the packaged FastAPI dashboard and API in one Docker web
service, with Render Postgres 17 and a 1 GB persistent upload disk in Ohio. There is no Redis,
worker, SAM synchronization, SMTP delivery, Ollama, or external AI provider. Processing runs
inline; embeddings and OCR are disabled to keep memory usage bounded. Text PDFs, DOCX and TXT
remain supported; scanned documents need OCR in a larger configuration.

Planning estimate checked 2026-11-17: approximately $13-15/month on a Hobby workspace
(web compute about $7, database compute about $6, plus 1 GB database storage and 1 GB disk).
This is an estimate, not a spending cap; taxes, bandwidth, build usage and future price changes
can increase the bill. Confirm every line item in Render's creation preview before approval.
Database storage is explicitly 1 GB because the default for this compute plan is 15 GB;
storage autoscaling and automatic service deploys are disabled.

Official references: [pricing](https://render.com/pricing),
[compute plans](https://render.com/docs/compute-plans),
[Blueprint specification](https://render.com/docs/blueprint-spec),
[extensions](https://render.com/docs/postgresql-extensions),
[persistent disks](https://render.com/docs/disks).

## Startup and persistence

The Docker command runs `alembic upgrade head` before starting one Uvicorn worker on `$PORT`
(default 8000). Failure prevents startup. Migration 0006 enables `vector`; the current head
is `20261106_0018`. Render's internal connection string is normalized to the installed Psycopg 3
driver; URL-encoded password characters are escaped for Alembic's ConfigParser.
The Blueprint generates a private signing key within Render: no local `.env` is uploaded.
The Docker build context is `backend/`; `.dockerignore` excludes environment files and uploads.

Domain records live in Postgres; original uploads live under `/app/data/uploads` on the disk.
Both must be backed up together for recovery. A disk binds the service to one instance and
redeploys have downtime. Inline jobs are not a durable queue: interruption can leave unfinished
processing that needs manual review/retry. The 5 MB upload limit and small compute plans are
for a low-traffic demonstration, not a throughput guarantee.

Demo seeding occurs at application startup. On an empty database it creates the synthetic
catalog and public demo accounts. If the primary sample profile is absent, the existing seed
routine resets application tables: use a dedicated demo database and never point this
Blueprint at an existing customer database. Do not delete that profile as a reset mechanism.
`/health` confirms process availability only; it does not probe the database or disk.

## Deployment runbook (after explicit approval)

1. Run `./scripts/verify.ps1` from the repository root. Review the full diff, then commit and
   publish the prepared changes to `codex/sam-sync-v1` using the normal review workflow.
2. In Render, select New Blueprint for this repository and that branch, using `render.yaml`.
   Review the exact web plan, Postgres plan, both storage allocations, region and estimated bill.
   Creating a Blueprint deploys initially even though automatic redeploys are off.
3. Apply only after approval. Keep the generated signing key and database credentials inside
   Render; do not copy local `.env`, SAM keys or customer data. No extra API keys are needed.
4. Inspect startup logs for Alembic head and successful Uvicorn startup. In the service shell,
   run `alembic current` and `alembic check`; verify extension `vector` and version 0018 through
   the internal database connection. Do not print connection strings or tokens in reports.
5. Open `/health` and `/`. Sign in with `demo@contractfit.local` /
   `contractfit-demo-password`. Confirm the synthetic catalog loads, upload a synthetic TXT
   solicitation, and verify evidence and matching. Register a second synthetic organization
   and confirm it cannot access the first organization's document.
6. Redeploy manually and confirm the uploaded original and its records still exist, login
   works, and seeding has not duplicated the catalog. Watch memory, disk and request latency.

## Recovery and teardown

Before an upgrade, take a database backup and a matching copy of uploads. Rolling back an
image does not reverse a database migration. Prefer a compatible forward fix; restore both
backups to recover a previous state. Do not run Alembic downgrade against a live demo casually.
To stop charges, delete the web service, its disk and Postgres explicitly in Render after
exporting anything needed. Removing YAML entries or suspending the web service is not proof
that all billable resources were deleted.

## Verification boundaries

Run `cd backend` then `uv run --with PyYAML==6.0.3 python ../scripts/check_render.py`
for offline Blueprint checks (also run in CI). This checks project constraints, not the full
Render schema. Local checks cover URL normalization, the Blueprint's demo/persistence constraints and existing
application regressions. CI is configured to validate migrations against real pgvector/Postgres 17. Neither
local checks nor CI prove Render provisioning, its quoted price, available capacity, restart
persistence or hosted performance; those checks remain pending until an approved deployment.

Preparation verification (2026-11-17):

- `./scripts/verify.ps1 -SkipTests` passed with the existing environment
  (`UV_NO_SYNC=true`, writable `UV_CACHE_DIR`): Ruff, Mypy (39 source files), quality gate,
  local links and secret-pattern scan. `python scripts/check_render.py` also passed.
- The complete `render.yaml` passed `jsonschema.Draft202012Validator` against the public
  [official JSON schema](https://render.com/schema/render.yaml.json), retrieved on this date.
  All 1,380 source lines were retrieved, parsed as JSON, and the schema itself was checked
  before validating the Blueprint. No credentials or configuration were sent to Render.
  This is schema validation, not an authenticated Render provisioning preview.
- A bounded diagnostic run of `pytest tests/test_amendment_workflow.py -vv
  -o faulthandler_timeout=15` showed the blocked thread in Python's Windows
  `socket.socketpair()` / `accept()` while AnyIO created the event loop, before the API handler.
  A separate Python process calling only `socket.socketpair()` also timed out after five
  seconds. This reproduces an environment limitation independently of ContractFit; it does
  not establish that the excluded application tests pass.
- A diagnostic subset selected all test modules without `TestClient`, async test functions,
  or `pytest.mark.asyncio`: **208 passed, 4 skipped**. Eleven HTTP/async modules (52 tests)
  were excluded; this was an explicit diagnostic selection, not a change to tests or CI.
  The four skips include checks requiring a live PostgreSQL environment.
- Docker access to `dockerDesktopLinuxEngine` was denied. No image build, container startup,
  new live PostgreSQL migration run, or disk persistence smoke test was possible here.

Before approving resource creation, complete the full suite and build/start the image against
an isolated empty pgvector/Postgres 17 database in an environment with Docker and working local
sockets. Verify migration head 0018, `$PORT`, `/health`, dashboard, login, a synthetic upload,
organization isolation and upload persistence across a container recreation. Do not use local
`.env` or existing customer volumes for these checks. No resources were provisioned, no secrets
were transmitted, and changes remain local until reviewed/published.

## Reproducible container verification

Run `python scripts/smoke_render.py` from the repository root on a machine with Docker Compose
and working local sockets. The script builds `backend/Dockerfile`, starts a uniquely named
synthetic Postgres/pgvector database and API with the Render settings and memory limits,
checks head 0018 and schema drift, verifies `$PORT=10000`, dashboard/login, inline TXT upload
and tenant isolation, then recreates only the API and checks records, original bytes and
catalog counts. It removes only its own Compose project, volumes and locally built image.
No host port, customer database, local `.env`, Render API or actual private key is used.
Failure logs are printed before cleanup. Linux CI is the intended execution environment.

CI now includes this container job plus the complete backend suite and validation against
the official schema. Pushes to `codex/sam-sync-v1` trigger these checks; no Render deployment
is triggered (`autoDeployTrigger: "off"`). A passing CI run must be observed before calling
these pending checks successful. The job definition and successful static checks alone are
not evidence of a working image or persistence.
