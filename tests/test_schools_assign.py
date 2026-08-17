import pytest
from httpx import AsyncClient
from sqlalchemy import select
import uuid
from uuid import UUID

from src.setup.database import AsyncSessionLocal
from src.models.core import FacultyProfile, Department
from src.setup.local_auth import get_password_hash

PASSWORD = "testpassword123"

async def _seed_user(email: str, role: str, school: str, department: str = None, is_active: bool = True):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FacultyProfile).where(FacultyProfile.email == email)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            profile = FacultyProfile(
                email=email,
                password_hash=get_password_hash(PASSWORD),
                full_name=f"Test {role.capitalize()}",
                appraisal_role=role,
                school=school,
                department=department,
                is_verified=True,
                is_active=is_active
            )
            db.add(profile)
            await db.commit()
            await db.refresh(profile)
        return profile

async def _seed_department(name: str, school_code: str, created_by_id: UUID):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Department).where(Department.name == name, Department.school_code == school_code)
        )
        dept = result.scalar_one_or_none()
        if not dept:
            dept = Department(
                id=uuid.uuid4(),
                school_code=school_code,
                name=name,
                status="active",
                created_by=created_by_id
            )
            db.add(dept)
            await db.commit()
            await db.refresh(dept)
        return dept

@pytest.fixture
async def director_headers(client: AsyncClient):
    director = await _seed_user("director_socsea@test.com", "director", "SoCSEA")
    await _seed_department("B.Tech Computer Science", "SoCSEA", director.id)
    login = await client.post(
        "/api/v1/auth/login", json={"email": "director_socsea@test.com", "password": PASSWORD}
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}

@pytest.fixture
async def other_director_headers(client: AsyncClient):
    director = await _seed_user("director_sobb@test.com", "director", "SoBB")
    await _seed_department("B.Tech Biotechnology", "SoBB", director.id)
    login = await client.post(
        "/api/v1/auth/login", json={"email": "director_sobb@test.com", "password": PASSWORD}
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}

@pytest.fixture
async def faculty_headers(client: AsyncClient):
    await _seed_user("faculty_socsea@test.com", "faculty", "SoCSEA")
    login = await client.post(
        "/api/v1/auth/login", json={"email": "faculty_socsea@test.com", "password": PASSWORD}
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}

@pytest.fixture
async def admin_headers(client: AsyncClient):
    await _seed_user("admin_user@test.com", "admin", "SoCSEA")
    login = await client.post(
        "/api/v1/auth/login", json={"email": "admin_user@test.com", "password": PASSWORD}
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}

@pytest.fixture
async def vc_headers(client: AsyncClient):
    await _seed_user("vc_user@test.com", "vc", "SoCSEA")
    login = await client.post(
        "/api/v1/auth/login", json={"email": "vc_user@test.com", "password": PASSWORD}
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}


# ── GET /schools/{school_code}/faculty Tests ──────────────────────────────────

@pytest.mark.asyncio
async def test_get_school_faculty_auth_success(client, director_headers, admin_headers, vc_headers):
    # Seed some faculty in SoCSEA
    await _seed_user("f1@test.com", "faculty", "SoCSEA")
    await _seed_user("f2@test.com", "faculty", "SoCSEA")
    # Seed a faculty in another school (should not be returned)
    await _seed_user("f3@test.com", "faculty", "SoBB")
    # Seed an HOD in SoCSEA (should not be returned)
    await _seed_user("hod1@test.com", "hod", "SoCSEA")

    # Check SoCSEA director access
    resp = await client.get("/api/v2/schools/SoCSEA/faculty", headers=director_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    emails = [f["email"] for f in data]
    assert "f1@test.com" in emails
    assert "f2@test.com" in emails
    assert "f3@test.com" not in emails
    assert "hod1@test.com" not in emails

    # Check Admin access
    resp_admin = await client.get("/api/v2/schools/SoCSEA/faculty", headers=admin_headers)
    assert resp_admin.status_code == 200

    # Check VC access
    resp_vc = await client.get("/api/v2/schools/SoCSEA/faculty", headers=vc_headers)
    assert resp_vc.status_code == 200

@pytest.mark.asyncio
async def test_get_school_faculty_auth_forbidden(client, other_director_headers, faculty_headers):
    # Other director cannot query SoCSEA faculty
    resp = await client.get("/api/v2/schools/SoCSEA/faculty", headers=other_director_headers)
    assert resp.status_code == 403

    # Faculty cannot query SoCSEA faculty
    resp2 = await client.get("/api/v2/schools/SoCSEA/faculty", headers=faculty_headers)
    assert resp2.status_code == 403

@pytest.mark.asyncio
async def test_get_school_faculty_empty(client, director_headers):
    # Query a school with no faculty (SoD)
    resp = await client.get("/api/v2/schools/SoD/faculty", headers=director_headers)
    # The director of SoCSEA is not director of SoD, so expect 403
    assert resp.status_code == 403

# ── POST /schools/{school_code}/faculty/{email}/assign Tests ─────────────────

@pytest.mark.asyncio
async def test_assign_faculty_success(client, director_headers):
    # Seed target faculty in SoCSEA
    faculty = await _seed_user("target_fac@test.com", "faculty", "SoCSEA")
    assert faculty.department is None

    # Assign program
    resp = await client.post(
        "/api/v2/schools/SoCSEA/faculty/target_fac@test.com/assign",
        json={"department": "B.Tech Computer Science"},
        headers=director_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "target_fac@test.com"
    assert data["department"] == "B.Tech Computer Science"

    # Verify database update
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(FacultyProfile).where(FacultyProfile.email == "target_fac@test.com")
        )
        updated = res.scalar_one()
        assert updated.department == "B.Tech Computer Science"

@pytest.mark.asyncio
async def test_assign_faculty_validation_department(client, director_headers):
    # Seed target faculty
    await _seed_user("target_fac_val@test.com", "faculty", "SoCSEA")

    # Nonexistent program name should fail with 404 Program not found
    resp = await client.post(
        "/api/v2/schools/SoCSEA/faculty/target_fac_val@test.com/assign",
        json={"department": "Nonexistent Program"},
        headers=director_headers
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Program not found"

    # Department from a different school should fail with 404 Program not found
    resp2 = await client.post(
        "/api/v2/schools/SoCSEA/faculty/target_fac_val@test.com/assign",
        json={"department": "B.Tech Biotechnology"},  # exists in SoBB
        headers=director_headers
    )
    assert resp2.status_code == 404
    assert resp2.json()["detail"] == "Program not found"

@pytest.mark.asyncio
async def test_assign_faculty_validation_target_user(client, director_headers):
    # Nonexistent target faculty should fail with 404 Faculty account not found
    resp1 = await client.post(
        "/api/v2/schools/SoCSEA/faculty/nonexistent@test.com/assign",
        json={"department": "B.Tech Computer Science"},
        headers=director_headers
    )
    assert resp1.status_code == 404
    assert resp1.json()["detail"] == "Faculty account not found"

    # Inactive target faculty should fail with 404 Faculty account not found
    await _seed_user("inactive_fac@test.com", "faculty", "SoCSEA", is_active=False)
    resp2 = await client.post(
        "/api/v2/schools/SoCSEA/faculty/inactive_fac@test.com/assign",
        json={"department": "B.Tech Computer Science"},
        headers=director_headers
    )
    assert resp2.status_code == 404
    assert resp2.json()["detail"] == "Faculty account not found"

    # Target user with non-faculty role (e.g. hod) should fail with 400 Not a faculty account in this school
    await _seed_user("hod_target@test.com", "hod", "SoCSEA")
    resp3 = await client.post(
        "/api/v2/schools/SoCSEA/faculty/hod_target@test.com/assign",
        json={"department": "B.Tech Computer Science"},
        headers=director_headers
    )
    assert resp3.status_code == 400
    assert resp3.json()["detail"] == "Not a faculty account in this school"

    # Target user from a different school should fail with 400 Not a faculty account in this school
    await _seed_user("faculty_sobb@test.com", "faculty", "SoBB")
    resp4 = await client.post(
        "/api/v2/schools/SoCSEA/faculty/faculty_sobb@test.com/assign",
        json={"department": "B.Tech Computer Science"},
        headers=director_headers
    )
    assert resp4.status_code == 400
    assert resp4.json()["detail"] == "Not a faculty account in this school"

@pytest.mark.asyncio
async def test_assign_faculty_auth_forbidden(client, other_director_headers, faculty_headers, admin_headers, vc_headers):
    await _seed_user("target_auth@test.com", "faculty", "SoCSEA")

    # Other director cannot assign SoCSEA faculty program
    resp = await client.post(
        "/api/v2/schools/SoCSEA/faculty/target_auth@test.com/assign",
        json={"department": "B.Tech Computer Science"},
        headers=other_director_headers
    )
    assert resp.status_code == 403

    # Faculty cannot assign program
    resp2 = await client.post(
        "/api/v2/schools/SoCSEA/faculty/target_auth@test.com/assign",
        json={"department": "B.Tech Computer Science"},
        headers=faculty_headers
    )
    assert resp2.status_code == 403

    # Admin cannot assign program (strict auth per Notepad spec)
    resp3 = await client.post(
        "/api/v2/schools/SoCSEA/faculty/target_auth@test.com/assign",
        json={"department": "B.Tech Computer Science"},
        headers=admin_headers
    )
    assert resp3.status_code == 403

    # VC cannot assign program (strict auth per Notepad spec)
    resp4 = await client.post(
        "/api/v2/schools/SoCSEA/faculty/target_auth@test.com/assign",
        json={"department": "B.Tech Computer Science"},
        headers=vc_headers
    )
    assert resp4.status_code == 403
