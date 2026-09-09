"""
Comprehensive tests for Dynamic Schools Catalog (/api/v1/admin/schools and /api/v1/schools).
"""

import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func

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
            "form_variant": "designArts",
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
            "form_variant": "designArts",
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


@pytest.fixture
def superadmin_override():
    async def get_superadmin():
        return User(id="superadmin-test-id", email="superadmin@test.com", roles=["super_admin"])

    app.dependency_overrides[get_current_user] = get_superadmin
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_school_delete_impact(admin_override):
    code = f"SOIMP_{uuid.uuid4().hex[:6]}"
    async with AsyncSessionLocal() as db:
        s = School(code=code, full_name="Impact Test School", track="engineering", approval_chain=["director", "dean", "vc"])
        db.add(s)

        user1 = FacultyProfile(email=f"u1_{code}@test.com", full_name="User 1", school=code)
        user2 = FacultyProfile(email=f"u2_{code}@test.com", full_name="User 2", school=code)
        db.add_all([user1, user2])
        await db.flush()

        dept = Department(name="CSE", school_code=code, created_by=user1.id)
        db.add(dept)

        from src.models.core import Declaration, AppraisalReview, AppraisalDocument, RoleAssignment
        dec = Declaration(faculty_email=f"u1_{code}@test.com", academic_year="2025-2026", grand_total=100)
        rev = AppraisalReview(faculty_email=f"u1_{code}@test.com", academic_year="2025-2026", reviewer_role="director", status="Approved")
        doc = AppraisalDocument(faculty_email=f"u1_{code}@test.com", academic_year="2025-2026", section="Part A", file_name="cert.pdf")
        asg = RoleAssignment(role_type="DIRECTOR", scope_type="school", scope_id=code, user_id=user1.id, academic_year="2025-2026", created_by=user1.id)
        db.add_all([dec, rev, doc, asg])
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/admin/schools/{code}/delete-impact")
        assert resp.status_code == 200
        data = resp.json()
        assert data["school"] == code
        assert data["can_safe_delete"] is False
        assert data["users"] == 2
        assert data["departments"] == 1
        assert data["role_assignments"] >= 1
        assert data["appraisals"] == 1
        assert data["reviews"] == 1
        assert data["documents"] == 1


@pytest.mark.asyncio
async def test_safe_delete_returns_409_with_blocking_counts(admin_override):
    code = f"SO409_{uuid.uuid4().hex[:6]}"
    async with AsyncSessionLocal() as db:
        s = School(code=code, full_name="409 Test School", track="engineering", approval_chain=["director", "dean", "vc"])
        db.add(s)
        user = FacultyProfile(email=f"u_{code}@test.com", full_name="User", school=code)
        db.add(user)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(f"/api/v1/admin/schools/{code}")
        assert resp.status_code == 409
        data = resp.json()
        assert data["can_safe_delete"] is False
        assert data["users"] == 1
        assert "blocking_counts" in data
        assert data["blocking_counts"]["users"] == 1


@pytest.mark.asyncio
async def test_force_delete_forbidden_for_regular_admin(admin_override):
    code = f"SOFORBID_{uuid.uuid4().hex[:6]}"
    async with AsyncSessionLocal() as db:
        s = School(code=code, full_name="Forbidden Force Delete", track="engineering", approval_chain=["director", "dean", "vc"])
        db.add(s)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(f"/api/v1/admin/schools/{code}?force=true")
        assert resp.status_code == 403
        assert "Super admin role required" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_force_delete_success_with_cascades_and_director_preservation(superadmin_override):
    code_a = f"SCH_A_{uuid.uuid4().hex[:6]}"
    code_b = f"SCH_B_{uuid.uuid4().hex[:6]}"

    from src.models.core import Declaration, AppraisalReview, AppraisalDocument, RoleAssignment, ActivityLog
    from src.models.part_a import TeachingProcess

    async with AsyncSessionLocal() as db:
        # Create School A (target) and School B (other)
        s_a = School(code=code_a, full_name="School A Target", track="engineering", approval_chain=["director", "dean", "vc"])
        s_b = School(code=code_b, full_name="School B Other", track="engineering", approval_chain=["director", "dean", "vc"])
        db.add_all([s_a, s_b])

        # Users exclusively in School A
        u_a1 = FacultyProfile(email=f"ua1_{code_a}@test.com", full_name="User A1", school=code_a)
        u_a2 = FacultyProfile(email=f"ua2_{code_a}@test.com", full_name="User A2", school=code_a)

        # Multi-school director assigned to School A and School B
        u_dir = FacultyProfile(email=f"dir_{code_a}@test.com", full_name="Director Multi", school=code_a, appraisal_role="director")

        # System admin whose school is School A
        u_admin = FacultyProfile(email=f"sys_{code_a}@test.com", full_name="System Admin", school=code_a, appraisal_role="admin")

        # User in School B
        u_b = FacultyProfile(email=f"ub_{code_b}@test.com", full_name="User B", school=code_b)

        db.add_all([u_a1, u_a2, u_dir, u_admin, u_b])
        await db.flush()

        dept_a = Department(name="Dept A", school_code=code_a, created_by=u_a1.id)
        dept_b = Department(name="Dept B", school_code=code_b, created_by=u_b.id)
        db.add_all([dept_a, dept_b])
        await db.flush()

        # Director role assignments for School A and School B
        asg_a = RoleAssignment(role_type="DIRECTOR", scope_type="school", scope_id=code_a, user_id=u_dir.id, academic_year="2025-2026", created_by=u_dir.id)
        asg_b = RoleAssignment(role_type="DIRECTOR", scope_type="school", scope_id=code_b, user_id=u_dir.id, academic_year="2025-2026", created_by=u_dir.id)

        # Declarations, reviews, docs, part A items for u_a1
        dec_a = Declaration(faculty_email=u_a1.email, academic_year="2025-2026", grand_total=85)
        rev_a = AppraisalReview(faculty_email=u_a1.email, academic_year="2025-2026", reviewer_role="director", status="Approved")
        doc_a = AppraisalDocument(faculty_email=u_a1.email, academic_year="2025-2026", section="Part A", file_name="a.pdf")
        teach_a = TeachingProcess(faculty_email=u_a1.email, academic_year="2025-2026", planned_classes=40, conducted_classes=40)

        # Records for School B user
        dec_b = Declaration(faculty_email=u_b.email, academic_year="2025-2026", grand_total=90)

        db.add_all([asg_a, asg_b, dec_a, rev_a, doc_a, teach_a, dec_b])
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(f"/api/v1/admin/schools/{code_a}?force=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == f"School '{code_a}' force deleted successfully"
        assert data["school"] == code_a
        assert "deleted" in data
        assert data["deleted"]["users"] == 2  # u_a1, u_a2 (u_dir and u_admin preserved)
        assert data["deleted"]["departments"] == 1
        assert data["deleted"]["appraisals"] >= 1
        assert data["deleted"]["documents"] >= 1

    # Verify database state after force delete
    async with AsyncSessionLocal() as db:
        # 1. School A is deleted
        res_sa = await db.execute(select(School).where(School.code == code_a))
        assert res_sa.scalar_one_or_none() is None

        # 2. School B is intact
        res_sb = await db.execute(select(School).where(School.code == code_b))
        assert res_sb.scalar_one_or_none() is not None

        # 3. u_a1 and u_a2 are deleted
        res_ua1 = await db.execute(select(FacultyProfile).where(func.lower(FacultyProfile.email) == f"ua1_{code_a}@test.com".lower()))
        assert res_ua1.scalar_one_or_none() is None

        # 4. Multi-school Director is preserved, primary school updated to code_b
        res_dir = await db.execute(select(FacultyProfile).where(func.lower(FacultyProfile.email) == f"dir_{code_a}@test.com".lower()))
        dir_prof = res_dir.scalar_one_or_none()
        assert dir_prof is not None
        assert dir_prof.school == code_b

        # 5. Director role assignment for School A is deleted, School B is active
        res_asg_a = await db.execute(select(RoleAssignment).where(func.lower(RoleAssignment.scope_id) == code_a.lower()))
        assert res_asg_a.scalar_one_or_none() is None
        res_asg_b = await db.execute(select(RoleAssignment).where(func.lower(RoleAssignment.scope_id) == code_b.lower()))
        assert res_asg_b.scalar_one_or_none() is not None

        # 6. System admin user is preserved, detached from School A
        res_admin = await db.execute(select(FacultyProfile).where(func.lower(FacultyProfile.email) == f"sys_{code_a}@test.com".lower()))
        admin_prof = res_admin.scalar_one_or_none()
        assert admin_prof is not None
        assert admin_prof.school is None

        # 7. School B user & declaration are intact
        res_ub = await db.execute(select(FacultyProfile).where(func.lower(FacultyProfile.email) == f"ub_{code_b}@test.com".lower()))
        assert res_ub.scalar_one_or_none() is not None
        res_dec_b = await db.execute(select(Declaration).where(func.lower(Declaration.faculty_email) == f"ub_{code_b}@test.com".lower()))
        assert res_dec_b.scalar_one_or_none() is not None

        # 8. Activity log recorded
        res_log = await db.execute(select(ActivityLog).where(ActivityLog.type == "school_force_delete"))
        logs = res_log.scalars().all()
        matching_log = [l for l in logs if l.meta.get("school_code") == code_a]
        assert len(matching_log) == 1
        assert matching_log[0].meta["action"] == "school_force_delete"

