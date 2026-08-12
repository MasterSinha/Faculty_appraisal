import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.setup.dependencies import User, get_current_user
from src.setup.database import AsyncSessionLocal
from src.models.core import FacultyProfile
from src.setup.local_auth import get_password_hash
from sqlalchemy import select

BASE_URL = "http://testserver"

async def _seed_staff_and_reviewers():
    async with AsyncSessionLocal() as db:
        profiles = [
            ("staff@test.com", "staff", "SoCSEA", "Computer Science", "ro@test.com"),
            ("ro@test.com", "reporting_officer", "SoCSEA", "Computer Science", None),
            ("registrar@test.com", "registrar", None, None, None),
            ("vc@test.com", "vc", None, None, None),
        ]
        for email, role, school, dept, ro_email in profiles:
            res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == email))
            if not res.scalar_one_or_none():
                db.add(FacultyProfile(
                    email=email,
                    password_hash=get_password_hash("password"),
                    full_name=email.split("@")[0].title(),
                    appraisal_role=role,
                    school=school,
                    department=dept,
                    reporting_officer_email=ro_email,
                    is_verified=True,
                ))
        await db.commit()

@pytest.mark.asyncio
async def test_non_teaching_workflow():
    await _seed_staff_and_reviewers()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            academic_year = "2025-26"
            
            # 1. Staff submits self-appraisal
            async def get_staff_user():
                return User(id="00000000-0000-0000-0000-000000000001", email="staff@test.com", roles=["staff"])
            app.dependency_overrides[get_current_user] = get_staff_user
            
            appraisal_data = {
                "academic_year": academic_year,
                "joining_date": "2020-01-01",
                "designation": "Lab Assistant",
                "department_section": "Computer Science",
                "experience_dypiu": 5.5,
                "total_experience": 10.0,
                "current_qualifications": "B.Sc. IT",
                "reporting_head": "Director CS",
                "status": "Pending RO Review",
                "payload": {
                    "selfResp": {"text": "Responsibilities text", "marks": 8.5},
                    "selfContrib": {"text": "Contributions text", "marks": 7.0},
                    "selfAchieve": {"text": "Achievements text", "marks": 4.0}
                }
            }
            
            # Create/submit appraisal
            response = await client.put("/api/v1/non-teaching/appraisal", json=appraisal_data)
            assert response.status_code == 200
            assert response.json()["status"] == "Pending RO Review"
            
            # 2. Get my appraisal
            response = await client.get(f"/api/v1/non-teaching/appraisal?academic_year={academic_year}")
            assert response.status_code == 200
            assert response.json()["staff_email"] == "staff@test.com"

            # 3. Reporting Officer Review
            async def get_ro_user():
                return User(id="ro_id", email="ro@test.com", roles=["reporting_officer"])
            app.dependency_overrides[get_current_user] = get_ro_user
            
            ro_data = {
                "academic_year": academic_year,
                "total_score": 8.0,
                "payload": {
                    "selfResp": {"roMarks": 8.0},
                    "selfContrib": {"roMarks": 6.5},
                    "selfAchieve": {"roMarks": 3.5},
                    "partB": {
                        "profComp": {"p0_ro": 5, "p1_ro": 4, "p2_ro": 5, "p3_ro": 4, "p4_ro": 5},
                        "quality": {"p0_ro": 5, "p1_ro": 4, "p2_ro": 5, "p3_ro": 4, "p4_ro": 5},
                        "personal": {"p0_ro": 5, "p1_ro": 5, "p2_ro": 5, "p3_ro": 4, "p4_ro": 5, "p5_ro": 4},
                        "regular": {"p0_ro": 5, "p1_ro": 5, "p2_ro": 4, "p3_ro": 5, "p4_ro": 4}
                    }
                }
            }
            response = await client.put("/api/v1/non-teaching/review/staff@test.com", json=ro_data)
            assert response.status_code == 200
            assert response.json()["status"] == "Reporting Officer Reviewed"

            # 4. Registrar Review
            async def get_registrar_user():
                return User(id="reg_id", email="registrar@test.com", roles=["registrar"])
            app.dependency_overrides[get_current_user] = get_registrar_user
            
            registrar_data = {
                "academic_year": academic_year,
                "total_score": 7.5,
                "payload": {
                    "selfResp": {"regMarks": 7.5},
                    "selfContrib": {"regMarks": 6.0},
                    "selfAchieve": {"regMarks": 3.0},
                    "partB": {
                        "profComp": {"p0_reg": 4, "p1_reg": 4, "p2_reg": 4, "p3_reg": 4, "p4_reg": 4},
                        "quality": {"p0_reg": 4, "p1_reg": 4, "p2_reg": 4, "p3_reg": 4, "p4_reg": 4},
                        "personal": {"p0_reg": 4, "p1_reg": 4, "p2_reg": 4, "p3_reg": 4, "p4_reg": 4, "p5_reg": 4},
                        "regular": {"p0_reg": 4, "p1_reg": 4, "p2_reg": 4, "p3_reg": 4, "p4_reg": 4}
                    }
                }
            }
            response = await client.put("/api/v1/non-teaching/review/staff@test.com", json=registrar_data)
            assert response.status_code == 200
            assert response.json()["status"] == "Registrar Reviewed"
            
            # 5. VC Finalize
            async def get_vc_user():
                return User(id="vc_id", email="vc@test.com", roles=["vc"])
            app.dependency_overrides[get_current_user] = get_vc_user
            
            vc_data = {
                "academic_year": academic_year,
                "total_score": 8.0,
                "payload": {
                    "selfResp": {"vcMarks": 8.0},
                    "selfContrib": {"vcMarks": 7.0},
                    "selfAchieve": {"vcMarks": 4.0},
                    "partB": {
                        "profComp": {"p0_vc": 5, "p1_vc": 5, "p2_vc": 5, "p3_vc": 5, "p4_vc": 5},
                        "quality": {"p0_vc": 5, "p1_vc": 5, "p2_vc": 5, "p3_vc": 5, "p4_vc": 5},
                        "personal": {"p0_vc": 5, "p1_vc": 5, "p2_vc": 5, "p3_vc": 5, "p4_vc": 5, "p5_vc": 5},
                        "regular": {"p0_vc": 5, "p1_vc": 5, "p2_vc": 5, "p3_vc": 5, "p4_vc": 5}
                    }
                }
            }
            response = await client.put("/api/v1/non-teaching/review/staff@test.com", json=vc_data)
            assert response.status_code == 200
            assert response.json()["status"] == "VC Approved"

    finally:
        app.dependency_overrides.clear()
