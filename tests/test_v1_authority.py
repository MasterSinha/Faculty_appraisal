"""
Tests for HOD authority and dashboard visibility.
Unique coverage: GET /dashboard/subordinates (faculty appear after submitting),
and the faculty-side view of their own status after an HOD review.

The HOD review step itself is already covered by test_review_chain.py;
this file focuses on the dashboard and the faculty's status perspective.
Both users are seeded directly with is_verified=True.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.setup.database import AsyncSessionLocal
from src.models.core import FacultyProfile
from src.setup.local_auth import get_password_hash

HOD_EMAIL = "auth_hod@test.com"
FACULTY_EMAIL = "auth_faculty@test.com"
PASSWORD = "password"
YEAR = "2025-26"


async def _seed(email: str, role: str, school: str, department: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FacultyProfile).where(FacultyProfile.email == email)
        )
        if not result.scalar_one_or_none():
            db.add(
                FacultyProfile(
                    email=email,
                    password_hash=get_password_hash(PASSWORD),
                    full_name=f"Test {role}",
                    appraisal_role=role,
                    school=school,
                    department=department,
                    is_verified=True,
                )
            )
            await db.commit()


@pytest.fixture
async def hod_headers(client: AsyncClient):
    await _seed(HOD_EMAIL, "hod", "SoEMR", "Mechanical")
    login = await client.post(
        "/api/v1/auth/login", json={"email": HOD_EMAIL, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['token']}"}


@pytest.fixture
async def faculty_headers(client: AsyncClient):
    await _seed(FACULTY_EMAIL, "faculty", "SoEMR", "Mechanical")
    login = await client.post(
        "/api/v1/auth/login", json={"email": FACULTY_EMAIL, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['token']}"}


@pytest.mark.asyncio
async def test_hod_sees_subordinate_in_dashboard(
    client: AsyncClient, hod_headers: dict, faculty_headers: dict
):
    # Faculty submits so they appear in the dashboard
    await client.post(
        "/api/v1/appraisal/submit",
        json={
            "academic_year": YEAR,
            "form": {},
            "totals": {"grandTotal": 50},
        },
        headers=faculty_headers,
    )

    resp = await client.get(
        f"/api/v1/dashboard/subordinates?academic_year={YEAR}",
        headers=hod_headers,
    )
    assert resp.status_code == 200
    emails = [s["email"] for s in resp.json()]
    assert FACULTY_EMAIL in emails


@pytest.mark.asyncio
async def test_faculty_sees_pending_director_after_hod_review(
    client: AsyncClient, hod_headers: dict, faculty_headers: dict
):
    # Faculty submits
    await client.post(
        "/api/v1/appraisal/submit",
        json={
            "academic_year": YEAR,
            "form": {},
            "totals": {"grandTotal": 50},
        },
        headers=faculty_headers,
    )

    # HOD reviews
    review_resp = await client.put(
        f"/api/v1/appraisal-remarks/hod/{FACULTY_EMAIL}",
        json={
            "academic_year": YEAR,
            "remarks": "Good work",
            "part_a_score": 40,
            "part_b_score": 35,
            "total_score": 75,
        },
        headers=hod_headers,
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "Pending Director Review"

    # Faculty checks their own status
    status_resp = await client.get(
        f"/api/v1/appraisal/status?academic_year={YEAR}",
        headers=faculty_headers,
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["declaration"]["status"] == "Pending Director Review"
