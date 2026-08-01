import pytest
from httpx import AsyncClient
from sqlalchemy import select
from src.setup.database import AsyncSessionLocal
from src.models.core import FacultyProfile
from src.models.part_a import CourseFile
from src.setup.local_auth import get_password_hash

FACULTY_EMAIL = "normalizer_faculty@test.com"
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
                    full_name="Normalizer Faculty",
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
async def test_course_file_normalization_success(client: AsyncClient, auth_headers: dict):
    test_cases = [
        ("Yes", "1.Available"),
        ("No", "3.Not Available"),
        ("1.Available", "1.Available"),
        ("2.Partially Available", "2.Partially Available"),
        ("3.Not Available", "3.Not Available"),
        ("Available", "1.Available"),
        ("Partial", "2.Partially Available"),
        ("Partially Available", "2.Partially Available"),
        ("Not Available", "3.Not Available"),
    ]
    
    for idx, (input_val, expected_val) in enumerate(test_cases):
        year = f"2025-26-{idx}"
        submit_res = await client.post(
            "/api/v1/appraisal/submit",
            json={
                "academic_year": year,
                "form": {
                    "courseFile": [
                        {
                            "course": f"Course-{idx}",
                            "title": f"Title-{idx}",
                            "details": input_val
                        }
                    ]
                },
                "totals": {"partATotal": 0, "partBTotal": 0, "grandTotal": 0},
            },
            headers=auth_headers,
        )
        assert submit_res.status_code == 200, f"Failed for input: {input_val}. Error: {submit_res.text}"
        
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(CourseFile).where(
                    CourseFile.faculty_email == FACULTY_EMAIL,
                    CourseFile.academic_year == year
                )
            )
            db_rows = res.scalars().all()
            assert len(db_rows) == 1
            assert db_rows[0].details == expected_val

@pytest.mark.asyncio
async def test_course_file_normalization_validation_error(client: AsyncClient, auth_headers: dict):
    submit_res = await client.post(
        "/api/v1/appraisal/submit",
        json={
            "academic_year": YEAR,
            "form": {
                "courseFile": [
                    {
                        "course": "Invalid Course",
                        "title": "Invalid Title",
                        "details": "InvalidValue"
                    }
                ]
            },
            "totals": {"partATotal": 0, "partBTotal": 0, "grandTotal": 0},
        },
        headers=auth_headers,
    )
    assert submit_res.status_code == 400
    assert "Invalid value for course file details" in submit_res.json()["user_message"]
