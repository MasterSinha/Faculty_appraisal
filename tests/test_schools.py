"""
Comprehensive tests for Dynamic Schools Catalog (/api/v1/admin/schools and /api/v1/schools).
"""

import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from src.main import app
from src.setup.database import AsyncSessionLocal
from src.setup.dependencies import User, get_current_user
from src.models.core import School, FacultyProfile, Department


@pytest.fixture
def admin_override():
    async def get_admin():
        return User(id="admin-test-id", email="sysadmin@test.com", roles=["admin"])

    app.dependency_overrides[get_current_user] = get_admin
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def nonadmin_override():
    async def get_nonadmin():
        return User(id="user-test-id", email="regular@test.com", roles=["faculty"])

    app.dependency_overrides[get_current_user] = get_nonadmin
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_schools_admin_and_non_admin(admin_override, nonadmin_override):
    # Seed a school
    async with AsyncSessionLocal() as db:
        s = School(
            code="TEST_SOCSEA",
            full_name="Test School of Computer Science",
            track="engineering",
            has_hod=False,
            has_director=True,
            approval_chain=["director", "dean", "vc"],
            default_form="standard",
            active=True,
            order=1,
        )
        db.add(s)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Non-admin / public catalog path
        resp = await client.get("/api/v1/schools")
        assert resp.status_code == 200
        data = resp.json()
        assert any(item["code"] == "TEST_SOCSEA" for item in data)

        # Admin endpoint with non-admin auth should also succeed for reading
        resp_admin_read = await client.get("/api/v1/admin/schools")
        assert resp_admin_read.status_code == 200


@pytest.mark.asyncio
async def test_create_school_success(admin_override):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "code": "SoTest",
            "full_name": "School of Testing",
            "track": "engineering",
            "has_hod": True,
            "has_director": True,
            "approval_chain": ["hod", "director", "dean", "vc"],
            "departments": ["QA", "DevOps"],
            "default_form": "standard",
            "active": True,
            "order": 5,
        }
        resp = await client.post("/api/v1/admin/schools", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["code"] == "SoTest"
        assert data["full_name"] == "School of Testing"
        assert data["track"] == "engineering"
        assert data["has_hod"] is True
        assert data["has_director"] is True
        assert data["approval_chain"] == ["hod", "director", "dean", "vc"]
        assert data["departments"] == ["QA", "DevOps"]
        assert data["default_form"] == "standard"
        assert data["active"] is True


@pytest.mark.asyncio
async def test_create_school_case_insensitive_duplicate(admin_override):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create 'SOD1'
        payload = {
            "code": "SOD1",
            "full_name": "School of Design 1",
            "track": "non_engineering",
            "has_hod": False,
            "has_director": True,
            "approval_chain": ["director", "dean", "vc"],
            "default_form": "creative",
        }
        resp1 = await client.post("/api/v1/admin/schools", json=payload)
        assert resp1.status_code == 201

        # Attempt to create 'sod1' differing only by case
        payload2 = {
            "code": "sod1",
            "full_name": "Duplicate School of Design",
            "track": "non_engineering",
            "has_hod": False,
            "has_director": True,
            "approval_chain": ["director", "dean", "vc"],
            "default_form": "creative",
        }
        resp2 = await client.post("/api/v1/admin/schools", json=payload2)
        assert resp2.status_code == 400
        assert "already exists" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_create_school_validation_chain_ending_vc(admin_override):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "code": "SoInvalidChain",
            "full_name": "School with invalid chain",
            "track": "engineering",
            "has_hod": False,
            "has_director": True,
            "approval_chain": ["director", "dean"],  # Missing vc
        }
        resp = await client.post("/api/v1/admin/schools", json=payload)
        assert resp.status_code == 400
        assert "vc" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_school_validation_has_hod_bidirectional(admin_override):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # has_hod is True but "hod" missing from chain
        payload1 = {
            "code": "SoHodMissing",
            "full_name": "School missing hod step",
            "track": "engineering",
            "has_hod": True,
            "has_director": True,
            "approval_chain": ["director", "dean", "vc"],
        }
        resp1 = await client.post("/api/v1/admin/schools", json=payload1)
        assert resp1.status_code == 400
        assert "has_hod" in resp1.json()["detail"]

        # has_hod is False but "hod" present in chain
        payload2 = {
            "code": "SoHodExtra",
            "full_name": "School extra hod step",
            "track": "engineering",
            "has_hod": False,
            "has_director": True,
            "approval_chain": ["hod", "director", "dean", "vc"],
        }
        resp2 = await client.post("/api/v1/admin/schools", json=payload2)
        assert resp2.status_code == 400
        assert "has_hod" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_create_school_validation_has_director_bidirectional(admin_override):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # has_director is True but "director" missing from chain
        payload1 = {
            "code": "SoDirMissing",
            "full_name": "School missing director step",
            "track": "engineering",
            "has_hod": False,
            "has_director": True,
            "approval_chain": ["dean", "vc"],
        }
        resp1 = await client.post("/api/v1/admin/schools", json=payload1)
        assert resp1.status_code == 400
        assert "has_director" in resp1.json()["detail"]

        # has_director is False but "director" present in chain
        payload2 = {
            "code": "SoDirExtra",
            "full_name": "School extra director step",
            "track": "engineering",
            "has_hod": False,
            "has_director": False,
            "approval_chain": ["director", "dean", "vc"],
        }
        resp2 = await client.post("/api/v1/admin/schools", json=payload2)
        assert resp2.status_code == 400
        assert "has_director" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_create_school_validation_invalid_track_and_form(admin_override):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Invalid track
        resp_track = await client.post(
            "/api/v1/admin/schools",
            json={
                "code": "SoBadTrack",
                "full_name": "Bad Track School",
                "track": "magic",
                "has_hod": False,
                "has_director": True,
                "approval_chain": ["director", "dean", "vc"],
            },
        )
        assert resp_track.status_code == 400

        # Invalid default_form
        resp_form = await client.post(
            "/api/v1/admin/schools",
            json={
                "code": "SoBadForm",
                "full_name": "Bad Form School",
                "track": "engineering",
                "has_hod": False,
                "has_director": True,
                "approval_chain": ["director", "dean", "vc"],
                "default_form": "unknown_form",
            },
        )
        assert resp_form.status_code == 400


@pytest.mark.asyncio
async def test_put_school_and_deactivation_with_faculty_references(admin_override):
    code = f"SODEACT_{uuid.uuid4().hex[:6]}"
    async with AsyncSessionLocal() as db:
        s = School(
            code=code,
            full_name="Deactivation Test School",
            track="engineering",
            has_hod=False,
            has_director=True,
            approval_chain=["director", "dean", "vc"],
            default_form="standard",
            active=True,
        )
        db.add(s)

        # Faculty profile referencing this school
        f = FacultyProfile(
            email=f"fac_{code}@test.com",
            full_name="Prof Test",
            school=code,
            appraisal_role="faculty",
        )
        db.add(f)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Updating active: false MUST SUCCEED even when faculty reference this school
        resp = await client.put(
            f"/api/v1/admin/schools/{code}",
            json={"active": False, "full_name": "Updated School Name"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False
        assert data["full_name"] == "Updated School Name"


@pytest.mark.asyncio
async def test_delete_school_blocked_by_faculty_or_department_references(admin_override):
    code_user = f"SOUSER_{uuid.uuid4().hex[:6]}"
    code_dept = f"SODEPT_{uuid.uuid4().hex[:6]}"
    code_clean = f"SOCLEAN_{uuid.uuid4().hex[:6]}"

    async with AsyncSessionLocal() as db:
        s1 = School(code=code_user, full_name="User Ref School", track="engineering", approval_chain=["director", "dean", "vc"])
        s2 = School(code=code_dept, full_name="Dept Ref School", track="engineering", approval_chain=["director", "dean", "vc"])
        s3 = School(code=code_clean, full_name="Clean School", track="engineering", approval_chain=["director", "dean", "vc"])
        db.add_all([s1, s2, s3])

        # Add faculty referencing s1
        user1 = FacultyProfile(email=f"u1_{code_user}@test.com", full_name="User 1", school=code_user)
        user_admin = FacultyProfile(email=f"admin_{code_dept}@test.com", full_name="Admin 1", school="ADMIN_DEPT")
        db.add_all([user1, user_admin])
        await db.flush()

        # Add department referencing s2
        dept = Department(name="Computer Engg", school_code=code_dept, created_by=user_admin.id)
        db.add(dept)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Deleting s1 should fail with 409 Conflict due to user reference
        resp1 = await client.delete(f"/api/v1/admin/schools/{code_user}")
        assert resp1.status_code == 409
        assert "faculty or users currently reference it" in resp1.json()["detail"]

        # Deleting s2 should fail with 409 Conflict due to dept reference
        resp2 = await client.delete(f"/api/v1/admin/schools/{code_dept}")
        assert resp2.status_code == 409
        assert "departments currently reference it" in resp2.json()["detail"]

        # Deleting s3 should succeed with 200
        resp3 = await client.delete(f"/api/v1/admin/schools/{code_clean}")
        assert resp3.status_code == 200
        assert resp3.json()["code"] == code_clean

        # Verify s3 is deleted
        resp_check = await client.delete(f"/api/v1/admin/schools/{code_clean}")
        assert resp_check.status_code == 404
