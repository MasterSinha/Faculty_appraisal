# Faculty Appraisal System - Backend API

A high-performance, asynchronous FastAPI backend designed for institutional faculty appraisals across 8 schools. Optimized for low latency (<200ms) and high concurrency.

## 🚀 Key Features
- **Fully Asynchronous Architecture:** Powered by `asyncpg` and SQLAlchemy `AsyncSession` for non-blocking database I/O.
- **High Performance:** Integrated `orjson` for fast serialization and custom middleware for request timing.
- **Hierarchical Access Control:** Strict VC > Dean > Director > HOD > Faculty authorization logic.
- **Production Ready:** Configured with Gunicorn and Uvicorn workers for efficient multi-core processing on GCP Cloud Run.
- **Database Agnostic:** Designed for portability between Supabase and standard PostgreSQL.

## 🛠 Tech Stack
- **Framework:** FastAPI (Asynchronous)
- **Serialization:** `orjson` (High-speed JSON)
- **Database Driver:** `asyncpg` (Async PostgreSQL)
- **ORM:** SQLAlchemy 2.0
- **Process Manager:** Gunicorn with Uvicorn workers
- **Auth & Storage:** Supabase (Async integration)

## ⚙️ Setup & Installation

1.  **Configure Environment:**
    Create a `.env` file in the root:
    ```dotenv
    DATABASE_URL="postgresql://postgres.[ID]:[PWD]@aws-pooler.supabase.com:6543/postgres"
    SUPABASE_URL="https://[ID].supabase.co"
    SUPABASE_ANON_KEY="your-anon-key"
    ```

2.  **Install Dependencies:**
    ```bash
    uv sync
    ```

3.  **Prepare Test Data (Optional):**
    ```bash
    $env:PYTHONPATH="."
    uv run python setup_test_db.py
    ```

4.  **Run Locally:**
    ```bash
    uv run uvicorn main:app --reload
    ```

## 🏗 Deployment (GCP)
The system is optimized for **Google Cloud Run**:
- **Execution:** Managed by Gunicorn with 4 workers (adjustable via `WORKERS` env var).
- **Concurrency:** Non-blocking event loop allows for high requests-per-second.
- **Monitoring:** Check the `X-Process-Time` response header for latency metrics.

- 

## 📚 Documentation
- [Migration & Portability Strategy](Docs/MIGRATION_STRATEGY.md)
- [API V1 Reference](Docs/API_V1_REFERENCE.md)
- [Developer Architecture Guide](Docs/DEVELOPER_GUIDE.md)
- [Testing Guide](Docs/testing_guide.md)
