# Faculty Appraisal System — CLAUDE.md

## Project Overview
Async FastAPI backend for a multi-school faculty appraisal system at DYP University. Supports 8 schools, 5-level role hierarchy, two appraisal form types (teaching + non-teaching), and dual cloud/on-premise deployment.

- **Frontend**: React/Vite on Firebase Hosting (`https://facultyappraisal-495011.web.app`)
- **Backend**: FastAPI on GCP Cloud Run (`asia-south1`, project `facultyappraisal-495011`, service `faculty-appraisal-git`)
- **Database**: GCP Cloud SQL PostgreSQL (`faculty-appraisal-db`). Originally Supabase but migrated due to auth limits.
- **Storage**: Google Cloud Storage (`GCP_STORAGE_BUCKET`) with local `./uploads` fallback
- **Auth**: Local JWT + bcrypt. Supabase auth code has been fully removed.

---

## Boundaries — what not to touch

`admin_ui/` is owned by the frontend teammate. **Do not read, edit, or suggest
changes to any file inside `admin_ui/`.** If a task seems to require a change
there (e.g. the React app needs a new API endpoint, a CORS origin, or a new
field in an API response), stop and tell the user what the frontend team needs
so they can coordinate with the teammate directly.

The only file in the repo root that belongs to both sides is `Dockerfile` —
edit it only for backend reasons (Python deps, build steps) and flag any
Node/Vite build changes to the frontend teammate before committing.

---

## Source Layout

```
src/
├── main.py              # FastAPI app, CORS, middleware, exception handlers
├── api/v1/              # Route handlers (auth, appraisal, dashboard, documents, remarks, non_teaching, upload)
├── crud/                # DB operations (core, part_a, part_b, non_teaching)
├── models/              # SQLAlchemy ORM models (core, part_a, part_b, non_teaching)
├── schema/              # Pydantic v2 schemas (core, part_a, part_b, non_teaching)
└── setup/
    ├── database.py      # Async engine, connection pool (size=5, overflow=10)
    ├── dependencies.py  # JWT auth, role hierarchy, CurrentUser dependency
    ├── local_auth.py    # Local bcrypt auth
    ├── storage_utils.py # GCS + local storage abstraction
    ├── supabase_client.py  # dead code — scheduled for removal
    └── email_utils.py
main.py                  # Gunicorn entrypoint (proxies src/main.py)
```

---

## Role Hierarchy
`Faculty(0) < HOD(1) < Director(2) < Dean(3) < Registrar(3.5) < VC(4) < Admin(5)`

Implemented in `src/setup/dependencies.py` via `has_authority_over()`. Use `CurrentUser` dependency on all protected routes.

## Form Types
- **Standard**: SoCSEA, SoBB, SoCE, SoEMR, SoCM, CISR
- **Media**: SoMCS
- **Design**: SoD, SoAA
- **SoEMR special case**: Uses the standard form, but the HOD score is visible alongside Director/Dean/VC scores in the review dashboard. All other standard schools do not show a HOD score column.
- Mapped in `get_form_family()` in `src/setup/dependencies.py`

---

## Environment Variables (see `.env.example`)
| Variable | Notes |
|---|---|
| `DATABASE_URL` | Must use `postgresql+asyncpg://` scheme. GCP Cloud SQL uses Unix socket path in Cloud Run. |
| `USE_LOCAL_AUTH` | Always `true` in production. `false` routes through Supabase Auth (unused). |
| `JWT_SECRET_KEY` | Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `APP_URL` | Backend public URL, no trailing slash |
| `FRONTEND_URL` | Frontend public URL, no trailing slash |
| `USE_LOCAL_STORAGE` | `true` = local `./uploads`, `false` = GCS |
| `GCP_STORAGE_BUCKET` | GCS bucket name |
| `ALLOW_MOCK_USER` | Dev only — bypasses login |

---

## Running Locally
```bash
# Install deps
uv pip install -r pyproject.toml

# Run dev server
uvicorn main:app --reload --port 8000
```
API docs at `http://localhost:8000/docs`

## Running with Docker
```bash
docker compose up --build
```

---

## GCP Deployment

**CI/CD**: GCP Cloud Build triggers automatically on push to `main`, builds the Docker image, and deploys to Cloud Run. This is the live pipeline.

> `.github/workflows/deploy.yml` exists in the repo but is **not active** — it was an earlier attempt at GitHub Actions CI/CD that never worked. Ignore it.

**Manual deploy** (if needed):
```bash
export PROJECT_ID=facultyappraisal-495011

# Build and push image
gcloud builds submit --tag asia-south1-docker.pkg.dev/$PROJECT_ID/faculty-appraisal-repo/faculty-appraisal-git:latest .

# Deploy to Cloud Run
gcloud run deploy faculty-appraisal-git \
    --image asia-south1-docker.pkg.dev/$PROJECT_ID/faculty-appraisal-repo/faculty-appraisal-git:latest \
    --region asia-south1 \
    --add-cloudsql-instances=$PROJECT_ID:asia-south1:faculty-appraisal-db \
    --allow-unauthenticated
```

---

## Key Patterns

### Adding a new appraisal endpoint
Each appraisal category follows a standard 6-endpoint REST pattern:
- `POST /` — create
- `GET /` — list all
- `GET /faculty/{faculty_id}` — list by faculty
- `PUT /{id}` — update
- `DELETE /{id}` — delete
- `GET /summary/{faculty_id}` — score aggregation

### Database sessions
Always use the `get_db` dependency:
```python
from src.setup.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

async def my_route(db: AsyncSession = Depends(get_db)):
    ...
```

### Modifying JSONB fields
Import `flag_modified` from the direct path (not the top-level namespace — it breaks on some SQLAlchemy builds):
```python
from sqlalchemy.orm.attributes import flag_modified  # correct
# NOT: from sqlalchemy.orm import flag_modified
```

### Auth guard
```python
from src.setup.dependencies import CurrentUser
async def my_route(current_user: CurrentUser):
    ...
```

---

## CORS Allowed Origins
Configured in `src/main.py`. Currently hardcoded — add new frontend URLs to the `origins` list there.

Current allowed: `localhost:5173/3000/8000/5174`, `https://facultyappraisal-495011.web.app`, old Cloud Run frontend URL (can be removed once traffic is fully on Firebase).

---

## Commit Messages

After completing any task, suggest a commit message following the Conventional Commits standard.

**Format:** `type(scope): short description` — imperative mood, lowercase, no period, ≤72 chars.

Common types: `feat` · `fix` · `docs` · `refactor` · `test` · `chore` · `perf`

**Short (one-liner) — just show the message:**
```
feat(auth): add two-tier user_message/detail error format
```

**Long (multi-line body) — give the full command so it can be pasted directly:**
```bash
git commit -m "$(cat <<'EOF'
feat(errors): add two-tier error response format

- Add AppError class with user_message/detail split
- Override HTTPException, RequestValidationError, SQLAlchemyError handlers
- Fix raw exception leaks in appraisal.py and upload.py
EOF
)"
```

Use the long form when the change touches multiple files or needs context that won't fit in 72 chars.

---

## Known Issues / Gotchas
- `--timeout 0` in Gunicorn CMD disables worker timeout — intentional for long async operations but watch for hung requests
- `statement_cache_size: 0` in database engine was originally required for Supabase/PgBouncer. Cloud SQL does not use PgBouncer so this is no longer strictly needed, but it is harmless to keep.
- Docker image runs as root (no non-root user configured) — acceptable for Cloud Run but **must be fixed before local server deployment** (add a non-root user in Dockerfile)
- `pool_size=5, max_overflow=10` — up to 15 DB connections per container instance. Cloud SQL default max connections is ~100; keep this in mind when scaling Cloud Run instances. For local server, tune this based on available RAM.
- `supabase_client.py` is dead code — safe to delete. All Supabase auth code has been removed from `dependencies.py` and `pyproject.toml`.
- Local server deployment: replace Cloud SQL Unix socket `DATABASE_URL` with a standard TCP connection string (`postgresql+asyncpg://user:pass@host:5432/db`). Remove all GCP-specific env vars (`GCP_STORAGE_BUCKET`, Cloud SQL instance strings). Set `USE_LOCAL_STORAGE=true`.
- Schema migrations are managed automatically by Alembic. The container automatically runs `alembic upgrade head` on startup.

---

## Future Work / TODOs
- [ ] **Isolated Experimental Sandbox Account**: The experimental account (`experimental@gmail.com`) currently bypasses database lookup for login and profiles to avoid crashes, but doesn't support interactive data modifications. We need to expand this feature to support mock database operations or isolated database schemas.
