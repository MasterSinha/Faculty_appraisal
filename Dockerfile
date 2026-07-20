# =============================================================================
# Stage 1 — Build the React admin UI
# =============================================================================
FROM node:20-alpine AS admin-build
WORKDIR /admin_ui

# Install deps first (cached unless package.json changes)
COPY admin_ui/package*.json ./
RUN npm ci --ignore-scripts

# Build
COPY admin_ui/ .
RUN npm run build

# =============================================================================
# Stage 2 — Python / FastAPI backend
# =============================================================================
FROM python:3.12-slim-bookworm

# Install system dependencies including postgresql-client-16 from official PostgreSQL repository
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates lsb-release gnupg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql-keyring.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-16 \
    && apt-get purge -y --auto-remove curl ca-certificates lsb-release gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_SYSTEM_PYTHON=1
ENV UV_CACHE_DIR=/tmp/uv_cache

# Install Python deps (cached unless pyproject.toml / uv.lock changes)
COPY pyproject.toml uv.lock ./
RUN uv pip install --no-cache -r pyproject.toml

# Copy backend source
COPY . .

# Overlay the compiled React bundle from stage 1
COPY --from=admin-build /admin_ui/dist ./admin_ui/dist

CMD ["sh", "-c", "gunicorn -w ${WORKERS:-1} -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:${PORT:-8080} --timeout 0"]
