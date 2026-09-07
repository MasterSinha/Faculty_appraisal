"""
Validation tests for Dynamic Approval Chain workflows.

Covers all 4 required scenarios:
School A: has_hod=false, has_director=false, approval_chain=["dean", "vc"]
          Faculty submits -> Dean review submit succeeds -> goes to VC -> VC review succeeds
School B: has_hod=false, has_director=true, approval_chain=["director", "dean", "vc"]
          Faculty submits -> Dean review before Director fails -> Director succeeds -> Dean succeeds
School C: has_hod=true, has_director=false, approval_chain=["hod", "dean", "vc"]
          Faculty submits -> Dean review before HOD fails (no Director required) -> HOD succeeds -> Dean succeeds
School D: has_hod=true, has_director=true, approval_chain=["hod", "director", "dean", "vc"]
          Existing full workflow remains unchanged
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from src.main import app
from src.setup.dependencies import User, get_current_user
from src.setup.database import AsyncSessionLocal
from src.models.core import School, FacultyProfile
from src.setup.local_auth import get_password_hash

YEAR = "2025-26"

SUBMIT_DATA = {
    "academic_year": YEAR,
    "form": {
        "lectures": [
            {
                "semester": "Sem 1",
                "course_code": "GEN101",
                "planned_classes": 40,
                "conducted_classes": 38,
            }
        ],
    },
    "totals": {"partATotal": 10, "partBTotal": 10, "grandTotal": 20},
}

REVIEW_DATA = {
    "academic_year": YEAR,
    "remarks": "Good performance",
    "part_a_score": 45,
    "part_b_score": 40,
    "total_score": 85,
}


async def _seed_school_and_faculty(code: str, full_name: str, has_hod: bool, has_director: bool, approval_chain: list, email: str, dept: str = "General", track: str = "engineering"):
    async with AsyncSessionLocal() as db:
        # Seed School
        res = await db.execute(select(School).where(School.code == code))
        school = res.scalar_one_or_none()
        if not school:
            school = School(
                code=code,
                full_name=full_name,
                track=track,
                has_hod=has_hod,
                has_director=has_director,
                approval_chain=approval_chain,
                departments=[dept],
                default_form="standard",
                active=True,
                order=1,
            )
            db.add(school)
        else:
            school.full_name = full_name
            school.has_hod = has_hod
            school.has_director = has_director
            school.approval_chain = approval_chain
            school.track = track

        # Seed Faculty
        res_fac = await db.execute(select(FacultyProfile).where(FacultyProfile.email == email))
        fac = res_fac.scalar_one_or_none()
        if not fac:
            db.add(
                FacultyProfile(
                    email=email,
                    password_hash=get_password_hash("password"),
                    full_name=f"Faculty {code}",
                    appraisal_role="faculty",
                    school=code,
                    department=dept,
                    is_verified=True,
                )
            )
        else:
            fac.school = code
            fac.department = dept
        await db.commit()


@pytest.mark.asyncio
async def test_school_a_faculty_dean_vc_workflow():
    """
    School A:
    has_hod=false, has_director=false, approval_chain=["dean", "vc"]
    Faculty submits -> Dean review submit succeeds (no Director/HOD required) -> goes to VC -> VC succeeds.
    """
    email = "faculty_school_a@test.com"
    school_code = "SoD"
    await _seed_school_and_faculty(
        code=school_code,
        full_name="School of Design",
        has_hod=False,
        has_director=False,
        approval_chain=["dean", "vc"],
        email=email,
        track="non_engineering",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        try:
            # 1. Faculty logs in and submits appraisal
            login_res = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "password"},
            )
            assert login_res.status_code == 200, login_res.text
            faculty_headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

            submit_res = await client.post(
                "/api/v1/appraisal/submit", json=SUBMIT_DATA, headers=faculty_headers
            )
            assert submit_res.status_code == 200, submit_res.text

            # 2. Dean reviews directly (first reviewer in chain)
            async def get_dean():
                return User(
                    id="dean-a-id",
                    email="dean_a@test.com",
                    roles=["dean"],
                    school="non_engineering",
                )

            app.dependency_overrides[get_current_user] = get_dean
            dean_resp = await client.put(
                f"/api/v1/appraisal-remarks/dean/{email}", json=REVIEW_DATA
            )
            assert dean_resp.status_code == 200, dean_resp.text
            assert dean_resp.json()["status"] == "Pending VC Review"

            # 3. Registrar releases Part D (Leave & Attendance)
            import uuid
            registrar_id = str(uuid.uuid4())
            async def get_registrar():
                return User(
                    id=registrar_id,
                    email="registrar_a@test.com",
                    roles=["registrar"],
                )

            app.dependency_overrides[get_current_user] = get_registrar
            rel_resp = await client.post(
                f"/api/v1/dashboard/part-d-release/{email}",
                json={"registrar_part_d_score": 15.0, "academic_year": YEAR}
            )
            assert rel_resp.status_code == 200, rel_resp.text

            # 4. VC reviews and finalizes
            async def get_vc():
                return User(
                    id="vc-a-id",
                    email="vc_a@test.com",
                    roles=["vc"],
                )

            app.dependency_overrides[get_current_user] = get_vc
            vc_resp = await client.put(
                f"/api/v1/appraisal-remarks/final/{email}", json=REVIEW_DATA
            )
            assert vc_resp.status_code == 200, vc_resp.text
            assert vc_resp.json()["status"] == "Reviewed"

        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_school_b_faculty_director_dean_vc_workflow():
    """
    School B:
    has_hod=false, has_director=true, approval_chain=["director", "dean", "vc"]
    Faculty submits -> Dean review before Director must fail -> Director succeeds -> Dean succeeds.
    """
    email = "faculty_school_b@test.com"
    school_code = "SoCSEA"
    await _seed_school_and_faculty(
        code=school_code,
        full_name="School of Computer Science and Engineering",
        has_hod=False,
        has_director=True,
        approval_chain=["director", "dean", "vc"],
        email=email,
        track="engineering",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        try:
            # 1. Faculty submits
            login_res = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "password"},
            )
            assert login_res.status_code == 200, login_res.text
            faculty_headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

            submit_res = await client.post(
                "/api/v1/appraisal/submit", json=SUBMIT_DATA, headers=faculty_headers
            )
            assert submit_res.status_code == 200, submit_res.text

            # 2. Dean attempts to review before Director -> MUST FAIL
            async def get_dean():
                return User(
                    id="dean-b-id",
                    email="dean_b@test.com",
                    roles=["dean"],
                    school="engineering",
                )

            app.dependency_overrides[get_current_user] = get_dean
            dean_fail_resp = await client.put(
                f"/api/v1/appraisal-remarks/dean/{email}", json=REVIEW_DATA
            )
            assert dean_fail_resp.status_code == 400
            assert "Previous review from DIRECTOR is missing" in dean_fail_resp.json()["detail"]

            # 3. Director reviews -> succeeds -> status becomes Pending Dean Review
            async def get_director():
                return User(
                    id="dir-b-id",
                    email="director_b@test.com",
                    roles=["director"],
                    school=school_code,
                )

            app.dependency_overrides[get_current_user] = get_director
            dir_resp = await client.put(
                f"/api/v1/appraisal-remarks/director/{email}", json=REVIEW_DATA
            )
            assert dir_resp.status_code == 200, dir_resp.text
            assert dir_resp.json()["status"] == "Pending Dean Review"

            # 4. Dean reviews -> now succeeds -> status becomes Pending VC Review
            app.dependency_overrides[get_current_user] = get_dean
            dean_ok_resp = await client.put(
                f"/api/v1/appraisal-remarks/dean/{email}", json=REVIEW_DATA
            )
            assert dean_ok_resp.status_code == 200, dean_ok_resp.text
            assert dean_ok_resp.json()["status"] == "Pending VC Review"

        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_school_c_faculty_hod_dean_vc_workflow():
    """
    School C:
    has_hod=true, has_director=false, approval_chain=["hod", "dean", "vc"]
    Faculty submits -> Dean review before HOD must fail (must NOT require Director) -> HOD succeeds -> Dean succeeds.
    """
    email = "faculty_school_c@test.com"
    school_code = "SoCM"
    dept = "DeptC"
    await _seed_school_and_faculty(
        code=school_code,
        full_name="School of Commerce and Management",
        has_hod=True,
        has_director=False,
        approval_chain=["hod", "dean", "vc"],
        email=email,
        dept=dept,
        track="non_engineering",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        try:
            # 1. Faculty submits
            login_res = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "password"},
            )
            assert login_res.status_code == 200, login_res.text
            faculty_headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

            submit_res = await client.post(
                "/api/v1/appraisal/submit", json=SUBMIT_DATA, headers=faculty_headers
            )
            assert submit_res.status_code == 200, submit_res.text

            # 2. Dean attempts to review before HOD -> MUST FAIL with HOD missing error (NOT Director)
            async def get_dean():
                return User(
                    id="dean-c-id",
                    email="dean_c@test.com",
                    roles=["dean"],
                    school="non_engineering",
                )

            app.dependency_overrides[get_current_user] = get_dean
            dean_fail_resp = await client.put(
                f"/api/v1/appraisal-remarks/dean/{email}", json=REVIEW_DATA
            )
            assert dean_fail_resp.status_code == 400
            assert "Previous review from HOD is missing" in dean_fail_resp.json()["detail"]
            assert "DIRECTOR" not in dean_fail_resp.json()["detail"]

            # 3. HOD reviews -> succeeds -> status becomes Pending Dean Review
            async def get_hod():
                return User(
                    id="hod-c-id",
                    email="hod_c@test.com",
                    roles=["hod"],
                    school=school_code,
                    department=dept,
                )

            app.dependency_overrides[get_current_user] = get_hod
            hod_resp = await client.put(
                f"/api/v1/appraisal-remarks/hod/{email}", json=REVIEW_DATA
            )
            assert hod_resp.status_code == 200, hod_resp.text
            assert hod_resp.json()["status"] == "Pending Dean Review"

            # 4. Dean reviews -> now succeeds -> status becomes Pending VC Review
            app.dependency_overrides[get_current_user] = get_dean
            dean_ok_resp = await client.put(
                f"/api/v1/appraisal-remarks/dean/{email}", json=REVIEW_DATA
            )
            assert dean_ok_resp.status_code == 200, dean_ok_resp.text
            assert dean_ok_resp.json()["status"] == "Pending VC Review"

        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_school_d_faculty_full_chain_workflow():
    """
    School D:
    has_hod=true, has_director=true, approval_chain=["hod", "director", "dean", "vc"]
    Existing full workflow remains unchanged: HOD -> Director -> Dean -> VC.
    """
    email = "faculty_school_d@test.com"
    school_code = "SoEMR"
    dept = "Mechanical"
    await _seed_school_and_faculty(
        code=school_code,
        full_name="School of Engineering",
        has_hod=True,
        has_director=True,
        approval_chain=["hod", "director", "dean", "vc"],
        email=email,
        dept=dept,
        track="engineering",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        try:
            # 1. Faculty submits
            login_res = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "password"},
            )
            assert login_res.status_code == 200, login_res.text
            faculty_headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

            submit_res = await client.post(
                "/api/v1/appraisal/submit", json=SUBMIT_DATA, headers=faculty_headers
            )
            assert submit_res.status_code == 200, submit_res.text

            # 2. Director before HOD -> Fails
            async def get_director():
                return User(
                    id="dir-d-id",
                    email="director_d@test.com",
                    roles=["director"],
                    school=school_code,
                )

            app.dependency_overrides[get_current_user] = get_director
            dir_fail = await client.put(
                f"/api/v1/appraisal-remarks/director/{email}", json=REVIEW_DATA
            )
            assert dir_fail.status_code == 400
            assert "Previous review from HOD is missing" in dir_fail.json()["detail"]

            # 3. HOD reviews -> Pending Director Review
            async def get_hod():
                return User(
                    id="hod-d-id",
                    email="hod_d@test.com",
                    roles=["hod"],
                    school=school_code,
                    department=dept,
                )

            app.dependency_overrides[get_current_user] = get_hod
            hod_resp = await client.put(
                f"/api/v1/appraisal-remarks/hod/{email}", json=REVIEW_DATA
            )
            assert hod_resp.status_code == 200, hod_resp.text
            assert hod_resp.json()["status"] == "Pending Director Review"

            # 4. Dean before Director -> Fails
            async def get_dean():
                return User(
                    id="dean-d-id",
                    email="dean_d@test.com",
                    roles=["dean"],
                    school="engineering",
                )

            app.dependency_overrides[get_current_user] = get_dean
            dean_fail = await client.put(
                f"/api/v1/appraisal-remarks/dean/{email}", json=REVIEW_DATA
            )
            assert dean_fail.status_code == 400
            assert "Previous review from DIRECTOR is missing" in dean_fail.json()["detail"]

            # 5. Director reviews -> Pending Dean Review
            app.dependency_overrides[get_current_user] = get_director
            dir_resp = await client.put(
                f"/api/v1/appraisal-remarks/director/{email}", json=REVIEW_DATA
            )
            assert dir_resp.status_code == 200, dir_resp.text
            assert dir_resp.json()["status"] == "Pending Dean Review"

            # 6. Dean reviews -> Pending VC Review
            app.dependency_overrides[get_current_user] = get_dean
            dean_resp = await client.put(
                f"/api/v1/appraisal-remarks/dean/{email}", json=REVIEW_DATA
            )
            assert dean_resp.status_code == 200, dean_resp.text
            assert dean_resp.json()["status"] == "Pending VC Review"

        finally:
            app.dependency_overrides.clear()
