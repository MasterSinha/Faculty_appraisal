from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os
from dotenv import load_dotenv

if not os.getenv("TESTING"):
    load_dotenv(override=True)
else:
    load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
if SQLALCHEMY_DATABASE_URL and SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif SQLALCHEMY_DATABASE_URL and SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

if SQLALCHEMY_DATABASE_URL and SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True
    )
else:
    engine = create_async_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args={"statement_cache_size": 0}
    )
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def run_auto_migrations():
    """
    Scans the migrations/ directory for sorted SQL files, compares with
    a schema_migrations table, and applies any pending migrations in a transaction.
    Skipped when TESTING is active (SQLite).
    """
    if os.getenv("TESTING"):
        return

    import logging
    logger = logging.getLogger(__name__)

    migration_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "migrations"))
    if not os.path.exists(migration_dir):
        logger.warning(f"Migration directory not found at: {migration_dir}")
        return

    from sqlalchemy import text
    async with AsyncSessionLocal() as session:
        try:
            # 1. Create migrations tracking table
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            await session.commit()

            # 2. Query already applied migration versions
            result = await session.execute(text("SELECT version FROM schema_migrations"))
            applied = {row[0] for row in result.all()}

            # 3. Apply sorted pending migrations
            files = sorted([f for f in os.listdir(migration_dir) if f.endswith(".sql")])
            for filename in files:
                if filename not in applied:
                    logger.info(f"Applying database schema migration: {filename}")
                    file_path = os.path.join(migration_dir, filename)
                    with open(file_path, "r", encoding="utf-8") as f:
                        sql_content = f.read().strip()

                    if sql_content:
                        await session.execute(text(sql_content))

                    await session.execute(
                        text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                        {"version": filename}
                    )
                    await session.commit()
                    logger.info(f"Successfully applied: {filename}")

        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to run database migrations: {e}", exc_info=True)
            raise
