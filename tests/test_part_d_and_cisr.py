import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from src.main import app
from src.setup.dependencies import User, get_current_user
from src.setup.database import AsyncSessionLocal
from src.models.core import FacultyProfile, AppraisalSnapshot, AppraisalReview, Declaration, School
from src.setup.local_auth import get_password_hash

FACULTY_EMAIL = "part_d_faculty@test.com"
YEAR = "2026-2027"

ORIGINAL_LEAVE_MGMT = [
    {
        "clTaken": 2,
        "clAllowed": 5,
        "mlTaken": 0,
        "mlAllowed": 10,
        "odTaken": 3,
        "odAllowed": 15,
        "coffTaken": 1,
        "coffAllowed": 4,
    }
]

CORRECTED_LEAVE_MGMT_1 = [
    {
        "clTaken": 1,
        "clAllowed": 3,
        "mlTaken": 1,
        "mlAllowed": 2,
        "odTaken": 11,
        "odAllowed": 21,
        "coffTaken": 4,
        "coffAllowed": 6,
    }
]

CORRECTED_LEAVE_MGMT_2 = [
    {
        "clTaken": 0,
        "clAllowed": 3,
        "mlTaken": 2,
        "mlAllowed": 2,
        "odTaken": 12,
        "odAllowed": 21,
        "coffTaken": 5,
        "coffAllowed": 6,
    }
]

SUBMIT_PAYLOAD = {
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
        "leaveManagement": ORIGINAL_LEAVE_MGMT,
        "sectionE": {"communityWork": "Helped students"},
    },
    "totals": {
        "partATotal": 10,
        "partBTotal": 10,
        "partCTotal": 10,
        "partDTotal": 10,
        "grandTotal": 40,
    },
}


async def _seed_test_data():
    async with AsyncSessionLocal() as db:
        # Faculty
        res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == FACULTY_EMAIL))
        fac = res.scalar_one_or_none()
        if not fac:
            fac = FacultyProfile(
                email=FACULTY_EMAIL,
                password_hash=get_password_hash("password"),
                full_name="Part D Test Faculty",
                appraisal_role="faculty",
                school="SoCSEA",
                department="Computer Science",
                is_verified=True,
            )
            db.add(fac)
        else:
            fac.school = "SoCSEA"
            fac.department = "Computer Science"

        # VC user
        res_vc = await db.execute(select(FacultyProfile).where(FacultyProfile.email == "vc@test.com"))
        if not res_vc.scalar_one_or_none():
            db.add(
                FacultyProfile(
                    email="vc@test.com",
                    password_hash=get_password_hash("password"),
                    full_name="VC User",
                    appraisal_role="vc",
                    school="University",
                    department="Admin",
                    is_verified=True,
                )
            )

        await db.commit()


@pytest.mark.asyncio
async def test_part_d_overwrite_workflow():
    """
    1. Faculty submits Part D with original leave rows.
    2. Registrar edits Part D with corrected leave rows and score.
    3. Verify AppraisalSnapshot has corrected leaveManagement and other sections unchanged.
    4. Verify /dashboard/subordinates returns corrected leave rows.
    5. Verify VC receives corrected Part D rows, Registrar score, and remarks.
    6. Verify second Registrar edit replaces previous Part D rows without creating duplicate rows.
    7. Verify unauthorized users cannot edit Part D.
    8. Verify score validation (0 to 25).
    """
    await _seed_test_data()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Faculty logs in and submits appraisal
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": FACULTY_EMAIL, "password": "password"},
        )
        assert login_res.status_code == 200
        faculty_headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

        submit_res = await client.post(
            "/api/v1/appraisal/submit",
            json=SUBMIT_PAYLOAD,
            headers=faculty_headers,
        )
        assert submit_res.status_code == 200

        # Verify initial snapshot
        async with AsyncSessionLocal() as db:
            snap_res = await db.execute(
                select(AppraisalSnapshot).where(
                    AppraisalSnapshot.faculty_email == FACULTY_EMAIL,
                    AppraisalSnapshot.academic_year == YEAR,
                )
            )
            snapshot = snap_res.scalar_one()
            snapshot_id = snapshot.id
            assert snapshot.payload["form"]["leaveManagement"] == ORIGINAL_LEAVE_MGMT
            assert "lectures" in snapshot.payload["form"]
            assert "sectionE" in snapshot.payload["form"]

        # Step 2: Test unauthorized user cannot edit Part D
        async def get_faculty():
            return User(id="fac-id", email="unauth_fac@test.com", roles=["faculty"])

        app.dependency_overrides[get_current_user] = get_faculty
        unauth_res = await client.post(
            f"/api/v1/dashboard/part-d-release/{FACULTY_EMAIL}",
            json={
                "registrar_part_d_score": 21,
                "remarks": "Unauthorized attempt",
                "academic_year": YEAR,
                "leave_management": CORRECTED_LEAVE_MGMT_1,
            },
        )
        assert unauth_res.status_code == 403
        app.dependency_overrides.clear()

        # Step 3: Test score validation (e.g. > 25 or < 0)
        async def get_registrar():
            return User(id="reg-id", email="registrar@test.com", roles=["registrar"])

        app.dependency_overrides[get_current_user] = get_registrar

        invalid_score_res = await client.post(
            f"/api/v1/dashboard/part-d-release/{FACULTY_EMAIL}",
            json={
                "registrar_part_d_score": 30,  # Invalid > 25
                "remarks": "Invalid score",
                "academic_year": YEAR,
                "leave_management": CORRECTED_LEAVE_MGMT_1,
            },
        )
        assert invalid_score_res.status_code == 400

        # Step 4: Registrar edits Part D successfully
        release_res = await client.post(
            f"/api/v1/dashboard/part-d-release/{FACULTY_EMAIL}",
            json={
                "registrar_part_d_score": 21,
                "remarks": "Corrected after verification",
                "leave_management": CORRECTED_LEAVE_MGMT_1,
                "academic_year": YEAR,
            },
        )
        assert release_res.status_code == 200
        rel_data = release_res.json()
        assert rel_data["part_d_status"] == "released"
        assert rel_data["part_d_total"] == 21.0

        # Step 5: Verify same AppraisalSnapshot has updated leaveManagement and unchanged other sections
        async with AsyncSessionLocal() as db:
            snap_res2 = await db.execute(
                select(AppraisalSnapshot).where(
                    AppraisalSnapshot.faculty_email == FACULTY_EMAIL,
                    AppraisalSnapshot.academic_year == YEAR,
                )
            )
            snapshot2 = snap_res2.scalar_one()
            assert snapshot2.id == snapshot_id
            assert snapshot2.payload["form"]["leaveManagement"] == CORRECTED_LEAVE_MGMT_1
            # Verify other snapshot sections remain exactly unchanged
            assert snapshot2.payload["form"]["lectures"] == SUBMIT_PAYLOAD["form"]["lectures"]
            assert snapshot2.payload["form"]["sectionE"] == SUBMIT_PAYLOAD["form"]["sectionE"]

            # Verify single AppraisalReview row for registrar
            rev_res = await db.execute(
                select(AppraisalReview).where(
                    AppraisalReview.faculty_email == FACULTY_EMAIL,
                    AppraisalReview.academic_year == YEAR,
                    AppraisalReview.reviewer_role == "registrar",
                )
            )
            reviews = rev_res.scalars().all()
            assert len(reviews) == 1
            assert reviews[0].registrar_part_d_score == 21.0
            assert reviews[0].remarks == "Corrected after verification"

        # Step 6: Verify /dashboard/subordinates returns corrected leave rows
        async def get_admin():
            return User(id="admin-id", email="admin@test.com", roles=["admin"])

        app.dependency_overrides[get_current_user] = get_admin
        sub_res = await client.get(f"/api/v1/dashboard/subordinates?academic_year={YEAR}")
        assert sub_res.status_code == 200
        sub_list = sub_res.json()
        fac_entry = next((s for s in sub_list if s["email"] == FACULTY_EMAIL), None)
        assert fac_entry is not None
        assert fac_entry["leave_management"] == CORRECTED_LEAVE_MGMT_1
        assert fac_entry["registrar_part_d_score"] == 21.0
        assert fac_entry["registrar_part_d_remarks"] == "Corrected after verification"

        # Step 7: Verify VC receives corrected Part D rows, Registrar score, and remarks
        async def get_vc():
            return User(id="vc-id", email="vc@test.com", roles=["vc"])

        app.dependency_overrides[get_current_user] = get_vc
        vc_fac_res = await client.get(f"/api/v1/dashboard/faculty/{FACULTY_EMAIL}?academic_year={YEAR}")
        assert vc_fac_res.status_code == 200
        vc_fac_data = vc_fac_res.json()
        assert vc_fac_data["leave_management"] == CORRECTED_LEAVE_MGMT_1
        assert vc_fac_data["payload"]["form"]["leaveManagement"] == CORRECTED_LEAVE_MGMT_1
        assert vc_fac_data["registrar_part_d_score"] == 21.0
        assert vc_fac_data["registrar_part_d_remarks"] == "Corrected after verification"

        # Step 8: Verify second Registrar edit replaces previous Part D rows without duplicate rows
        app.dependency_overrides[get_current_user] = get_registrar
        release_res2 = await client.post(
            f"/api/v1/dashboard/part-d-release/{FACULTY_EMAIL}",
            json={
                "registrar_part_d_score": 24,
                "remarks": "Second correction after re-audit",
                "leave_management": CORRECTED_LEAVE_MGMT_2,
                "academic_year": YEAR,
            },
        )
        assert release_res2.status_code == 200

        async with AsyncSessionLocal() as db:
            snap_res3 = await db.execute(
                select(AppraisalSnapshot).where(
                    AppraisalSnapshot.faculty_email == FACULTY_EMAIL,
                    AppraisalSnapshot.academic_year == YEAR,
                )
            )
            snapshot3 = snap_res3.scalar_one()
            assert snapshot3.id == snapshot_id
            assert snapshot3.payload["form"]["leaveManagement"] == CORRECTED_LEAVE_MGMT_2

            rev_res2 = await db.execute(
                select(AppraisalReview).where(
                    AppraisalReview.faculty_email == FACULTY_EMAIL,
                    AppraisalReview.academic_year == YEAR,
                    AppraisalReview.reviewer_role == "registrar",
                )
            )
            reviews2 = rev_res2.scalars().all()
            assert len(reviews2) == 1
            assert reviews2[0].registrar_part_d_score == 24.0
            assert reviews2[0].remarks == "Second correction after re-audit"

        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cisr_dynamic_track_support():
    """
    Verify CISR dynamic track:
    1. Admin creates a school with track='cisr', has_hod=False, has_director=False, approval_chain=['center_head', 'vc'].
    2. Dynamic school catalog returns cisr track.
    3. Dean / Director cannot access CISR faculty.
    4. Center Head and VC have authority over CISR faculty.
    5. Invalid track is rejected.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async def get_admin():
            return User(id="admin-id", email="admin@test.com", roles=["admin"])

        app.dependency_overrides[get_current_user] = get_admin

        # Test valid CISR school creation
        cisr_payload = {
            "code": "CISR_TEST",
            "full_name": "Center for Interdisciplinary Science and Research",
            "track": "cisr",
            "has_hod": False,
            "has_director": False,
            "approval_chain": ["center_head", "vc"],
            "departments": ["Research"],
            "default_form": "standard",
            "active": True,
            "order": 10,
        }
        res = await client.post("/api/v1/admin/schools", json=cisr_payload)
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["code"] == "CISR_TEST"
        assert data["track"] == "cisr"
        assert data["has_hod"] is False
        assert data["has_director"] is False
        assert data["approval_chain"] == ["center_head", "vc"]

        # Test invalid track is rejected
        bad_track_payload = {
            "code": "BAD_TRACK",
            "full_name": "Bad Track School",
            "track": "invalid_track",
            "has_hod": False,
            "has_director": False,
            "approval_chain": ["center_head", "vc"],
        }
        bad_res = await client.post("/api/v1/admin/schools", json=bad_track_payload)
        assert bad_res.status_code == 400
        assert "Invalid track" in bad_res.json()["detail"]

        # Authority checks for CISR:
        # Dean (engineering or non_engineering) cannot access CISR faculty
        dean_eng = User(id="dean-eng-id", email="dean_eng@test.com", roles=["dean"], school="engineering")
        assert not dean_eng.has_authority_over("cisr_fac@test.com", "faculty", subordinate_dept="Research", subordinate_school="CISR_TEST")
        assert not dean_eng.has_authority_over("cisr_fac@test.com", "faculty", subordinate_dept="Research", subordinate_school="CISR")

        # Director cannot access CISR faculty
        director = User(id="dir-id", email="director@test.com", roles=["director"], school="SoCSEA")
        assert not director.has_authority_over("cisr_fac@test.com", "faculty", subordinate_dept="Research", subordinate_school="CISR_TEST")
        assert not director.has_authority_over("cisr_fac@test.com", "faculty", subordinate_dept="Research", subordinate_school="CISR")

        # Center Head can access CISR faculty
        center_head = User(id="ch-id", email="centerhead@test.com", roles=["center_head"], school="CISR")
        assert center_head.has_authority_over("cisr_fac@test.com", "faculty", subordinate_dept="Research", subordinate_school="CISR")

        # VC can access CISR faculty
        vc = User(id="vc-id", email="vc@test.com", roles=["vc"])
        assert vc.has_authority_over("cisr_fac@test.com", "faculty", subordinate_dept="Research", subordinate_school="CISR")

        app.dependency_overrides.clear()
