import pytest
from datetime import datetime
from sqlalchemy import select

from httpx import AsyncClient
from src.setup.database import AsyncSessionLocal
from src.models.core import FacultyProfile, AppraisalSnapshot, AppraisalReview
from src.setup.local_auth import get_password_hash

FACULTY_EMAIL = "cisr_faculty@test.com"
CENTER_HEAD_EMAIL = "cisr_center_head@test.com"
PASSWORD = "testpassword"
YEAR = "2025-26"


async def _seed_cisr_users():
    async with AsyncSessionLocal() as db:
        for email, name, role, school, dept in [
            (FACULTY_EMAIL, "CISR Faculty", "faculty", "CISR", None),
            (CENTER_HEAD_EMAIL, "CISR Center Head", "center_head", "CISR", None),
        ]:
            res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == email))
            if not res.scalar_one_or_none():
                db.add(FacultyProfile(
                    email=email,
                    password_hash=get_password_hash(PASSWORD),
                    full_name=name,
                    appraisal_role=role,
                    school=school,
                    department=dept,
                    is_verified=True,
                ))
        await db.commit()


async def _seed_cisr_snapshot_and_review():
    async with AsyncSessionLocal() as db:
        snapshot = AppraisalSnapshot(
            faculty_email=FACULTY_EMAIL,
            academic_year=YEAR,
            payload={
                "form": {"title": "CISR appraisal"},
                "totals": {"partATotal": 50, "partBTotal": 100, "grandTotal": 150},
            },
        )
        db.add(snapshot)
        await db.flush()

        review = AppraisalReview(
            faculty_email=FACULTY_EMAIL,
            academic_year=YEAR,
            reviewer_email=CENTER_HEAD_EMAIL,
            reviewer_role="center_head",
            part_a_score=20,
            part_b_score=40,
            total_score=60,
            remarks="Good performance",
            section_scores={},
            status="Reviewed",
            reviewed_at=datetime.utcnow(),
        )
        db.add(review)
        await db.commit()


@pytest.fixture
async def center_head_headers(client: AsyncClient):
    await _seed_cisr_users()
    await _seed_cisr_snapshot_and_review()
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": CENTER_HEAD_EMAIL, "password": PASSWORD},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.mark.asyncio
async def test_dashboard_faculty_returns_cisr_center_head_review(client: AsyncClient, center_head_headers: dict):
    res = await client.get(
        f"/api/v1/dashboard/faculty/{FACULTY_EMAIL}?academic_year={YEAR}",
        headers=center_head_headers,
    )
    assert res.status_code == 200, res.text

    data = res.json()
    assert "reviews" in data
    reviews = data["reviews"]
    assert any(
        review["reviewer_role"] == "center_head" and
        review["part_a_score"] == 20 and
        review["part_b_score"] == 40 and
        review["total_score"] == 60
        for review in reviews
    ), "Expected center_head review scores in dashboard payload"
