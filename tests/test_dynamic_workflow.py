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


@pytest.mark.asyncio
async def test_hod_own_appraisal_workflow():
    """
    Example 5:
    If approval_chain = ["hod", "director", "dean", "vc"]:
    HOD submit own appraisal -> Pending Director Review

    If approval_chain = ["hod", "dean", "vc"]:
    HOD submit own appraisal -> Pending Dean Review
    """
    # 1. HOD with Director in chain
    email_d = "hod_with_director@test.com"
    await _seed_school_and_faculty(
        code="SoEMR_HOD",
        full_name="School with HOD and Director",
        has_hod=True,
        has_director=True,
        approval_chain=["hod", "director", "dean", "vc"],
        email=email_d,
        track="engineering",
    )
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == email_d))
        fac = res.scalar_one()
        fac.appraisal_role = "hod"
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email_d, "password": "password"},
        )
        assert login_res.status_code == 200, login_res.text
        hod_headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

        submit_res = await client.post(
            "/api/v1/appraisal/submit", json=SUBMIT_DATA, headers=hod_headers
        )
        assert submit_res.status_code == 200, submit_res.text
        assert submit_res.json()["status"] == "Pending Director Review"
        assert submit_res.json()["next_reviewer"] == "director"

    # 2. HOD without Director in chain
    email_nod = "hod_without_director@test.com"
    await _seed_school_and_faculty(
        code="SoCM_HOD",
        full_name="School with HOD no Director",
        has_hod=True,
        has_director=False,
        approval_chain=["hod", "dean", "vc"],
        email=email_nod,
        track="non_engineering",
    )
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == email_nod))
        fac = res.scalar_one()
        fac.appraisal_role = "hod"
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email_nod, "password": "password"},
        )
        assert login_res.status_code == 200, login_res.text
        hod_headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

        submit_res = await client.post(
            "/api/v1/appraisal/submit", json=SUBMIT_DATA, headers=hod_headers
        )
        assert submit_res.status_code == 200, submit_res.text
        assert submit_res.json()["status"] == "Pending Dean Review"
        assert submit_res.json()["next_reviewer"] == "dean"


@pytest.mark.asyncio
async def test_director_own_appraisal_workflow():
    """
    Example 6:
    Director submit own appraisal -> Pending Dean Review
    Director should not review their own appraisal.
    """
    email_dir = "director_self@test.com"
    school_code = "SoEMR_DIR"
    await _seed_school_and_faculty(
        code=school_code,
        full_name="School for Director Self",
        has_hod=True,
        has_director=True,
        approval_chain=["hod", "director", "dean", "vc"],
        email=email_dir,
        track="engineering",
    )
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == email_dir))
        fac = res.scalar_one()
        fac.appraisal_role = "director"
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email_dir, "password": "password"},
        )
        assert login_res.status_code == 200, login_res.text
        dir_headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

        submit_res = await client.post(
            "/api/v1/appraisal/submit", json=SUBMIT_DATA, headers=dir_headers
        )
        assert submit_res.status_code == 200, submit_res.text
        assert submit_res.json()["status"] == "Pending Dean Review"
        assert submit_res.json()["next_reviewer"] == "dean"


@pytest.mark.asyncio
async def test_dean_own_appraisal_workflow():
    """
    Example 7:
    Dean submit own appraisal -> Pending VC Review
    """
    email_dean = "dean_self@test.com"
    school_code = "SoEMR_DEAN"
    await _seed_school_and_faculty(
        code=school_code,
        full_name="School for Dean Self",
        has_hod=True,
        has_director=True,
        approval_chain=["hod", "director", "dean", "vc"],
        email=email_dean,
        track="engineering",
    )
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == email_dean))
        fac = res.scalar_one()
        fac.appraisal_role = "dean"
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email_dean, "password": "password"},
        )
        assert login_res.status_code == 200, login_res.text
        dean_headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

        submit_res = await client.post(
            "/api/v1/appraisal/submit", json=SUBMIT_DATA, headers=dean_headers
        )
        assert submit_res.status_code == 200, submit_res.text
        assert submit_res.json()["status"] == "Pending VC Review"
        assert submit_res.json()["next_reviewer"] == "vc"


@pytest.mark.asyncio
async def test_vc_own_appraisal_workflow():
    """
    Example 8:
    VC own appraisal -> Reviewed
    """
    email_vc = "vc_self@test.com"
    school_code = "SoEMR_VC"
    await _seed_school_and_faculty(
        code=school_code,
        full_name="School for VC Self",
        has_hod=True,
        has_director=True,
        approval_chain=["hod", "director", "dean", "vc"],
        email=email_vc,
        track="engineering",
    )
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == email_vc))
        fac = res.scalar_one()
        fac.appraisal_role = "vc"
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email_vc, "password": "password"},
        )
        assert login_res.status_code == 200, login_res.text
        vc_headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

        submit_res = await client.post(
            "/api/v1/appraisal/submit", json=SUBMIT_DATA, headers=vc_headers
        )
        assert submit_res.status_code == 200, submit_res.text
        assert submit_res.json()["status"] == "Reviewed"
        assert submit_res.json()["next_reviewer"] is None


@pytest.mark.asyncio
async def test_rejection_workflow_and_resubmission():
    """
    Rule 7: On reviewer reject:
    Do not advance workflow.
    Save: status = "{Reviewer Label} Rejected", rejected_by = reviewer role, next_reviewer = null
    On faculty resubmit: workflow resets to initial step.
    """
    email = "faculty_rejection_test@test.com"
    school_code = "SoRejection"
    await _seed_school_and_faculty(
        code=school_code,
        full_name="School for Rejection",
        has_hod=True,
        has_director=False,
        approval_chain=["hod", "dean", "vc"],
        email=email,
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
            assert submit_res.json()["status"] == "Pending HOD Review"

            # 2. HOD rejects
            async def get_hod():
                return User(
                    id="hod-rej-id",
                    email="hod_rej@test.com",
                    roles=["hod"],
                    school=school_code,
                    department="General",
                )

            app.dependency_overrides[get_current_user] = get_hod
            rej_resp = await client.put(
                f"/api/v1/appraisal-remarks/hod/{email}",
                json={
                    "academic_year": YEAR,
                    "decision": "rejected",
                    "remarks": "Please correct lectures count.",
                },
            )
            assert rej_resp.status_code == 200, rej_resp.text
            rej_data = rej_resp.json()
            assert rej_data["status"] == "HOD Rejected"
            assert rej_data["decision"] == "rejected"
            assert rej_data["rejected_by"] == "hod"
            assert rej_data["next_reviewer"] is None
            assert rej_data["next_reviewer_role"] is None

            # 3. Faculty resubmits -> resets to Pending HOD Review
            app.dependency_overrides.clear()
            resubmit_res = await client.post(
                "/api/v1/appraisal/submit", json=SUBMIT_DATA, headers=faculty_headers
            )
            assert resubmit_res.status_code == 200, resubmit_res.text
            assert resubmit_res.json()["status"] == "Pending HOD Review"
            assert resubmit_res.json()["next_reviewer"] == "hod"

        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_boolean_and_approval_chain_derivation():
    """
    Rule 2, 3, 4:
    If approval_chain is empty in School DB, derive from has_hod & has_director.
    Normalize boolean strings/ints safely ('true', 'false', '1', '0', 'yes', 'no').
    """
    from src.api.v1.remarks import normalize_bool, parse_approval_chain, get_school_workflow_chain

    # Check normalize_bool
    assert normalize_bool(True) is True
    assert normalize_bool(False) is False
    assert normalize_bool("true") is True
    assert normalize_bool("True") is True
    assert normalize_bool("1") is True
    assert normalize_bool(1) is True
    assert normalize_bool("yes") is True
    assert normalize_bool("false") is False
    assert normalize_bool("False") is False
    assert normalize_bool("0") is False
    assert normalize_bool(0) is False
    assert normalize_bool("no") is False

    # Check parse_approval_chain
    assert parse_approval_chain(["hod", "director", "dean", "vc"]) == ["hod", "director", "dean", "vc"]
    assert parse_approval_chain('["hod", "dean", "vc"]') == ["hod", "dean", "vc"]
    assert parse_approval_chain("hod, dean, vc") == ["hod", "dean", "vc"]
    assert parse_approval_chain(["HOD", "Director", "Dean", "VC"]) == ["hod", "director", "dean", "vc"]
    assert parse_approval_chain(["center_head", "vc"]) == ["center_head", "vc"]

    # Test school with approval_chain = [] deriving from has_hod=True, has_director=False
    async with AsyncSessionLocal() as db:
        s_code = "SoBoolTest"
        res = await db.execute(select(School).where(School.code == s_code))
        school = res.scalar_one_or_none()
        if not school:
            school = School(
                code=s_code,
                full_name="School for Boolean Test",
                track="non_engineering",
                has_hod=True,
                has_director=False,
                approval_chain=[],
                departments=["General"],
                active=True,
            )
            db.add(school)
        else:
            school.has_hod = True
            school.has_director = False
            school.approval_chain = []
        await db.commit()

        derived_chain = await get_school_workflow_chain(s_code, db)
        assert derived_chain == ["hod", "dean", "vc"]
