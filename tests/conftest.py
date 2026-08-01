import os
import tempfile
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport

# Create a temporary SQLite database for testing
db_fd, db_path = tempfile.mkstemp()
os.close(db_fd)
db_url = f"sqlite+aiosqlite:///{db_path.replace('\\', '/')}"
os.environ["DATABASE_URL"] = db_url
os.environ["TESTING"] = "True"
os.environ["MFA_ENABLED"] = "false"
os.environ["TWO_FACTOR_AUTH"] = "false"
os.environ["USE_LOCAL_STORAGE"] = "true"

# Force SQLAlchemy to compile JSONB to TEXT for SQLite
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"

# Force load all models so metadata knows about them
import src.models.core
import src.models.part_a
import src.models.part_b
import src.models.non_teaching

from src.main import app
from src.setup.database import engine, Base, AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, delete
from src.models.core import FacultyProfile, Declaration, AppraisalSnapshot, AppraisalReview, ReviewerSnapshot
from src.models.non_teaching import NonTeachingAppraisal, NonTeachingPartAItem, NonTeachingPartBRating

import atexit

def cleanup_temp_db():
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

atexit.register(cleanup_temp_db)

@pytest.fixture(scope="function", autouse=True)
async def setup_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


# Fix for event loop scope in pytest-asyncio
@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture(scope="function")
async def db():
    async with AsyncSessionLocal() as session:
        yield session
        # Cleanup is handled by specific test teardowns or global reset if safe

@pytest.fixture(scope="function", autouse=True)
async def cleanup_db():
    """
    Cleans up test data after each test.
    We identify test data by the '@test.com' domain.
    Silently skips cleanup if no DB connection is available (e.g., unit tests on Windows).
    """
    yield
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(Declaration).where(Declaration.faculty_email.like("%@test.com")))
            await db.execute(delete(AppraisalSnapshot).where(AppraisalSnapshot.faculty_email.like("%@test.com")))
            await db.execute(delete(AppraisalReview).where(AppraisalReview.faculty_email.like("%@test.com")))
            await db.execute(delete(ReviewerSnapshot).where(ReviewerSnapshot.faculty_email.like("%@test.com")))
            await db.execute(delete(NonTeachingPartAItem).where(NonTeachingPartAItem.staff_email.like("%@test.com")))
            await db.execute(delete(NonTeachingPartBRating).where(NonTeachingPartBRating.staff_email.like("%@test.com")))
            await db.execute(delete(NonTeachingAppraisal).where(NonTeachingAppraisal.staff_email.like("%@test.com")))
            await db.execute(delete(FacultyProfile).where(FacultyProfile.email.like("%@test.com")))
            await db.commit()
    except Exception:
        pass  # No DB connection available (e.g., Cloud SQL socket on Windows) — skip cleanup
