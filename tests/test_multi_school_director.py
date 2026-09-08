"""
Test Suite: Multi-School Director Assignments and Authorization.
Validates:
- Test A: Director with two schools sees both
- Test B: Director cannot see unassigned school
- Test C: Director can review both assigned schools
- Test D: Director cannot review when chain omits director
- Test E: Manage Program / Department multi-school
- Test F: Backward compatibility (Director without RoleAssignment uses profile.school)
- Test G: CISR isolation from Director
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from uuid import UUID
import uuid

from src.main import app
from src.setup.database import AsyncSessionLocal
from src.models.core import School, FacultyProfile, RoleAssignment
from src.setup.local_auth import get_password_hash
from src.setup.dependencies import normalize_school, User, get_current_user

YEAR = "2025-2026"
PASSWORD = "testpassword123"

SUBMIT_PAYLOAD = {
    "academic_year": YEAR,
    "form": {
        "lectures": [
            {
                "semester": "Sem 1",
                "course_code": "CSE101",
                "planned_classes": 40,
                "conducted_classes": 40,
            }
        ],
    },
    "totals": {"partATotal": 50, "partBTotal": 50, "grandTotal": 100},
}

REVIEW_PAYLOAD = {
    "academic_year": YEAR,
    "remarks": "Approved by Director",
    "part_a_score": 45,
    "part_b_score": 45,
    "total_score": 90,
}


async def _seed_school(code: str, full_name: str, has_hod: bool, has_director: bool, approval_chain: list, depts: list = None):
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(School).where(School.code == code))
        s = res.scalar_one_or_none()
        if not s:
            s = School(
                code=code,
                full_name=full_name,
                track="engineering",
                has_hod=has_hod,
                has_director=has_director,
                approval_chain=approval_chain,
                departments=depts or ["General"],
                default_form="standard",
                active=True,
                order=1,
            )
            db.add(s)
        else:
            s.full_name = full_name
            s.has_hod = has_hod
            s.has_director = has_director
            s.approval_chain = approval_chain
            s.departments = depts or ["General"]
            s.active = True
        await db.commit()


async def _seed_faculty(email: str, full_name: str, role: str, school: str, dept: str = "General"):
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == email))
        fac = res.scalar_one_or_none()
        if not fac:
            fac = FacultyProfile(
                email=email,
                password_hash=get_password_hash(PASSWORD),
                full_name=full_name,
                appraisal_role=role,
                school=school,
                department=dept,
                is_verified=True,
                is_active=True,
            )
            db.add(fac)
        else:
            fac.full_name = full_name
            fac.appraisal_role = role
            fac.school = school
            fac.department = dept
            fac.is_active = True
        await db.commit()
        await db.refresh(fac)
        return fac


async def _assign_role(user_id: UUID, role_type: str, scope_type: str, scope_id: str, academic_year: str = YEAR, created_by: UUID = None):
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(RoleAssignment).where(
                RoleAssignment.user_id == user_id,
                RoleAssignment.role_type == role_type,
                RoleAssignment.scope_type == scope_type,
                RoleAssignment.scope_id == scope_id,
                RoleAssignment.academic_year == academic_year,
                RoleAssignment.status == "active",
            )
        )
        asg = res.scalar_one_or_none()
        if not asg:
            asg = RoleAssignment(
                id=uuid.uuid4(),
                user_id=user_id,
                role_type=role_type,
                scope_type=scope_type,
                scope_id=scope_id,
                academic_year=academic_year,
                status="active",
                created_by=created_by or user_id,
            )
            db.add(asg)
            await db.commit()
            await db.refresh(asg)
        return asg


@pytest.mark.asyncio
async def test_a_director_with_two_schools_sees_both():
    """Test A: Director with two schools sees both in dashboard."""
    await _seed_school("DIR_SCH_A", "School A", False, True, ["director", "dean", "vc"])
    await _seed_school("DIR_SCH_B", "School B", False, True, ["director", "dean", "vc"])

    director = await _seed_faculty("multi_director_a@test.com", "Multi Director", "director", "DIR_SCH_A")
    await _assign_role(director.id, "DIRECTOR", "school", "DIR_SCH_A")
    await _assign_role(director.id, "DIRECTOR", "school", "DIR_SCH_B")

    fac_a = await _seed_faculty("fac_dir_a@test.com", "Faculty A", "faculty", "DIR_SCH_A")
    fac_b = await _seed_faculty("fac_dir_b@test.com", "Faculty B", "faculty", "DIR_SCH_B")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Faculty A submits
        app.dependency_overrides[get_current_user] = lambda: User(
            id=str(fac_a.id), email=fac_a.email, roles=["faculty"], school="DIR_SCH_A"
        )
        res_sub_a = await client.post("/api/v1/appraisal/submit", json=SUBMIT_PAYLOAD)
        assert res_sub_a.status_code == 200

        # Faculty B submits
        app.dependency_overrides[get_current_user] = lambda: User(
            id=str(fac_b.id), email=fac_b.email, roles=["faculty"], school="DIR_SCH_B"
        )
        res_sub_b = await client.post("/api/v1/appraisal/submit", json=SUBMIT_PAYLOAD)
        assert res_sub_b.status_code == 200

        # Login as Director to verify JWT token creation and get_current_user
        app.dependency_overrides.pop(get_current_user, None)
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "multi_director_a@test.com", "password": PASSWORD}
        )
        assert login_res.status_code == 200
        token = login_res.json()["token"]
        schools = login_res.json()["profile"]["schools"]
        assert "DIR_SCH_A" in schools
        assert "DIR_SCH_B" in schools

        # Query subordinates
        headers = {"Authorization": f"Bearer {token}"}
        sub_res = await client.get(f"/api/v1/dashboard/subordinates?academic_year={YEAR}", headers=headers)
        assert sub_res.status_code == 200
        sub_emails = [s["email"] for s in sub_res.json()]
        assert "fac_dir_a@test.com" in sub_emails
        assert "fac_dir_b@test.com" in sub_emails


@pytest.mark.asyncio
async def test_b_director_cannot_see_unassigned_school():
    """Test B: Director cannot see unassigned school or its faculty."""
    await _seed_school("DIR_SCH_C", "School C", False, True, ["director", "dean", "vc"])
    fac_c = await _seed_faculty("fac_dir_c@test.com", "Faculty C", "faculty", "DIR_SCH_C")

    director = await _seed_faculty("multi_director_b@test.com", "Multi Director B", "director", "DIR_SCH_A")
    await _assign_role(director.id, "DIRECTOR", "school", "DIR_SCH_A")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Faculty C submits
        app.dependency_overrides[get_current_user] = lambda: User(
            id=str(fac_c.id), email=fac_c.email, roles=["faculty"], school="DIR_SCH_C"
        )
        res_sub_c = await client.post("/api/v1/appraisal/submit", json=SUBMIT_PAYLOAD)
        assert res_sub_c.status_code == 200

        # Login as Director B
        app.dependency_overrides.pop(get_current_user, None)
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "multi_director_b@test.com", "password": PASSWORD}
        )
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Subordinates does not contain fac_dir_c
        sub_res = await client.get(f"/api/v1/dashboard/subordinates?academic_year={YEAR}", headers=headers)
        assert sub_res.status_code == 200
        sub_emails = [s["email"] for s in sub_res.json()]
        assert "fac_dir_c@test.com" not in sub_emails

        # 2. Passing reviewer_school=DIR_SCH_C returns 403 Forbidden
        filter_res = await client.get(
            f"/api/v1/dashboard/subordinates?academic_year={YEAR}&reviewer_school=DIR_SCH_C",
            headers=headers
        )
        assert filter_res.status_code == 403

        # 3. Accessing snapshot for fac_dir_c returns 403 Forbidden
        snap_res = await client.get(
            f"/api/v1/dashboard/faculty/fac_dir_c@test.com?academic_year={YEAR}",
            headers=headers
        )
        assert snap_res.status_code == 403


@pytest.mark.asyncio
async def test_c_director_can_review_both_assigned_schools():
    """Test C: Director can successfully review submissions across multiple assigned schools."""
    director = await _seed_faculty("multi_director_c@test.com", "Multi Director C", "director", "DIR_SCH_A")
    await _assign_role(director.id, "DIRECTOR", "school", "DIR_SCH_A")
    await _assign_role(director.id, "DIRECTOR", "school", "DIR_SCH_B")

    fac_a = await _seed_faculty("fac_review_a@test.com", "Faculty Review A", "faculty", "DIR_SCH_A")
    fac_b = await _seed_faculty("fac_review_b@test.com", "Faculty Review B", "faculty", "DIR_SCH_B")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Faculty A submits
        app.dependency_overrides[get_current_user] = lambda: User(
            id=str(fac_a.id), email=fac_a.email, roles=["faculty"], school="DIR_SCH_A"
        )
        res_a = await client.post("/api/v1/appraisal/submit", json=SUBMIT_PAYLOAD)
        assert res_a.status_code == 200

        # Faculty B submits
        app.dependency_overrides[get_current_user] = lambda: User(
            id=str(fac_b.id), email=fac_b.email, roles=["faculty"], school="DIR_SCH_B"
        )
        res_b = await client.post("/api/v1/appraisal/submit", json=SUBMIT_PAYLOAD)
        assert res_b.status_code == 200

        # Login Director C
        app.dependency_overrides.pop(get_current_user, None)
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "multi_director_c@test.com", "password": PASSWORD}
        )
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Director reviews Faculty A
        rev_a = await client.put(
            f"/api/v1/appraisal-remarks/director/{fac_a.email}",
            json=REVIEW_PAYLOAD,
            headers=headers
        )
        assert rev_a.status_code == 200
        assert rev_a.json()["next_reviewer"] == "dean"

        # Director reviews Faculty B
        rev_b = await client.put(
            f"/api/v1/appraisal-remarks/director/{fac_b.email}",
            json=REVIEW_PAYLOAD,
            headers=headers
        )
        assert rev_b.status_code == 200
        assert rev_b.json()["next_reviewer"] == "dean"


@pytest.mark.asyncio
async def test_d_director_cannot_review_when_chain_omits_director():
    """Test D: Director cannot review when school approval chain omits director."""
    await _seed_school("DIR_SCH_D", "School D (No Director)", False, False, ["dean", "vc"])
    fac_d = await _seed_faculty("fac_dir_d@test.com", "Faculty D", "faculty", "DIR_SCH_D")

    director = await _seed_faculty("multi_director_d@test.com", "Multi Director D", "director", "DIR_SCH_D")
    await _assign_role(director.id, "DIRECTOR", "school", "DIR_SCH_D")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Faculty D submits
        app.dependency_overrides[get_current_user] = lambda: User(
            id=str(fac_d.id), email=fac_d.email, roles=["faculty"], school="DIR_SCH_D"
        )
        res_d = await client.post("/api/v1/appraisal/submit", json=SUBMIT_PAYLOAD)
        assert res_d.status_code == 200

        # Login Director D
        app.dependency_overrides.pop(get_current_user, None)
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "multi_director_d@test.com", "password": PASSWORD}
        )
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Director attempts review on DIR_SCH_D -> MUST return 403 Forbidden
        rev_d = await client.put(
            f"/api/v1/appraisal-remarks/director/{fac_d.email}",
            json=REVIEW_PAYLOAD,
            headers=headers
        )
        assert rev_d.status_code == 403


@pytest.mark.asyncio
async def test_e_manage_program_multi_school():
    """Test E: Director assigned to multiple schools can manage departments/faculty for both, but not unassigned."""
    director = await _seed_faculty("multi_director_e@test.com", "Multi Director E", "director", "DIR_SCH_A")
    await _assign_role(director.id, "DIRECTOR", "school", "DIR_SCH_A")
    await _assign_role(director.id, "DIRECTOR", "school", "DIR_SCH_B")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app.dependency_overrides.pop(get_current_user, None)
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "multi_director_e@test.com", "password": PASSWORD}
        )
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create department in SCHOOL_A -> 200
        dept_a_res = await client.post(
            "/api/v1/schools/DIR_SCH_A/departments",
            json={"name": f"Dept A {uuid.uuid4().hex[:6]}"},
            headers=headers
        )
        assert dept_a_res.status_code == 200

        # 2. Create department in SCHOOL_B -> 200
        dept_b_res = await client.post(
            "/api/v1/schools/DIR_SCH_B/departments",
            json={"name": f"Dept B {uuid.uuid4().hex[:6]}"},
            headers=headers
        )
        assert dept_b_res.status_code == 200

        # 3. Create department in unassigned SCHOOL_C -> 403
        dept_c_res = await client.post(
            "/api/v1/schools/DIR_SCH_C/departments",
            json={"name": f"Dept C {uuid.uuid4().hex[:6]}"},
            headers=headers
        )
        assert dept_c_res.status_code == 403

        # 4. List faculty for SCHOOL_A and SCHOOL_B -> 200
        fac_list_a = await client.get("/api/v1/schools/DIR_SCH_A/faculty", headers=headers)
        assert fac_list_a.status_code == 200
        fac_list_b = await client.get("/api/v1/schools/DIR_SCH_B/faculty", headers=headers)
        assert fac_list_b.status_code == 200

        # 5. List faculty for unassigned SCHOOL_C -> 403
        fac_list_c = await client.get("/api/v1/schools/DIR_SCH_C/faculty", headers=headers)
        assert fac_list_c.status_code == 403


@pytest.mark.asyncio
async def test_f_backward_compatibility_single_school_director():
    """Test F: Director with no RoleAssignment records still works via profile.school."""
    director = await _seed_faculty("single_director_f@test.com", "Single Director F", "director", "DIR_SCH_A")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app.dependency_overrides.pop(get_current_user, None)
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "single_director_f@test.com", "password": PASSWORD}
        )
        assert login_res.status_code == 200
        assert login_res.json()["profile"]["schools"] == ["DIR_SCH_A"]
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Can see DIR_SCH_A subordinates
        sub_res = await client.get(f"/api/v1/dashboard/subordinates?academic_year={YEAR}", headers=headers)
        assert sub_res.status_code == 200


@pytest.mark.asyncio
async def test_g_cisr_isolation_from_director():
    """Test G: CISR faculty are never visible to Director accounts."""
    await _seed_school("CISR", "Center for Interdisciplinary Scientific Research", False, False, ["center_head", "vc"])
    fac_cisr = await _seed_faculty("fac_cisr_test@test.com", "Faculty CISR", "faculty", "CISR")

    director = await _seed_faculty("multi_director_cisr@test.com", "Multi Director CISR", "director", "DIR_SCH_A")
    await _assign_role(director.id, "DIRECTOR", "school", "DIR_SCH_A")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # CISR submits
        app.dependency_overrides[get_current_user] = lambda: User(
            id=str(fac_cisr.id), email=fac_cisr.email, roles=["faculty"], school="CISR"
        )
        sub_res = await client.post("/api/v1/appraisal/submit", json=SUBMIT_PAYLOAD)
        assert sub_res.status_code == 200

        # Login Director
        app.dependency_overrides.pop(get_current_user, None)
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "multi_director_cisr@test.com", "password": PASSWORD}
        )
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Director subordinates query must not contain CISR
        dash_res = await client.get(f"/api/v1/dashboard/subordinates?academic_year={YEAR}", headers=headers)
        assert dash_res.status_code == 200
        dash_emails = [s["email"] for s in dash_res.json()]
        assert "fac_cisr_test@test.com" not in dash_emails

        # Director direct access to CISR faculty snapshot returns 403
        snap_res = await client.get(
            f"/api/v1/dashboard/faculty/fac_cisr_test@test.com?academic_year={YEAR}",
            headers=headers
        )
        assert snap_res.status_code == 403
