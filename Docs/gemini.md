# Gemini Model Context Transfer

## Mandatory Instructions
- **Architecture:** Always use **asynchronous** patterns (`async def`, `await`).
- **Database:** Use `sqlalchemy.ext.asyncio` with the `asyncpg` driver. Use `AsyncSession` for all DB interactions.
- **Serialization:** `orjson` is used for high-traffic response serialization via `ORJSONResponse` / Pydantic v2.
- **statement_cache_size:** `statement_cache_size: 0` is set in `create_async_engine`. Originally required for Supabase/PgBouncer; database is now GCP Cloud SQL (no PgBouncer), so this is no longer strictly needed but is kept as it is harmless.
- **Tools:** Always use `uv` for package management (`uv sync`, `uv run`).
- **Hierarchy:** Enforce the Reporting Tree: `Faculty(0) < HOD(1) < Director(2) < Dean(3) < Registrar(3.5) < VC(4) < Admin(5)`. Implemented in `src/setup/dependencies.py` via `has_authority_over()`.
- **Visibility:** Higher authorities can see/manage data of subordinates; same-level users are isolated.
- **Schema Alignment:** Models are aligned with `project_complete_schema.sql` (the authoritative schema file). Always verify column names against that file or existing models before making schema changes. Migrations are plain SQL files in `migrations/` — there is no Alembic.
- **Context & Artifacts:** Important architectural plans, planning documents, or research notes are stored in the project's `Docs/` directory (e.g., [academic_year_transition_plan.md](file:///C:/Users/ruhan/fahh/Faculty_appraisal/Docs/academic_year_transition_plan.md)) as well as the Antigravity conversation-specific brain/artifacts directory (`C:/Users/ruhan/.gemini/antigravity-cli/brain/<conversation-id>/`). Whenever the user asks about context, previous designs, or plans, always search both locations.



## Current Infrastructure

| Component | Details |
|---|---|
| Frontend | React/Vite on Netlify — `https://dypfacultyappraisal.netlify.app` |
| Backend | GCP Cloud Run, region `asia-south1`, project `facultyappraisal-495011`, service `faculty-appraisal-git` |
| Database | GCP Cloud SQL PostgreSQL (`faculty-appraisal-db`). **Not Supabase.** |
| Auth | Local JWT + bcrypt. `USE_LOCAL_AUTH=true` always in production. |
| Storage | Google Cloud Storage (`GCP_STORAGE_BUCKET`), local `./uploads` fallback |
| CI/CD | GCP Cloud Build — auto-triggers on push to `main`, builds Docker image, deploys to Cloud Run |

> `.github/workflows/deploy.yml` exists in the repo but is **dead code** — it is not the active pipeline. GCP Cloud Build is.

> `supabase_client.py` is dead code — the project was originally on Supabase but migrated to Cloud SQL due to auth rate limits (2 users/hour on free tier). It is kept as an emergency backup but scheduled for removal.

## Schools and Form Families

| Form Family | Schools |
|---|---|
| `standard` | SoCSEA, SoBB, SoCE, SoEMR, SoC, CISR |
| `media` | SoMCS |
| `design` | CioD, SoAA |

**SoEMR special case:** Uses the standard form, but the HOD score is shown alongside Director/Dean/VC scores in the review dashboard. All other standard schools do not expose a HOD score column.

## Work Done So Far

### 1. Initial Setup & Hierarchy
- Configured FastAPI with SQLAlchemy 2.0 async.
- Implemented Hierarchical Access Control in `src/setup/dependencies.py`.
- Standardized all IDs to UUID.

### 2. High-Performance Async Refactor
- Replaced `psycopg2` with `asyncpg`. Migrated entire codebase to non-blocking I/O.
- Integrated `orjson` for fast JSON serialization.
- Updated Dockerfile to use Gunicorn with `uvicorn.workers.UvicornWorker`.
- Added `X-Process-Time` latency middleware in `main.py`.

### 3. Database & Schema Work
- Migrated from Supabase to GCP Cloud SQL. Auth is now fully local (bcrypt + JWT).
- Authoritative schema is `project_complete_schema.sql`. Migrations are numbered SQL files in `migrations/`.
- `v5_sync_to_final_schema.sql` syncs the running DB to the current code state — run this if deploying to a fresh DB or if column errors appear.
- Key gotcha: `faculty_profiles.is_verified` (Boolean) is in the model and auth code but was missing from the original schema file. It is added by `v5_sync_to_final_schema.sql`.

### 4. Appraisal Modules
- Models, schemas, and CRUD for Part A (Teaching) and Part B (Research).
- Non-teaching staff appraisal flow: Staff → Reporting Officer → Registrar → VC.
- Teaching faculty flow: Faculty → HOD (SoEMR only) → Director → Dean → VC.
- `shred_form` in `src/api/v1/appraisal.py`: normalizes JSON form submission into individual DB tables.
- Dual storage: JSONB `appraisal_snapshots` (dashboard reads) + normalized Part A/B tables (reporting).

## Key Patterns

### Auth guard
```python
from src.setup.dependencies import CurrentUser
async def my_route(current_user: CurrentUser): ...
```
`current_user.email`, `current_user.school`, `current_user.department`, `current_user.roles` are all available from the JWT.

### DB session
```python
from src.setup.database import get_db
async def my_route(db: AsyncSession = Depends(get_db)): ...
```

### JSONB mutation
```python
from sqlalchemy.orm.attributes import flag_modified  # not from sqlalchemy.orm
flag_modified(instance, "payload")
```

### non_teaching_appraisals status values
Allowed by DB CHECK constraint: `'Draft'`, `'Submitted'`, `'Reporting Officer Reviewed'`, `'Registrar Reviewed'`, `'VC Approved'`. Do not use informal strings like `pending_registrar`.

## Plan for Future Work

### 1. On-Premise Deployment
- GCP is temporary (client testing only). Long-term target is client's local server.
- Before packaging: remove `supabase_client.py`, all Supabase env vars, and GCS storage references. Switch `USE_LOCAL_STORAGE=true`.
- Run `project_complete_schema.sql` then all numbered migrations in order.
- **Local VM Deployment Details:** Active work is ongoing on the college local VM (Linux, dockerized, local DB). See the comprehensive context, networking setup, and persistent volume solutions in [LOCAL_VM_DEPLOYMENT_CONTEXT.md](file:///C:/Users/ruhan/fahh/Faculty_appraisal/Docs/LOCAL_VM_DEPLOYMENT_CONTEXT.md).


### 2. Performance Profiling
- Use `X-Process-Time` response header to measure endpoint latency.
- Target: <200ms under normal load.

### 3. Test Coverage
- Expand `pytest-asyncio` coverage for multi-role approval scenarios.
- Unit tests (no DB) go in `tests/test_*_unit.py`. Integration tests require Cloud SQL — skip gracefully on Windows dev machines (no Unix socket support in asyncpg).
