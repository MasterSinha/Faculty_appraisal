import pytest
import os
import json
import copy
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

# SQLite doesn't know JSONB, so we tell SQLAlchemy to compile it as TEXT in sqlite
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"

from src.models.core import Base, AppraisalDocument, AppraisalSnapshot, ReviewerSnapshot
from src.models.non_teaching import NonTeachingAppraisal
from src.api.v1.appraisal import _rewrite_payload_urls
from src.api.v1.admin import migrate_urls
from src.setup.dependencies import User

@pytest.mark.asyncio
async def test_rewrite_payload_urls():
    app_url = "https://backend.test"
    payload = {
        "docs": {
            "fdp-0": [
                {
                    "url": "/api/v1/upload/view/faculty/test@dypiu.ac.in/file.pdf",
                    "publicId": "faculty/test@dypiu.ac.in/file.pdf"
                }
            ]
        },
        "some_other_field": "hello"
    }
    
    # Run helper
    _rewrite_payload_urls(payload, app_url)
    
    # Assert it prepended APP_URL
    assert payload["docs"]["fdp-0"][0]["url"] == "https://backend.test/api/v1/upload/view/faculty/test@dypiu.ac.in/file.pdf"
    assert payload["some_other_field"] == "hello"

@pytest.mark.asyncio
async def test_url_migration_script():
    # 1. Setup in-memory sqlite engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    # 2. Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with AsyncSessionLocal() as session:
        # 3. Seed mock data with old bucket URLs
        old_bucket = "faculty-appraisal-uploads"
        
        # Document
        doc = AppraisalDocument(
            faculty_email="test@dypiu.ac.in",
            academic_year="2025-2026",
            section="lec-",
            file_name="test.pdf",
            file_url=f"https://storage.googleapis.com/{old_bucket}/faculty/test@dypiu.ac.in/test.pdf",
            storage_path="faculty/test@dypiu.ac.in/test.pdf"
        )
        session.add(doc)
        
        # Appraisal Snapshot
        snap = AppraisalSnapshot(
            faculty_email="test@dypiu.ac.in",
            academic_year="2025-2026",
            payload={
                "docs": {
                    "lec-0": [
                        {
                            "url": f"https://storage.googleapis.com/{old_bucket}/faculty/test@dypiu.ac.in/test.pdf",
                            "publicId": "faculty/test@dypiu.ac.in/test.pdf"
                        }
                    ]
                }
            }
        )
        session.add(snap)
        
        # Reviewer Snapshot
        rev_snap = ReviewerSnapshot(
            faculty_email="test@dypiu.ac.in",
            academic_year="2025-2026",
            reviewer_email="dean@dypiu.ac.in",
            reviewer_role="dean",
            payload={
                "docs": {
                    "lec-0": [
                        {
                            "url": f"https://storage.googleapis.com/{old_bucket}/faculty/test@dypiu.ac.in/test.pdf",
                            "publicId": "faculty/test@dypiu.ac.in/test.pdf"
                        }
                    ]
                }
            }
        )
        session.add(rev_snap)
        
        # Non-teaching Appraisal
        nt = NonTeachingAppraisal(
            staff_email="staff@dypiu.ac.in",
            academic_year="2025-2026",
            status="Draft",
            payload={
                "docs": [
                    {
                        "url": f"https://storage.googleapis.com/{old_bucket}/staff/test.pdf",
                        "publicId": "staff/test.pdf"
                    }
                ]
            }
        )
        session.add(nt)
        await session.commit()
        
        # 4. Invoke the migration function
        # Mock current user as super_admin
        current_user = User(id="admin-id", email="admin@test.com", roles=["super_admin"])
        current_user.appraisal_role = "super_admin"
        
        result = await migrate_urls(
            current_user=current_user,
            db=session,
            old_pattern=old_bucket
        )
        
        # Verify result counts
        assert result["updated_documents"] == 1
        assert result["updated_snapshots"] == 1
        assert result["updated_reviewer_snapshots"] == 1
        assert result["updated_non_teaching_appraisals"] == 1
        
        # 5. Verify the database records have been updated to portable relative URLs
        await session.close()
        
    async with AsyncSessionLocal() as session:
        # Document check
        res = await session.execute(select(AppraisalDocument))
        db_doc = res.scalar_one()
        assert db_doc.file_url == "/api/v1/upload/view/faculty/test@dypiu.ac.in/test.pdf"
        
        # Snapshot check
        res = await session.execute(select(AppraisalSnapshot))
        db_snap = res.scalar_one()
        assert db_snap.payload["docs"]["lec-0"][0]["url"] == "/api/v1/upload/view/faculty/test@dypiu.ac.in/test.pdf"
        
        # Reviewer snapshot check
        res = await session.execute(select(ReviewerSnapshot))
        db_rev = res.scalar_one()
        assert db_rev.payload["docs"]["lec-0"][0]["url"] == "/api/v1/upload/view/faculty/test@dypiu.ac.in/test.pdf"
        
        # Non-teaching check
        res = await session.execute(select(NonTeachingAppraisal))
        db_nt = res.scalar_one()
        assert db_nt.payload["docs"][0]["url"] == "/api/v1/upload/view/staff/test.pdf"
        
        await session.close()
        
    await engine.dispose()
