"""
Tests for the core faculty appraisal workflow.
Unique coverage: snapshot save/retrieve (PUT + GET /appraisal/snapshot),
appraisal submit, and GET /appraisal/status.

The user is seeded directly with is_verified=True to avoid the
email-verification block that prevents login after a fresh register.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.setup.database import AsyncSessionLocal
from src.models.core import FacultyProfile
from src.setup.local_auth import get_password_hash

FACULTY_EMAIL = "workflow_faculty@test.com"
PASSWORD = "password"
YEAR = "2025-26"


async def _seed_faculty():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FacultyProfile).where(FacultyProfile.email == FACULTY_EMAIL)
        )
        if not result.scalar_one_or_none():
            db.add(
                FacultyProfile(
                    email=FACULTY_EMAIL,
                    password_hash=get_password_hash(PASSWORD),
                    full_name="Workflow Faculty",
                    appraisal_role="faculty",
                    school="SoCSEA",
                    department="Computer Science",
                    is_verified=True,
                )
            )
            await db.commit()


@pytest.fixture
async def auth_headers(client: AsyncClient):
    await _seed_faculty()
    login = await client.post(
        "/api/v1/auth/login", json={"email": FACULTY_EMAIL, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['token']}"}


@pytest.mark.asyncio
async def test_appraisal_snapshot_and_submit(client: AsyncClient, auth_headers: dict):
    snapshot_payload = {
        "academic_year": YEAR,
        "payload": {
            "form": {
                "lectures": [
                    {
                        "semester": "Sem 1",
                        "course_code": "CS101",
                        "planned_classes": 40,
                        "conducted_classes": 38,
                    }
                ],
                "journals": [
                    {"title": "Test Paper", "journal": "Test Journal", "score": 10}
                ],
            },
            "totals": {"partATotal": 10, "partBTotal": 10, "grandTotal": 20},
        },
    }

    # Save snapshot (draft)
    save_res = await client.put(
        "/api/v1/appraisal/snapshot", json=snapshot_payload, headers=auth_headers
    )
    assert save_res.status_code == 200
    assert save_res.json()["message"] == "Saved"

    # Retrieve snapshot
    get_res = await client.get(
        f"/api/v1/appraisal/snapshot?academic_year={YEAR}", headers=auth_headers
    )
    assert get_res.status_code == 200
    assert (
        get_res.json()["payload"]["form"]["lectures"][0]["course_code"] == "CS101"
    )

    # Submit appraisal
    submit_res = await client.post(
        "/api/v1/appraisal/submit",
        json={
            "academic_year": YEAR,
            "form": snapshot_payload["payload"]["form"],
            "totals": snapshot_payload["payload"]["totals"],
        },
        headers=auth_headers,
    )
    assert submit_res.status_code == 200
    assert "Submitted" in submit_res.json()["message"]

    # Check status
    status_res = await client.get(
        f"/api/v1/appraisal/status?academic_year={YEAR}", headers=auth_headers
    )
    assert status_res.status_code == 200
    decl = status_res.json()["declaration"]
    assert decl["status"] == "Pending Director Review"
    assert decl["grand_total"] == 20
