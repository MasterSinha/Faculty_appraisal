"""
Direct database migration script to ensure `form_variant`, `form_type`, and `form_label`
columns exist on `schools` table and backfill legacy creative schools.

Usage:
    python3 scripts/migrate_school_form_variants.py
"""

import asyncio
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from src.setup.database import AsyncSessionLocal, SQLALCHEMY_DATABASE_URL


async def main():
    print(f"Connecting to database: {SQLALCHEMY_DATABASE_URL.split('@')[-1] if '@' in SQLALCHEMY_DATABASE_URL else SQLALCHEMY_DATABASE_URL}")
    async with AsyncSessionLocal() as session:
        try:
            print("1. Adding columns to 'schools' table if not exist...")
            await session.execute(text("""
                ALTER TABLE public.schools 
                ADD COLUMN IF NOT EXISTS form_variant VARCHAR(50) NOT NULL DEFAULT 'standard',
                ADD COLUMN IF NOT EXISTS form_type VARCHAR(50) NOT NULL DEFAULT 'FORM_A',
                ADD COLUMN IF NOT EXISTS form_label VARCHAR(255) NOT NULL DEFAULT 'Standard Appraisal';
            """))
            await session.commit()
            print("   -> Columns added successfully.")

            print("2. Backfilling creative school variants...")
            await session.execute(text("""
                UPDATE public.schools
                SET form_variant = 'mediaCommunication',
                    form_type = 'FORM_B',
                    form_label = 'Creative Appraisal - Media Communication'
                WHERE UPPER(code) IN ('SOMCS', 'SOHSS');

                UPDATE public.schools
                SET form_variant = 'designArts',
                    form_type = 'FORM_C',
                    form_label = 'Creative Appraisal - Design Arts'
                WHERE UPPER(code) IN ('SOD', 'SOAA');

                UPDATE public.schools
                SET form_variant = 'standard',
                    form_type = 'FORM_A',
                    form_label = 'Standard Appraisal'
                WHERE default_form = 'standard';
            """))
            await session.commit()
            print("   -> Existing schools backfilled successfully.")

            # Record in schema_migrations if table exists
            try:
                await session.execute(text("""
                    INSERT INTO schema_migrations (version) 
                    VALUES ('032_add_school_form_variants.sql')
                    ON CONFLICT (version) DO NOTHING;
                """))
                await session.commit()
                print("   -> Migration 032 recorded in schema_migrations.")
            except Exception as e:
                print(f"   (Note on schema_migrations record: {e})")

            print("\n[SUCCESS] All school form columns and variants are fully migrated!")

        except Exception as e:
            await session.rollback()
            print(f"\n[ERROR] Migration failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
