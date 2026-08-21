"""
Tests for the Director → Dean → VC review chain (teaching staff).
The HOD step is covered in test_v1_authority.py; this file extends
to the remaining three reviewer roles and tests cross-role attacks.

Reviewer users are injected via dependency_overrides so we don't need
real DB accounts or JWT tokens for them.  The faculty target MUST exist
in the DB (handle_review looks it up by email), so we seed it directly
with is_verified=True to bypass the email-verification flow.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from src.main import app
from src.setup.dependencies import User, get_current_user
from src.setup.database import AsyncSessionLocal
from src.models.core import FacultyProfile
from src.setup.local_auth import get_password_hash

FACULTY_EMAIL = "chain_faculty@test.com"
YEAR = "2025-26"

SUBMIT_DATA = {
    "academic_year": YEAR,
    "form": {
        "lectures": [
            {
                "semester": "Sem 1",
                "course_code": "CS101",
                "planned_classes": 40,
                "conducted_classes": 38,
            }
        ],
    },
    "totals": {"partATotal": 10, "partBTotal": 10, "grandTotal": 20},
}

REVIEW_DATA = {
    "academic_year": YEAR,
    "remarks": "Good performance",
    "part_a_score": 45,
    "part_b_score": 40,
    "total_score": 85,
}


async def _seed_faculty():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FacultyProfile).where(FacultyProfile.email == FACULTY_EMAIL)
        )
        if not result.scalar_one_or_none():
            db.add(
                FacultyProfile(
                    email=FACULTY_EMAIL,
                    password_hash=get_password_hash("password"),
                    full_name="Chain Test Faculty",
                    appraisal_role="faculty",
                    school="SoEMR",
                    department="Mechanical",
                    is_verified=True,
                )
            )
            await db.commit()


@pytest.mark.asyncio
async def test_full_review_chain():
    """HOD → Director → Dean → VC chain advances declaration status correctly."""
    await _seed_faculty()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        try:
            # Faculty logs in (is_verified=True so login succeeds)
            login_res = await client.post(
                "/api/v1/auth/login",
                json={"email": FACULTY_EMAIL, "password": "password"},
            )
            assert login_res.status_code == 200, login_res.text
            faculty_headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

            # Faculty submits appraisal
            submit_res = await client.post(
                "/api/v1/appraisal/submit", json=SUBMIT_DATA, headers=faculty_headers
            )
            assert submit_res.status_code == 200, submit_res.text

            # HOD review → pending_director
            async def get_hod():
                return User(
                    id="hod-chain-id",
                    email="hod_chain@test.com",
                    roles=["hod"],
                    school="SoEMR",
                    department="Mechanical",
                )

            app.dependency_overrides[get_current_user] = get_hod
            resp = await client.put(
                f"/api/v1/appraisal-remarks/hod/{FACULTY_EMAIL}", json=REVIEW_DATA
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["status"] == "Pending Director Review"

            # Director review → pending_dean
            async def get_director():
                return User(
                    id="dir-chain-id",
                    email="director_chain@test.com",
                    roles=["director"],
                    school="SoEMR",
                )

            app.dependency_overrides[get_current_user] = get_director
            resp = await client.put(
                f"/api/v1/appraisal-remarks/director/{FACULTY_EMAIL}", json=REVIEW_DATA
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["status"] == "Pending Dean Review"

            # Dean review → pending_vc
            # Dean's school must be "engineering" and faculty must be in ENGINEERING_SCHOOLS
            async def get_dean():
                return User(
                    id="dean-chain-id",
                    email="dean_chain@test.com",
                    roles=["dean"],
                    school="engineering",
                )

            app.dependency_overrides[get_current_user] = get_dean
            resp = await client.put(
                f"/api/v1/appraisal-remarks/dean/{FACULTY_EMAIL}", json=REVIEW_DATA
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["status"] == "Pending VC Review"

            # Registrar releases Part D (Leave & Attendance)
            import uuid
            registrar_id = str(uuid.uuid4())
            async def get_registrar():
                return User(
                    id=registrar_id,
                    email="registrar_chain@test.com",
                    roles=["registrar"],
                )

            app.dependency_overrides[get_current_user] = get_registrar
            resp = await client.post(
                f"/api/v1/dashboard/part-d-release/{FACULTY_EMAIL}",
                json={"registrar_part_d_score": 15.0, "academic_year": YEAR}
            )
            assert resp.status_code == 200, resp.text

            # VC review → completed
            async def get_vc():
                return User(
                    id="vc-chain-id",
                    email="vc_chain@test.com",
                    roles=["vc"],
                )

            app.dependency_overrides[get_current_user] = get_vc
            resp = await client.put(
                f"/api/v1/appraisal-remarks/final/{FACULTY_EMAIL}", json=REVIEW_DATA
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["status"] == "Reviewed"

        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_hod_cannot_use_director_endpoint():
    """An HOD must not be able to call the director review endpoint."""
    await _seed_faculty()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        try:
            async def get_hod():
                return User(
                    id="hod-chain-id",
                    email="hod_chain@test.com",
                    roles=["hod"],
                    school="SoCSEA",
                    department="Computer Science",
                )

            app.dependency_overrides[get_current_user] = get_hod
            resp = await client.put(
                f"/api/v1/appraisal-remarks/director/{FACULTY_EMAIL}", json=REVIEW_DATA
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_faculty_cannot_use_hod_endpoint():
    """A faculty member must not be able to call the HOD review endpoint."""
    await _seed_faculty()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        try:
            async def get_faculty():
                return User(
                    id="fac-chain-id",
                    email="attacker_chain@test.com",
                    roles=["faculty"],
                    school="SoCSEA",
                    department="Computer Science",
                )

            app.dependency_overrides[get_current_user] = get_faculty
            resp = await client.put(
                f"/api/v1/appraisal-remarks/hod/{FACULTY_EMAIL}", json=REVIEW_DATA
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_hod_different_school_is_rejected():
    """An HOD from a different school cannot review faculty outside their school."""
    await _seed_faculty()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        try:
            async def get_foreign_hod():
                return User(
                    id="hod2-chain-id",
                    email="hod2_chain@test.com",
                    roles=["hod"],
                    school="SoMCS",  # different school
                    department="Computer Science",
                )

            app.dependency_overrides[get_current_user] = get_foreign_hod
            resp = await client.put(
                f"/api/v1/appraisal-remarks/hod/{FACULTY_EMAIL}", json=REVIEW_DATA
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_director_different_school_is_rejected():
    """A director from a different school cannot review faculty outside their school."""
    await _seed_faculty()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        try:
            async def get_foreign_director():
                return User(
                    id="dir2-chain-id",
                    email="dir2_chain@test.com",
                    roles=["director"],
                    school="SoBB",  # different school from SoCSEA
                )

            app.dependency_overrides[get_current_user] = get_foreign_director
            resp = await client.put(
                f"/api/v1/appraisal-remarks/director/{FACULTY_EMAIL}", json=REVIEW_DATA
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()
