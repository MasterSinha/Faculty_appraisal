# Faculty Appraisal System - Developer Guide

## Architecture Overview

Async FastAPI backend for DYP University's faculty appraisal system. 8 schools, 5-level RBAC, two form tracks (teaching staff + non-teaching staff), deployed on GCP Cloud Run.

### Core Pillars
1. **Async I/O** — every DB query uses `await` via `asyncpg`. No blocking calls anywhere in the request path.
2. **Unified Submit Model** — faculty fill a form in the frontend and submit it as a single JSON payload. The backend "shreds" that payload into normalised relational tables (`shred_form` in `src/api/v1/appraisal.py`) and also keeps a full JSONB snapshot for the reviewer UI.
3. **Hierarchical RBAC** — role weights (0–5) enforced in `src/setup/dependencies.py`. All protected routes use the `CurrentUser` dependency.
4. **Auth** — local JWT by default (`USE_LOCAL_AUTH=true`). Supabase Auth is a legacy fallback (`USE_LOCAL_AUTH=false`).
5. **Storage** — Google Cloud Storage for production file uploads. Local `./uploads` filesystem fallback for on-premise deployments.

---

## 1. Institutional Hierarchy

```
VC (4) → Dean (3) → Director (2) → HOD (1) → Faculty (0)
                                 ↘ Registrar (3.5) → Reporting Officer (1.5) → Non-Teaching Staff (0)
```

Role weights are defined in `src/setup/dependencies.py → User.has_authority_over()`. Horizontal isolation is enforced: Directors only see their own school, HODs only see their own department.

Full role list: `faculty`, `hod`, `director`, `dean`, `vc`, `registrar`, `reporting_officer`, `section_head`, `center_head`, `non_teaching_staff`, `admin`

---

## 2. Form Families

| Family | Schools | Code |
|--------|---------|------|
| standard | SoCSEA, SoBB, SoCE, SoEMR, SoC, CISR | `"standard"` |
| media | SoMCS | `"media"` |
| design | CioD, SoAA | `"design"` |

Resolved in `src/setup/dependencies.py → get_form_family(school)`. School 8 (SoEMR) is unique — it has an HOD layer between faculty and director.

---

## 3. Project Structure

```
src/
├── main.py              — FastAPI app, CORS, middleware, exception handlers
├── api/v1/
│   ├── auth.py          — register, login, verify-email, /me
│   ├── appraisal.py     — snapshot, submit, status (core faculty workflow)
│   ├── dashboard.py     — subordinate list + faculty snapshot viewer (reviewer UI)
│   ├── remarks.py       — HOD/Director/Dean/VC review endpoints
│   ├── documents.py     — uploaded document listing
│   ├── upload.py        — file upload to GCS or local storage
│   ├── non_teaching.py  — non-teaching appraisal workflow
│   ├── admin.py         — REST admin API: stats, config, user management
│   └── feedback.py      — public feedback form submission + admin retrieval
├── crud/
│   ├── core.py          — faculty profile, declaration, review CRUD
│   ├── part_a.py        — Part A section CRUD
│   ├── part_b.py        — Part B section CRUD
│   └── non_teaching.py  — non-teaching appraisal CRUD
├── models/
│   ├── core.py          — FacultyProfile, Declaration, AppraisalSnapshot, AppraisalReview, AppraisalDocument, Feedback
│   ├── part_a.py        — BasePartAModel + 11 concrete models
│   ├── part_b.py        — BasePartBModel + 15 concrete models
│   └── non_teaching.py  — NonTeachingAppraisal, Part A items, Part B ratings
├── schema/
│   ├── core.py          — Pydantic v2 schemas
│   ├── part_a.py / part_b.py / non_teaching.py
└── setup/
    ├── database.py      — async engine, pool (size=5, overflow=10)
    ├── dependencies.py  — JWT validation, User class, has_authority_over(), CurrentUser
    ├── local_auth.py    — bcrypt hashing, JWT sign/verify
    ├── storage_utils.py — GCS + local storage abstraction
    ├── admin_views.py   — SQLAdmin UI mounted at /admin (sqladmin)
    ├── supabase_client.py  — dead code, remove before on-premise packaging
    └── email_utils.py
```

---

## 4. Key Workflows

### Faculty Appraisal Submit Flow
1. **Draft save** — `PUT /appraisal/snapshot` stores the full form JSON in `appraisal_snapshots`. This is what the reviewer UI reads.
2. **Submit** — `POST /appraisal/submit`:
   - `shred_form()` deletes existing rows for that faculty/year in all Part A and Part B tables, then inserts fresh rows from the submitted JSON. Each section key in the payload must match the mapping in `shred_form` exactly (see `src/api/v1/appraisal.py`).
   - `create_or_update_declaration()` stages a `Declaration` row (status = `Submitted`).
   - Snapshot is updated with the full submission payload.
   - Single `await db.commit()` commits everything atomically.

> **Important:** CRUD functions (`create_or_update_declaration`, etc.) do **not** call `db.commit()` internally. Transaction ownership belongs to the endpoint. Do not add `db.commit()` inside CRUD functions that are called mid-endpoint.

### Reviewer Flow (Teaching Staff)
- Reviewer calls `PUT /appraisal-remarks/{role}/{email}` with scores + remarks.
- `update_item_scores()` writes per-section reviewer scores into the same normalized tables (using `hod_score`, `director_score`, etc. columns).
- `Declaration.status` advances: `Submitted` → `pending_director` → `pending_dean` → `pending_vc` → `completed`.

### Non-Teaching Flow
- Staff submits via `PUT /non-teaching/appraisal` (full JSONB payload). The backend also shreds Part A fields (`selfResp`, `selfContrib`, `selfAchieve`) into `non_teaching_part_a_items`.
- Reviewer submits via `PUT /non-teaching/review/{email}`. Reviewer marks in the payload are written to `non_teaching_part_a_items` (ro_marks/registrar_marks/vc_marks) and `non_teaching_part_b_ratings` (ro_rating/registrar_rating/vc_rating).
- Status chain: `Draft` → `Submitted` → `Reporting Officer Reviewed` → `Registrar Reviewed` → `VC Approved`
- **`reports_to_registrar` flag** — if `faculty_profiles.reports_to_registrar = true` for a staff member, their submission status stays `Submitted` (same as normal). The difference is that the RO subordinates query filters them out (`reports_to_registrar == False`), so the RO never sees them and cannot review them. The Registrar sees them directly. Admin sets this flag per staff member via `PUT /api/v1/admin/users/{email}`.

---

## 5. Critical Patterns & Gotchas

### SQLAlchemy import
```python
# CORRECT — works on all SQLAlchemy 2.x builds
from sqlalchemy.orm.attributes import flag_modified

# WRONG — fails on some production SQLAlchemy builds (caused the GCP crash)
from sqlalchemy.orm import flag_modified
```

### Transaction management
CRUD helper functions must **not** own the transaction when called from within an endpoint's try/except block. The endpoint is responsible for the single `await db.commit()` and `await db.rollback()`.

### PgBouncer compatibility
`statement_cache_size: 0` is set in `database.py`. Originally required for Supabase's PgBouncer. Cloud SQL does not use PgBouncer so it is no longer strictly needed, but harmless to keep.

### JSONB mutation tracking
When mutating a JSONB column in-place (e.g., updating `AppraisalSnapshot.payload`), always call `flag_modified(instance, "field_name")` before committing, or SQLAlchemy won't detect the change.

### CORS
Allowed origins are hardcoded in `src/main.py`. Add new frontend URLs to the `origins` list there.

---

## 6. Error Handling

Every error response (4xx and 5xx) returns the same two-field JSON shape:

```json
{
  "user_message": "Plain-English sentence — safe to display directly in the UI.",
  "detail":       "Technical description — visible in the network tab and GCP logs only."
}
```

500 responses also include `"type"` (exception class name) and `"path"` (endpoint URL).

### Exception handlers registered in `src/main.py`

| Handler | When it fires | `user_message` | `detail` |
|---|---|---|---|
| `HTTPException` | `raise HTTPException(...)` in any endpoint | same as `exc.detail` | same as `exc.detail` |
| `RequestValidationError` | Pydantic fails to parse the request body | generic "check highlighted fields" | Pydantic error list |
| `AppError` | `raise AppError(...)` in any endpoint | caller-supplied | caller-supplied |
| `SQLAlchemyError` | uncaught DB driver error | "A database error occurred…" | raw SQL exception string |
| `Exception` | anything else that escapes all handlers | "An unexpected error occurred…" | `str(exc)` |

The HTTP middleware has a matching catch-all as a safety net for exceptions that escape FastAPI's handler stack entirely.

### Raising errors in endpoints — two patterns

**Pattern 1 — `HTTPException`**: use for expected client errors (auth failures, 404s, role checks). The `detail` string is user-facing, so keep it plain English.

```python
raise HTTPException(status_code=403, detail="Admin role required")
raise HTTPException(status_code=404, detail="Faculty not found")
raise HTTPException(status_code=401, detail="Invalid credentials. Please check your email and password.")
```

**Pattern 2 — `AppError`**: use when the message shown in the UI needs to be different from the technical cause logged for debugging. Import from `src.setup.errors`.

```python
from src.setup.errors import AppError

raise AppError(
    "Your appraisal could not be submitted. Please try again.",
    detail=f"shred_form KeyError on section key 'lectures_v2': {e}",
    status_code=500,
)
```

### Rule: never leak raw exceptions into a user-visible field

```python
# WRONG — exposes internal implementation details to the client
raise HTTPException(status_code=500, detail=f"Submission failed: {str(e)}")

# CORRECT — generic user message, technical info tucked into detail via AppError
raise AppError(
    "Your appraisal could not be submitted. Please try again.",
    detail=f"Submission failed: {type(e).__name__}: {e}",
    status_code=500,
)
```

---

## 7. Testing

```bash
# Windows
$env:PYTHONPATH="."
uv run pytest

# Linux/Mac
PYTHONPATH=. uv run pytest
```

| File | What it tests |
|---|---|
| `test_hierarchy_unit.py` | `has_authority_over()` role-weight logic (pure unit, no DB) |
| `test_score_normalizer.py` | `_extract_numeric_score()` normaliser (pure unit, no DB) |
| `test_v1_auth.py` | register, login, `/me`, profile update |
| `test_v1_workflow.py` | snapshot save/retrieve, appraisal submit, status check |
| `test_v1_authority.py` | HOD dashboard visibility, faculty-side status view |
| `test_review_chain.py` | Full HOD → Director → Dean → VC approval chain + cross-role attacks |
| `test_feedback.py` | Public POST /feedback, admin-only GET /feedback |
| `test_admin.py` | Admin user CRUD, stats endpoint, role enforcement |
| `test_non_teaching_workflow.py` | Non-teaching staff → Section Head → Registrar → VC chain |

---

## 8. Running Locally

```bash
uv pip install -r pyproject.toml
uvicorn main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

---

## 9. GCP Deployment

Primary deployment is GCP Cloud Run (`asia-south1`, project `facultyappraisal-495011`, service `faculty-appraisal-git`).

**CI/CD**: Cloud Build triggers automatically on push to `main` via `cloudbuild.yaml`. It pulls the previous image for layer caching, builds with `BUILDKIT_INLINE_CACHE=1`, pushes both `:latest` and `:<commit_sha>` tags, then deploys to Cloud Run. No manual action needed for normal deploys.

> `.github/workflows/deploy.yml` exists in the repo but is **not active** — it was an earlier GitHub Actions attempt. Ignore it.

**Manual deploy** (if Cloud Build is unavailable):
```bash
export PROJECT_ID=facultyappraisal-495011
export IMAGE=asia-south1-docker.pkg.dev/$PROJECT_ID/faculty-appraisal-repo/faculty-appraisal-git

gcloud builds submit --tag $IMAGE:latest .

gcloud run deploy faculty-appraisal-git \
    --image $IMAGE:latest \
    --region asia-south1 \
    --add-cloudsql-instances=$PROJECT_ID:asia-south1:faculty-appraisal-db \
    --allow-unauthenticated
```

---

## 10. Database Migrations

### Two files, two purposes

| File | When to use |
|---|---|
| `Docs/schema.sql` | **Fresh install only** — drops everything and recreates. Use this on a new server. Do NOT run on a live DB with data. |
| `migrations/NNN_*.sql` | **Live DB upgrades** — incremental ALTER/CREATE statements that modify an existing schema without touching data. |

They must stay in sync. Every change applied via a migration file must also be reflected in `Docs/schema.sql`.

### Setting up a brand new database

```bash
# 1. Run the full schema (creates all tables, indexes, triggers, fac_user role)
psql -U postgres -f Docs/schema.sql

# 2. Create the first admin account
psql -U postgres -f migrations/seed_admin_user.sql
```

You do **not** need to run migrations 001–005 after this — `schema.sql` already includes all of them.

### Upgrading an existing database (live DB with data)

Run only the migration files that haven't been applied yet, in order:

```bash
psql -U postgres -f migrations/006_your_new_change.sql
```

Never run `schema.sql` on a live database — it will wipe all faculty data.

### Applied migrations (do not modify or re-run)

| File | What it does |
|---|---|
| `001_unique_constraints.sql` | Composite UNIQUE constraints on declarations, snapshots, reviews, non-teaching |
| `002_fix_appraisal_role_constraint.sql` | Expanded `appraisal_role` CHECK to include `admin`, `staff`, `section_head` |
| `003_create_feedback_table.sql` | Created `feedback` table with category CHECK + indexes |
| `004_add_indexes.sql` | Performance indexes on all Part A/B tables, faculty_profiles, declarations |
| `005_add_is_verified_column.sql` | Added `is_verified boolean` to `faculty_profiles` |
| `006_appraisal_config_and_announcements.sql` | Created `appraisal_config` and `announcements` tables |
| `007_section_scores_and_password_reset.sql` | Added `section_scores jsonb` to `appraisal_reviews`; created `password_reset_tokens` table |
| `008_add_audience_to_announcements.sql` | Added `audience varchar(50)` column to `announcements` |
| `009_add_module_config_table.sql` | Created `module_config` table for Section Controls toggles |
| `010_add_is_active_to_faculty_profiles.sql` | Added `is_active boolean` to `faculty_profiles` |
| `011_widen_announcement_audience.sql` | Widened `announcements.audience` from `varchar(50)` to `varchar(500)` |
| `012_add_reports_to_registrar.sql` | Added `reports_to_registrar boolean` to `faculty_profiles` for direct-to-registrar non-teaching flow |
| `013_add_hr_super_admin_roles.sql` | Expanded `appraisal_role` CHECK to include `hr` and `super_admin` |
| `seed_admin_user.sql` | One-time seed — creates the first admin account (not a schema change) |

> **Rule: never edit a migration file that has already been applied to any database.**
> Past migrations are a permanent record of what changed and when. If you need to undo or extend a past change, write a new numbered file.

### Adding a new migration

1. Create `migrations/006_describe_your_change.sql` using `IF NOT EXISTS` / `IF EXISTS` guards so it is safe to re-run.
2. Apply it to the live DB via Cloud SQL Studio or `psql`.
3. Update `Docs/schema.sql` to reflect the same change (so new installs stay in sync).
4. Update the applied migrations table above.

---

## 11. Admin Backdoor

Two access methods for managing data:

### SQLAdmin UI (`/admin`)
Browser-based table viewer and editor. Mounted at `/admin` by `src/setup/admin_views.py` using `sqladmin`. Login requires a user with `appraisal_role = 'admin'` in `faculty_profiles`.

### REST Admin API (`/api/v1/admin`)
All endpoints require a valid JWT for a user with `appraisal_role = 'admin'`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/admin/stats` | Submission counts by school/year |
| `GET` / `PUT` | `/api/v1/admin/config` | Read/write env vars (on-premise only — does not persist on Cloud Run) |
| `GET` / `POST` | `/api/v1/admin/users` | List all users / create a new user |
| `PUT` / `DELETE` | `/api/v1/admin/users/{email}` | Update or delete a user |

> Creating the first admin: manually `INSERT` a row into `faculty_profiles` with `appraisal_role = 'admin'` and a bcrypt-hashed password. Generate the hash with: `python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"`

---

## 12. Development Tools

| Tool | Purpose |
|------|---------|
| `uv` | Package manager (fast, lockfile-based) |
| `gunicorn` + `uvicorn.workers.UvicornWorker` | Production ASGI server |
| `asyncpg` | Async PostgreSQL driver |
| `orjson` | Fast JSON serialisation |
| `pydantic v2` | Request/response validation |
