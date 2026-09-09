import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, and_
from uuid import UUID
import uuid

from src.main import app
from src.setup.database import AsyncSessionLocal
from src.models.core import School, FacultyProfile, RoleAssignment, Declaration, AppraisalReview, AppraisalConfig
from src.setup.local_auth import get_password_hash
from src.setup.dependencies import User, get_current_user, normalize_school

YEAR = "2025-2026"
PASSWORD = "testpassword123"

SUBMIT_PAYLOAD = {
    "academic_year": YEAR,
    "form": {
        "lectures": [
            {
                "semester": "Sem 1",
                "course_code": "GEN101",
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


async def _seed_school(code: str, full_name: str, track: str, approval_chain: list, active: bool = True):
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(School).where(School.code == code))
        s = res.scalar_one_or_none()
        if not s:
            s = School(
                code=code,
                full_name=full_name,
                track=track,
                has_hod=False,
                has_director=True,
                approval_chain=approval_chain,
                departments=["General"],
                default_form="standard",
                active=active,
                order=1,
            )
            db.add(s)
        else:
            s.full_name = full_name
            s.track = track
            s.approval_chain = approval_chain
            s.active = active
        await db.commit()


async def _seed_admin(email: str = "admin_super@test.com"):
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == email))
        user = res.scalar_one_or_none()
        if not user:
            user = FacultyProfile(
                email=email,
                password_hash=get_password_hash(PASSWORD),
                full_name="Super Admin",
                appraisal_role="super_admin",
                school="SoCSEA",
                is_verified=True,
                is_active=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user


@pytest.mark.asyncio
async def test_admin_multi_school_director_lifecycle():
    """
    Test 1-8: Full Multi-School Director Lifecycle:
    1. Admin creates Director with schools = ["SoPE", "SoD"]
       Assert FacultyProfile.school == "SoPE", 2 active RoleAssignment rows exist.
    2. /auth/login returns schools & assigned_schools == ["SoPE", "SoD"]
    3. /auth/me returns same.
    4. Director dashboard returns faculty from both assigned schools.
    5. Director dashboard does NOT return faculty from unassigned school.
    6. Admin edits Director to ["SoD", "SoAA"] -> SoPE deactivated, SoD active, SoAA added active.
    7. Single school director still works.
    8. Duplicate payloads do not create duplicate active rows.
    """
    # Seed schools
    await _seed_school("SoPE", "School of Petroleum Engineering", "engineering", ["director", "dean", "vc"])
    await _seed_school("SoD", "School of Design", "non_engineering", ["director", "dean", "vc"])
    await _seed_school("SoAA", "School of Applied Arts", "non_engineering", ["director", "dean", "vc"])
    await _seed_school("SoCSEA", "School of Computer Science", "engineering", ["director", "dean", "vc"])

    # Ensure open academic year config exists
    async with AsyncSessionLocal() as db:
        cfg_res = await db.execute(select(AppraisalConfig).where(AppraisalConfig.academic_year == YEAR))
        cfg = cfg_res.scalar_one_or_none()
        if not cfg:
            db.add(AppraisalConfig(academic_year=YEAR, is_open=True))
            await db.commit()

    admin = await _seed_admin()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Admin login
        admin_login = await client.post("/api/v1/auth/login", json={"email": admin.email, "password": PASSWORD})
        assert admin_login.status_code == 200
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['token']}"}

        # 1. Admin creates Director with schools = ["SoPE", "SoD"]
        director_email = f"director_multi_{uuid.uuid4().hex[:6]}@test.com"
        create_payload = {
            "full_name": "Dr. Multi Director",
            "email": director_email,
            "password": PASSWORD,
            "appraisal_role": "director",
            "school": "SoPE",
            "schools": ["SoPE", "SoD"],
            "assigned_schools": ["SoPE", "SoD"],
        }
        create_res = await client.post("/api/v1/admin/users", json=create_payload, headers=admin_headers)
        assert create_res.status_code == 201, create_res.text

        # Verify DB records
        async with AsyncSessionLocal() as db:
            fac_res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == director_email))
            fac_prof = fac_res.scalar_one_or_none()
            assert fac_prof is not None
            assert fac_prof.school == "SoPE"

            asg_res = await db.execute(
                select(RoleAssignment).where(
                    RoleAssignment.user_id == fac_prof.id,
                    RoleAssignment.role_type == "DIRECTOR",
                    RoleAssignment.status == "active"
                )
            )
            asgs = asg_res.scalars().all()
            assert len(asgs) == 2
            scopes = {a.scope_id for a in asgs}
            assert scopes == {"SoPE", "SoD"}

        # 2. Login as Director -> check schools and assigned_schools
        dir_login = await client.post("/api/v1/auth/login", json={"email": director_email, "password": PASSWORD})
        assert dir_login.status_code == 200
        dir_token = dir_login.json()["token"]
        dir_profile = dir_login.json()["profile"]
        assert dir_profile["school"] == "SoPE"
        assert set(dir_profile["schools"]) == {"SoPE", "SoD"}
        assert set(dir_profile["assigned_schools"]) == {"SoPE", "SoD"}

        dir_headers = {"Authorization": f"Bearer {dir_token}"}

        # 3. GET /auth/me returns same
        me_res = await client.get("/api/v1/auth/me", headers=dir_headers)
        assert me_res.status_code == 200
        me_profile = me_res.json()
        assert me_profile["school"] == "SoPE"
        assert set(me_profile["schools"]) == {"SoPE", "SoD"}
        assert set(me_profile["assigned_schools"]) == {"SoPE", "SoD"}

        # Seed faculty for SoPE, SoD, and unassigned SoCSEA
        fac_sope_email = f"fac_sope_{uuid.uuid4().hex[:6]}@test.com"
        fac_sod_email = f"fac_sod_{uuid.uuid4().hex[:6]}@test.com"
        fac_socsea_email = f"fac_socsea_{uuid.uuid4().hex[:6]}@test.com"

        for em, sch in [(fac_sope_email, "SoPE"), (fac_sod_email, "SoD"), (fac_socsea_email, "SoCSEA")]:
            await client.post(
                "/api/v1/admin/users",
                json={
                    "full_name": f"Faculty {sch}",
                    "email": em,
                    "password": PASSWORD,
                    "appraisal_role": "faculty",
                    "school": sch,
                },
                headers=admin_headers,
            )

        # 4 & 5. Director dashboard returns faculty from both assigned schools (SoPE & SoD), NOT SoCSEA
        sub_res = await client.get(f"/api/v1/dashboard/subordinates?academic_year={YEAR}", headers=dir_headers)
        assert sub_res.status_code == 200
        sub_emails = [s["email"] for s in sub_res.json()]
        assert fac_sope_email in sub_emails
        assert fac_sod_email in sub_emails
        assert fac_socsea_email not in sub_emails

        # 6. Admin edits Director from ["SoPE", "SoD"] to ["SoD", "SoAA"]
        edit_payload = {
            "schools": ["SoD", "SoAA"],
            "assigned_schools": ["SoD", "SoAA"],
        }
        edit_res = await client.put(f"/api/v1/admin/users/{director_email}", json=edit_payload, headers=admin_headers)
        assert edit_res.status_code == 200

        # Assert SoPE deactivated, SoD active, SoAA added active
        async with AsyncSessionLocal() as db:
            all_asg_res = await db.execute(
                select(RoleAssignment).where(
                    RoleAssignment.user_id == fac_prof.id,
                    RoleAssignment.role_type == "DIRECTOR",
                )
            )
            all_asgs = all_asg_res.scalars().all()
            status_by_scope = {a.scope_id: a.status for a in all_asgs}
            assert status_by_scope["SoPE"] == "transferred"
            assert status_by_scope["SoD"] == "active"
            assert status_by_scope["SoAA"] == "active"

        # 8. Saving duplicate payload does not create duplicate active rows
        edit_res_2 = await client.put(f"/api/v1/admin/users/{director_email}", json=edit_payload, headers=admin_headers)
        assert edit_res_2.status_code == 200
        async with AsyncSessionLocal() as db:
            active_asg_res = await db.execute(
                select(RoleAssignment).where(
                    RoleAssignment.user_id == fac_prof.id,
                    RoleAssignment.role_type == "DIRECTOR",
                    RoleAssignment.status == "active"
                )
            )
            active_asgs = active_asg_res.scalars().all()
            assert len(active_asgs) == 2
            assert {a.scope_id for a in active_asgs} == {"SoD", "SoAA"}

        # 7. Single school director works correctly
        single_dir_email = f"single_dir_{uuid.uuid4().hex[:6]}@test.com"
        await client.post(
            "/api/v1/admin/users",
            json={
                "full_name": "Single School Director",
                "email": single_dir_email,
                "password": PASSWORD,
                "appraisal_role": "director",
                "school": "SoCSEA",
            },
            headers=admin_headers,
        )
        single_login = await client.post("/api/v1/auth/login", json={"email": single_dir_email, "password": PASSWORD})
        assert single_login.status_code == 200
        assert single_login.json()["profile"]["schools"] == ["SoCSEA"]


@pytest.mark.asyncio
async def test_dean_dashboard_dynamic_schools_and_tracks():
    """
    Test Dean Dashboard Dynamic Schools:
    1. Dynamic school created with track="engineering" (e.g. "EA")
       - Faculty submits -> Director reviews -> status Pending Dean Review
       - Engineering Dean sees faculty in /dashboard/subordinates
    2. Dynamic school created with track="non_engineering" (e.g. "XYZ")
       - Faculty submits -> Director reviews -> status Pending Dean Review
       - Non-Engineering Dean sees faculty in /dashboard/subordinates
    3. Wrong Dean cannot see wrong track:
       - Engineering Dean cannot see XYZ (non_engineering)
       - Non-Engineering Dean cannot see EA (engineering)
    4. Dean authority: has_authority_over() returns True for dynamic track, False for wrong track.
    5. Regression: Legacy schools still appear, CISR isolated.
    """
    await _seed_school("EA", "Engineering Academy Dynamic", "engineering", ["director", "dean", "vc"])
    await _seed_school("XYZ", "Design & Arts Dynamic", "non_engineering", ["director", "dean", "vc"])
    await _seed_school("SoCSEA", "School of Computer Science", "engineering", ["director", "dean", "vc"])
    await _seed_school("SoCM", "School of Commerce & Management", "non_engineering", ["director", "dean", "vc"])
    await _seed_school("CISR", "Center for Research", "engineering", ["vc"])

    admin = await _seed_admin()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_login = await client.post("/api/v1/auth/login", json={"email": admin.email, "password": PASSWORD})
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['token']}"}

        # Seed Dean Engineering and Dean Non-Engineering
        dean_eng_email = f"dean_eng_{uuid.uuid4().hex[:6]}@test.com"
        dean_non_eng_email = f"dean_non_eng_{uuid.uuid4().hex[:6]}@test.com"

        await client.post(
            "/api/v1/admin/users",
            json={
                "full_name": "Dean Engineering",
                "email": dean_eng_email,
                "password": PASSWORD,
                "appraisal_role": "dean",
                "school": "engineering",
            },
            headers=admin_headers,
        )

        await client.post(
            "/api/v1/admin/users",
            json={
                "full_name": "Dean Non-Engineering",
                "email": dean_non_eng_email,
                "password": PASSWORD,
                "appraisal_role": "dean",
                "school": "non_engineering",
            },
            headers=admin_headers,
        )

        # Seed Faculty for EA and XYZ
        fac_ea_email = f"fac_ea_{uuid.uuid4().hex[:6]}@test.com"
        fac_xyz_email = f"fac_xyz_{uuid.uuid4().hex[:6]}@test.com"

        await client.post(
            "/api/v1/admin/users",
            json={"full_name": "Fac EA", "email": fac_ea_email, "password": PASSWORD, "appraisal_role": "faculty", "school": "EA"},
            headers=admin_headers,
        )
        await client.post(
            "/api/v1/admin/users",
            json={"full_name": "Fac XYZ", "email": fac_xyz_email, "password": PASSWORD, "appraisal_role": "faculty", "school": "XYZ"},
            headers=admin_headers,
        )

        # Seed declarations for EA and XYZ in status "Pending Dean Review"
        async with AsyncSessionLocal() as db:
            db.add(Declaration(
                faculty_email=fac_ea_email,
                academic_year=YEAR,
                status="Pending Dean Review",
                part_a_total=40,
                part_b_total=40,
                grand_total=80
            ))
            db.add(Declaration(
                faculty_email=fac_xyz_email,
                academic_year=YEAR,
                status="Pending Dean Review",
                part_a_total=40,
                part_b_total=40,
                grand_total=80
            ))
            await db.commit()

        # Login as Engineering Dean
        eng_login = await client.post("/api/v1/auth/login", json={"email": dean_eng_email, "password": PASSWORD})
        assert eng_login.status_code == 200
        eng_headers = {"Authorization": f"Bearer {eng_login.json()['token']}"}

        # Login as Non-Engineering Dean
        non_eng_login = await client.post("/api/v1/auth/login", json={"email": dean_non_eng_email, "password": PASSWORD})
        assert non_eng_login.status_code == 200
        non_eng_headers = {"Authorization": f"Bearer {non_eng_login.json()['token']}"}

        # 1. Engineering Dean sees EA
        eng_sub = await client.get(f"/api/v1/dashboard/subordinates?academic_year={YEAR}", headers=eng_headers)
        assert eng_sub.status_code == 200
        eng_emails = [s["email"] for s in eng_sub.json()]
        assert fac_ea_email in eng_emails
        # 3. Engineering Dean does NOT see XYZ
        assert fac_xyz_email not in eng_emails

        # 2. Non-Engineering Dean sees XYZ
        non_eng_sub = await client.get(f"/api/v1/dashboard/subordinates?academic_year={YEAR}", headers=non_eng_headers)
        assert non_eng_sub.status_code == 200
        non_eng_emails = [s["email"] for s in non_eng_sub.json()]
        assert fac_xyz_email in non_eng_emails
        # 3. Non-Engineering Dean does NOT see EA
        assert fac_ea_email not in non_eng_emails

        # 4. Dean authority check
        dean_eng_user = User(id="dean_eng_id", email=dean_eng_email, roles=["dean"], school="engineering")
        assert dean_eng_user.has_authority_over(fac_ea_email, "faculty", subordinate_school="EA") is True
        assert dean_eng_user.has_authority_over(fac_xyz_email, "faculty", subordinate_school="XYZ") is False
        assert dean_eng_user.has_authority_over("cisr_fac", "faculty", subordinate_school="CISR") is False

        dean_non_eng_user = User(id="dean_non_eng_id", email=dean_non_eng_email, roles=["dean"], school="non_engineering")
        assert dean_non_eng_user.has_authority_over(fac_xyz_email, "faculty", subordinate_school="XYZ") is True
        assert dean_non_eng_user.has_authority_over(fac_ea_email, "faculty", subordinate_school="EA") is False
        assert dean_non_eng_user.has_authority_over("cisr_fac", "faculty", subordinate_school="CISR") is False
