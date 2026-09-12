from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os
import re
from dotenv import load_dotenv

env_file = os.getenv("ENV_FILE")
is_testing = str(os.getenv("TESTING", "")).lower() in ("true", "1", "yes") or str(os.getenv("ENVIRONMENT", "")).lower() == "test"

if env_file and os.path.exists(env_file):
    load_dotenv(env_file, override=False)
elif is_testing and os.path.exists(".env.test"):
    load_dotenv(".env.test", override=False)
elif os.path.exists(".env"):
    load_dotenv(".env", override=False)
elif os.path.exists(".env.test"):
    load_dotenv(".env.test", override=False)
else:
    load_dotenv(override=False)

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

def split_sql_statements(sql_text: str) -> list[str]:
    """
    Splits SQL script into individual executable statements, correctly ignoring
    semicolons inside single quotes, block comments, line comments, and dollar-quoted blocks.
    """
    clean_sql = re.sub(r'/\*.*?\*/', '', sql_text, flags=re.DOTALL)
    clean_sql = re.sub(r'--[^\n]*', '', clean_sql)

    statements = []
    current = []
    in_single_quote = False
    in_dollar_quote = False
    dollar_tag = ""
    i = 0
    n = len(clean_sql)

    while i < n:
        char = clean_sql[i]

        if not in_single_quote:
            if not in_dollar_quote:
                if char == '$':
                    m = re.match(r'(\$[A-Za-z0-9_]*\$)', clean_sql[i:])
                    if m:
                        dollar_tag = m.group(1)
                        in_dollar_quote = True
                        current.append(dollar_tag)
                        i += len(dollar_tag)
                        continue
            else:
                if clean_sql[i:i+len(dollar_tag)] == dollar_tag:
                    in_dollar_quote = False
                    current.append(dollar_tag)
                    i += len(dollar_tag)
                    dollar_tag = ""
                    continue

        if not in_dollar_quote:
            if char == "'":
                if in_single_quote and i + 1 < n and clean_sql[i+1] == "'":
                    current.append("''")
                    i += 2
                    continue
                in_single_quote = not in_single_quote
                current.append(char)
                i += 1
                continue

        if char == ';' and not in_single_quote and not in_dollar_quote:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue

        current.append(char)
        i += 1

    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)
    return statements


async def run_auto_migrations():
    """
    Scans the migrations/ directory for sorted SQL files, compares with
    a schema_migrations table, and applies any pending migrations in a transaction.
    Skipped for SQLite in-memory / unit testing, or if explicitly disabled via SKIP_AUTO_MIGRATIONS.
    """
    if SQLALCHEMY_DATABASE_URL and SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        return

    if os.getenv("SKIP_AUTO_MIGRATIONS", "").lower() in ("true", "1", "yes"):
        return

    import logging
    logger = logging.getLogger(__name__)

    migration_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "migrations"))
    if not os.path.exists(migration_dir):
        logger.warning(f"Migration directory not found at: {migration_dir}")
        return

    # 0. Automatically create any missing ORM tables via SQLAlchemy metadata
    try:
        import src.models
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLAlchemy Base.metadata.create_all completed successfully.")
    except Exception as e:
        logger.error(f"Error during Base.metadata.create_all: {e}", exc_info=True)

    from sqlalchemy import text
    async with AsyncSessionLocal() as session:
        try:
            # Direct ensure for schools form columns in PostgreSQL
            try:
                await session.execute(text("""
                    ALTER TABLE IF EXISTS public.schools 
                    ADD COLUMN IF NOT EXISTS form_variant VARCHAR(50) NOT NULL DEFAULT 'standard',
                    ADD COLUMN IF NOT EXISTS form_type VARCHAR(50) NOT NULL DEFAULT 'FORM_A',
                    ADD COLUMN IF NOT EXISTS form_label VARCHAR(255) NOT NULL DEFAULT 'Standard Appraisal';
                """))
                await session.commit()
            except Exception as sch_col_err:
                logger.warning(f"Note on direct ensure schools columns: {sch_col_err}")
                await session.rollback()

            # Direct ensure for feedback attachment columns in PostgreSQL
            try:
                await session.execute(text("""
                    ALTER TABLE IF EXISTS public.feedback 
                    ADD COLUMN IF NOT EXISTS attachment_filename VARCHAR(255),
                    ADD COLUMN IF NOT EXISTS attachment_content_type VARCHAR(100),
                    ADD COLUMN IF NOT EXISTS attachment_size INTEGER,
                    ADD COLUMN IF NOT EXISTS attachment_storage_path VARCHAR(500);
                """))
                await session.commit()
            except Exception as fb_col_err:
                logger.warning(f"Note on direct ensure feedback attachment columns: {fb_col_err}")
                await session.rollback()

            # Direct ensure for form_section_definitions and custom_fields in PostgreSQL
            try:
                await session.execute(text("""
                    ALTER TABLE IF EXISTS public.form_section_definitions 
                    ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT true,
                    ADD COLUMN IF NOT EXISTS "order" INTEGER NOT NULL DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS table_order JSONB NOT NULL DEFAULT '[]'::jsonb;
                """))
                await session.commit()
            except Exception as fsd_col_err:
                logger.warning(f"Note on direct ensure form_section_definitions columns: {fsd_col_err}")
                await session.rollback()

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
            if "036_form_builder_and_custom_sections.sql" in applied:
                res_036 = await session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'custom_section_rows'
                    ) AND EXISTS (
                        SELECT FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = 'form_section_definitions'
                        AND column_name = 'active'
                    );
                """))
                if not res_036.scalar():
                    logger.warning("Migration 036 was marked applied but custom_section_rows or form_section_definitions.active is missing. Forcing re-run.")
                    applied.discard("036_form_builder_and_custom_sections.sql")
                    await session.execute(
                        text("DELETE FROM schema_migrations WHERE version = :version"),
                        {"version": "036_form_builder_and_custom_sections.sql"}
                    )
                    await session.commit()
            if "035_fix_duplicate_schools_and_add_unique_constraints.sql" in applied:
                res_035 = await session.execute(text("""
                    SELECT 
                        (SELECT COUNT(*) FROM public.schools WHERE LOWER(TRIM(code)) = 'soemr') = 1
                        AND EXISTS (
                            SELECT 1 FROM pg_indexes 
                            WHERE tablename = 'schools' 
                            AND indexname = 'idx_schools_lower_code'
                        );
                """))
                if not res_035.scalar():
                    logger.warning("Migration 035 was marked applied but school uniqueness/canonical SoEMR is not intact. Forcing re-run.")
                    applied.discard("035_fix_duplicate_schools_and_add_unique_constraints.sql")
                    await session.execute(
                        text("DELETE FROM schema_migrations WHERE version = :version"),
                        {"version": "035_fix_duplicate_schools_and_add_unique_constraints.sql"}
                    )
                    await session.commit()

            if "034_fix_cisr_school_configuration.sql" in applied:
                res_034 = await session.execute(text("""
                    SELECT EXISTS (
                        SELECT 1 FROM public.schools 
                        WHERE code = 'CISR' 
                        AND track = 'cisr' 
                        AND approval_chain::text LIKE '%center_head%'
                    );
                """))
                if not res_034.scalar():
                    logger.warning("Migration 034 was marked applied but CISR school configuration is outdated. Forcing re-run.")
                    applied.discard("034_fix_cisr_school_configuration.sql")
                    await session.execute(
                        text("DELETE FROM schema_migrations WHERE version = :version"),
                        {"version": "034_fix_cisr_school_configuration.sql"}
                    )
                    await session.commit()

            if "033_add_feedback_attachments.sql" in applied:
                res_033 = await session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = 'feedback' 
                        AND column_name = 'attachment_filename'
                    );
                """))
                if not res_033.scalar():
                    logger.warning("Migration 033 was marked applied but column 'attachment_filename' on 'feedback' is missing. Forcing re-run.")
                    applied.discard("033_add_feedback_attachments.sql")
                    await session.execute(
                        text("DELETE FROM schema_migrations WHERE version = :version"),
                        {"version": "033_add_feedback_attachments.sql"}
                    )
                    await session.commit()

            if "032_add_school_form_variants.sql" in applied:
                res_032 = await session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = 'schools' 
                        AND column_name = 'form_variant'
                    );
                """))
                if not res_032.scalar():
                    logger.warning("Migration 032 was marked applied but column 'form_variant' on 'schools' is missing. Forcing re-run.")
                    applied.discard("032_add_school_form_variants.sql")
                    await session.execute(
                        text("DELETE FROM schema_migrations WHERE version = :version"),
                        {"version": "032_add_school_form_variants.sql"}
                    )
                    await session.commit()

            if "031_create_schools_table.sql" in applied:
                res_031 = await session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'schools'
                    );
                """))
                if not res_031.scalar():
                    logger.warning("Migration 031 was marked applied but table 'schools' is missing. Forcing re-run.")
                    applied.discard("031_create_schools_table.sql")
                    await session.execute(
                        text("DELETE FROM schema_migrations WHERE version = :version"),
                        {"version": "031_create_schools_table.sql"}
                    )
                    await session.commit()

            if "028_add_activity_logs.sql" in applied:
                res_028 = await session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'activity_logs'
                    );
                """))

                if not res_028.scalar():
                    logger.warning("Migration 028 was marked applied but table 'activity_logs' is missing. Forcing re-run.")
                    applied.discard("028_add_activity_logs.sql")
                    await session.execute(
                        text("DELETE FROM schema_migrations WHERE version = :version"),
                        {"version": "028_add_activity_logs.sql"}
                    )
                    await session.commit()

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

            # Self-healing verification for non_teaching_appraisals status check
            try:
                chk_res = await session.execute(text("""
                    SELECT pg_get_constraintdef(c.oid)
                    FROM pg_constraint c
                    JOIN pg_class t ON c.conrelid = t.oid
                    WHERE t.relname = 'non_teaching_appraisals'
                    AND c.conname = 'non_teaching_appraisals_status_check';
                """))
                chk_def = chk_res.scalar()
                if not chk_def or "Pending VC Review" not in chk_def:
                    logger.warning("non_teaching_appraisals_status_check is missing 'Pending VC Review'. Updating constraint.")
                    await session.execute(text("ALTER TABLE public.non_teaching_appraisals DROP CONSTRAINT IF EXISTS non_teaching_appraisals_status_check;"))
                    await session.execute(text("""
                        ALTER TABLE public.non_teaching_appraisals
                        ADD CONSTRAINT non_teaching_appraisals_status_check
                        CHECK (status IN (
                            'Draft',
                            'Submitted',
                            'Pending RO Review',
                            'Pending Registrar Review',
                            'Pending VC Review',
                            'Reporting Officer Reviewed',
                            'Registrar Reviewed',
                            'VC Approved',
                            'Reviewed',
                            'Rejected'
                        ));
                    """))
                    await session.commit()
            except Exception as chk_err:
                logger.warning(f"Could not verify or update non_teaching_appraisals_status_check constraint: {chk_err}")

            # 3. Apply sorted pending migrations (only numbered files like 001_xxx.sql)
            files = sorted([
                f for f in os.listdir(migration_dir) 
                if f.endswith(".sql") and len(f) >= 4 and f[:3].isdigit() and f[3] == '_'
            ])
            for filename in files:
                if filename not in applied:
                    logger.info(f"Applying database schema migration: {filename}")
                    file_path = os.path.join(migration_dir, filename)
                    with open(file_path, "r", encoding="utf-8") as f:
                        sql_content = f.read().strip()

                    if sql_content:
                        statements = split_sql_statements(sql_content)
                        for stmt in statements:
                            try:
                                async with session.begin_nested():
                                    await session.execute(text(stmt))
                            except Exception as stmt_err:
                                err_str = str(stmt_err).lower()
                                if any(x in err_str for x in ("already exists", "duplicate", "duplicatetable", "duplicateobject", "check constraint", "checkviolationerror", "violated by some row")):
                                    logger.info(f"Notice during migration {filename}: {stmt_err} ({stmt[:60]}...)")
                                else:
                                    raise

                    await session.execute(
                        text("INSERT INTO schema_migrations (version) VALUES (:version) ON CONFLICT (version) DO NOTHING"),
                        {"version": filename}
                    )
                    await session.commit()
                    logger.info(f"Successfully applied: {filename}")

        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to run database migrations: {e}", exc_info=True)
            raise
