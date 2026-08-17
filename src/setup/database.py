from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os
from dotenv import load_dotenv

env_file = os.getenv("ENV_FILE")
if env_file and os.path.exists(env_file):
    load_dotenv(env_file, override=True)
elif os.getenv("TESTING") == "True":
    if os.path.exists(".env.test"):
        load_dotenv(".env.test")
    else:
        load_dotenv()
elif os.path.exists(".env.test") and not os.path.exists(".env"):
    load_dotenv(".env.test", override=True)
else:
    load_dotenv(override=True)

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

            # Self-healing verification: Check if critical tables/columns actually exist in the DB.
            # If a migration is marked applied but its schema objects are missing, force re-run by removing it.
            if "027_dynamic_departments_and_part_d.sql" in applied:
                res_027 = await session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'hod_assignments'
                    );
                """))
                if not res_027.scalar():
                    logger.warning("Migration 027 was marked applied but table 'hod_assignments' is missing. Forcing re-run.")
                    applied.discard("027_dynamic_departments_and_part_d.sql")
                    await session.execute(
                        text("DELETE FROM schema_migrations WHERE version = :version"),
                        {"version": "027_dynamic_departments_and_part_d.sql"}
                    )
                    await session.commit()

            if "026_add_profile_picture_url.sql" in applied:
                res_026 = await session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = 'faculty_profiles' 
                        AND column_name = 'profile_picture_url'
                    );
                """))
                if not res_026.scalar():
                    logger.warning("Migration 026 was marked applied but column 'profile_picture_url' is missing. Forcing re-run.")
                    applied.discard("026_add_profile_picture_url.sql")
                    await session.execute(
                        text("DELETE FROM schema_migrations WHERE version = :version"),
                        {"version": "026_add_profile_picture_url.sql"}
                    )
                    await session.commit()

            if "025_create_part_c_tables.sql" in applied:
                res_025 = await session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'event_organisation'
                    );
                """))
                if not res_025.scalar():
                    logger.warning("Migration 025 was marked applied but table 'event_organisation' is missing. Forcing re-run.")
                    applied.discard("025_create_part_c_tables.sql")
                    await session.execute(
                        text("DELETE FROM schema_migrations WHERE version = :version"),
                        {"version": "025_create_part_c_tables.sql"}
                    )
                    await session.commit()

            if "024_add_part_c_and_d_scores.sql" in applied:
                res_024 = await session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = 'declarations' 
                        AND column_name = 'part_c_total'
                    );
                """))
                if not res_024.scalar():
                    logger.warning("Migration 024 was marked applied but column 'part_c_total' is missing. Forcing re-run.")
                    applied.discard("024_add_part_c_and_d_scores.sql")
                    await session.execute(
                        text("DELETE FROM schema_migrations WHERE version = :version"),
                        {"version": "024_add_part_c_and_d_scores.sql"}
                    )
                    await session.commit()


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
