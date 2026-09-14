"""
Comprehensive Test Suite for Dynamic Form Registrar Part (registrar_part flag) End-to-End.
Tests:
1. Admin Form Builder CRUD for registrar_part (with dual-casing alias support).
2. Faculty GET /appraisal/form-schema exposes registrar_part and registrarPart.
3. Dynamic form WITHOUT registrar_part:
   - Initial Declaration.part_d_status is 'released'.
   - Faculty does not appear in Registrar's /dashboard/part-d-queue.
   - VC is not blocked by Part D gate.
4. Dynamic form WITH registrar_part:
   - Initial Declaration.part_d_status is 'pending'.
   - Faculty appears in Registrar's /dashboard/part-d-queue.
   - Registrar release enforces schema-computed max_marks (e.g. 30 instead of fixed 25).
   - Successful release updates Declaration.part_d_status to 'released', updates totals, and unblocks VC.
5. Standard appraisal backward compatibility:
   - Standard forms retain fixed 25 max score validation and standard totals math.
"""

import pytest
import uuid
from decimal import Decimal
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

from src.main import app
from src.setup.database import AsyncSessionLocal
from src.setup.dependencies import User, get_current_user
from src.models.core import FormSectionDefinition, Declaration, AppraisalReview, AppraisalSnapshot, FacultyProfile, School
from src.api.v1.appraisal import invalidate_form_schema_cache, _SCHEMA_CACHE


@pytest.fixture
def admin_override():
    async def get_admin():
        return User(id="admin-test-id", email="sysadmin@test.com", roles=["admin"])

    app.dependency_overrides[get_current_user] = get_admin
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def registrar_override():
    async def get_registrar():
        return User(id="registrar-test-id", email="registrar@test.com", roles=["registrar"])

    app.dependency_overrides[get_current_user] = get_registrar
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def vc_override():
    async def get_vc():
        return User(id="vc-test-id", email="vc@test.com", roles=["vc"])

    app.dependency_overrides[get_current_user] = get_vc
    yield
    app.dependency_overrides.clear()


def make_faculty_override(email: str, school: str = "Engineering"):
    async def get_fac():
        return User(id="fac-test-id", email=email, school=school, roles=["faculty"])
    return get_fac


@pytest.mark.asyncio
async def test_admin_form_builder_registrar_part_crud(admin_override):
    transport = ASGITransport(app=app)
    fam = "test_reg_builder_fam"
    sec_code = "test_reg_sec_1"

    async with AsyncSessionLocal() as db:
        await db.execute(delete(FormSectionDefinition).where(FormSectionDefinition.form_family == fam))
        await db.commit()
    invalidate_form_schema_cache(fam)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create section with registrar_part = True (camelCase alias)
        create_payload = {
            "code": sec_code,
            "form_family": fam,
            "part": "Part D - Governance",
            "section_key": "sec_gov",
            "title": "Governance & Compliance",
            "max_marks": 30.0,
            "active": True,
            "order": 1,
            "registrarPart": True,
            "fields": [
                {"id": "f1", "key": "compliance_score", "label": "Compliance", "type": "number", "active": True}
            ]
        }
        res_create = await client.post("/api/v1/admin/form-schema", json=create_payload)
        assert res_create.status_code == 200, res_create.text
        data = res_create.json()
        assert data["registrar_part"] is True
        assert data["registrarPart"] is True
        assert data["maxMarks"] == 30.0

        # 2. Verify faculty read path GET /appraisal/form-schema exposes registrar_part
        res_read = await client.get(f"/api/v1/appraisal/form-schema?form_family={fam}")
        assert res_read.status_code == 200
        read_schema = res_read.json()
        assert len(read_schema) == 1
        assert read_schema[0]["registrar_part"] is True
        assert read_schema[0]["registrarPart"] is True

        # 3. Update section metadata to set registrar_part = False
        res_update = await client.put(
            f"/api/v1/admin/form-schema/{sec_code}",
            json={"registrar_part": False}
        )
        assert res_update.status_code == 200
        assert res_update.json()["registrar_part"] is False
        assert res_update.json()["registrarPart"] is False

        # 4. Verify updated read path schema reflects false
        res_read2 = await client.get(f"/api/v1/appraisal/form-schema?form_family={fam}")
        assert res_read2.status_code == 200
        assert res_read2.json()[0]["registrar_part"] is False
        assert res_read2.json()[0]["registrarPart"] is False

    # Cleanup
    async with AsyncSessionLocal() as db:
        await db.execute(delete(FormSectionDefinition).where(FormSectionDefinition.form_family == fam))
        await db.commit()
    invalidate_form_schema_cache(fam)


@pytest.mark.asyncio
async def test_dynamic_form_without_registrar_part_flow():
    transport = ASGITransport(app=app)
    fam = "dynamic_fam_no_reg"
    sec_code = "dyn_no_reg_sec_1"
    fac_email = "dynamic_fac_noreg@test.com"
    academic_year = "2025-2026"

    # Setup DB
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Declaration).where(Declaration.faculty_email == fac_email))
        await db.execute(delete(AppraisalSnapshot).where(AppraisalSnapshot.faculty_email == fac_email))
        await db.execute(delete(AppraisalReview).where(AppraisalReview.faculty_email == fac_email))
        await db.execute(delete(FormSectionDefinition).where(FormSectionDefinition.form_family == fam))
        await db.execute(delete(FacultyProfile).where(FacultyProfile.email == fac_email))

        # Dynamic section WITHOUT registrar_part (default False)
        sec = FormSectionDefinition(
            code=sec_code,
            form_family=fam,
            part="Part 1",
            section_key="sec1",
            title="Custom Part 1",
            max_marks=100.0,
            active=True,
            order=1,
            registrar_part=False,
            fields=[{"id": "f1", "key": "c1", "label": "Column 1", "type": "text", "active": True}]
        )
        db.add(sec)

        prof = FacultyProfile(
            email=fac_email,
            full_name="Dynamic Faculty No Reg",
            school="School of Law",
            department="Law",
            appraisal_role="Faculty"
        )
        db.add(prof)
        await db.commit()

    invalidate_form_schema_cache(fam)

    # 1. Faculty submits dynamic form
    app.dependency_overrides[get_current_user] = make_faculty_override(fac_email, "School of Law")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        submit_payload = {
            "academic_year": academic_year,
            "form_family": fam,
            "form": {
                "form_family": fam,
                "sec1": [{"c1": "Value 1"}]
            },
            "totals": {
                "grandTotal": 85.0
            }
        }
        res_sub = await client.post("/api/v1/appraisal/submit", json=submit_payload)
        assert res_sub.status_code == 200, res_sub.text

    # 2. Verify Declaration was created with part_d_status == 'released'
    async with AsyncSessionLocal() as db:
        decl_res = await db.execute(select(Declaration).where(
            Declaration.faculty_email == fac_email,
            Declaration.academic_year == academic_year
        ))
        decl = decl_res.scalar_one()
        assert decl.part_d_status == "released"
        assert float(decl.grand_total) == 85.0

    # 3. Verify Registrar's /part-d-queue DOES NOT include this faculty
    app.dependency_overrides[get_current_user] = lambda: User(id="reg-id", email="reg@test.com", roles=["registrar"])
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_q = await client.get(f"/api/v1/dashboard/part-d-queue?academic_year={academic_year}")
        assert res_q.status_code == 200
        emails_in_queue = [item["faculty_email"] for item in res_q.json()]
        assert fac_email not in emails_in_queue

    # Cleanup
    app.dependency_overrides.clear()
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Declaration).where(Declaration.faculty_email == fac_email))
        await db.execute(delete(AppraisalSnapshot).where(AppraisalSnapshot.faculty_email == fac_email))
        await db.execute(delete(AppraisalReview).where(AppraisalReview.faculty_email == fac_email))
        await db.execute(delete(FormSectionDefinition).where(FormSectionDefinition.form_family == fam))
        await db.execute(delete(FacultyProfile).where(FacultyProfile.email == fac_email))
        await db.commit()
    invalidate_form_schema_cache(fam)


@pytest.mark.asyncio
async def test_dynamic_form_with_registrar_part_flow():
    transport = ASGITransport(app=app)
    fam = "dynamic_fam_with_reg"
    sec_code = "dyn_reg_sec_1"
    fac_email = "dynamic_fac_reg@test.com"
    academic_year = "2025-2026"

    # Setup DB
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Declaration).where(Declaration.faculty_email == fac_email))
        await db.execute(delete(AppraisalSnapshot).where(AppraisalSnapshot.faculty_email == fac_email))
        await db.execute(delete(AppraisalReview).where(AppraisalReview.faculty_email == fac_email))
        await db.execute(delete(FormSectionDefinition).where(FormSectionDefinition.form_family == fam))
        await db.execute(delete(FacultyProfile).where(FacultyProfile.email == fac_email))

        # Dynamic section WITH registrar_part = True and max_marks = 30
        sec = FormSectionDefinition(
            code=sec_code,
            form_family=fam,
            part="Registrar Part",
            section_key="reg_sec",
            title="Registrar Evaluation Table",
            max_marks=30.0,
            active=True,
            order=1,
            registrar_part=True,
            fields=[{"id": "f1", "key": "eval", "label": "Evaluation", "type": "number", "active": True}]
        )
        db.add(sec)

        prof = FacultyProfile(
            email=fac_email,
            full_name="Dynamic Faculty Reg",
            school="School of Pharmacy",
            department="Pharmacy",
            appraisal_role="Faculty"
        )
        db.add(prof)
        await db.commit()

    invalidate_form_schema_cache(fam)

    # 1. Faculty submits dynamic form
    app.dependency_overrides[get_current_user] = make_faculty_override(fac_email, "School of Pharmacy")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        submit_payload = {
            "academic_year": academic_year,
            "form_family": fam,
            "form": {
                "form_family": fam,
                "reg_sec": [{"eval": 20}]
            },
            "totals": {
                "partATotal": 50.0,
                "partBTotal": 20.0,
                "grandTotal": 70.0
            }
        }
        res_sub = await client.post("/api/v1/appraisal/submit", json=submit_payload)
        assert res_sub.status_code == 200, res_sub.text

    # 2. Verify Declaration was created with part_d_status == 'pending'
    async with AsyncSessionLocal() as db:
        decl_res = await db.execute(select(Declaration).where(
            Declaration.faculty_email == fac_email,
            Declaration.academic_year == academic_year
        ))
        decl = decl_res.scalar_one()
        assert decl.part_d_status == "pending"

    # 3. Verify Registrar's /part-d-queue includes this faculty
    app.dependency_overrides[get_current_user] = lambda: User(id="reg-id", email="registrar@test.com", roles=["registrar"])
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_q = await client.get(f"/api/v1/dashboard/part-d-queue?academic_year={academic_year}")
        assert res_q.status_code == 200
        items = res_q.json()
        target = next((item for item in items if item["faculty_email"] == fac_email), None)
        assert target is not None
        assert target["part_d_status"] == "pending"
        assert target["form_family"] == fam

        # 4. Registrar attempts to release with score > 30 (max is 30 for this schema) -> 400
        res_fail = await client.post(
            f"/api/v1/dashboard/part-d-release/{fac_email}",
            json={
                "registrar_part_d_score": 35.0,
                "academic_year": academic_year,
                "remarks": "Score exceeding max"
            }
        )
        assert res_fail.status_code == 400
        assert "between 0 and 30" in res_fail.json()["detail"]

        # 5. Registrar releases with valid score 28 <= 30 -> 200 OK
        res_ok = await client.post(
            f"/api/v1/dashboard/part-d-release/{fac_email}",
            json={
                "registrar_part_d_score": 28.0,
                "academic_year": academic_year,
                "remarks": "Approved by Registrar"
            }
        )
        assert res_ok.status_code == 200
        data = res_ok.json()
        assert data["part_d_status"] == "released"
        assert data["part_d_total"] == 28.0
        # Grand total recalculation: 50 + 20 + 28 = 98
        assert data["grand_total"] == 98.0

    # 6. Verify Declaration is now 'released' in DB
    async with AsyncSessionLocal() as db:
        decl_res2 = await db.execute(select(Declaration).where(
            Declaration.faculty_email == fac_email,
            Declaration.academic_year == academic_year
        ))
        decl2 = decl_res2.scalar_one()
        assert decl2.part_d_status == "released"
        assert float(decl2.part_d_total) == 28.0
        assert float(decl2.grand_total) == 98.0

    # Cleanup
    app.dependency_overrides.clear()
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Declaration).where(Declaration.faculty_email == fac_email))
        await db.execute(delete(AppraisalSnapshot).where(AppraisalSnapshot.faculty_email == fac_email))
        await db.execute(delete(AppraisalReview).where(AppraisalReview.faculty_email == fac_email))
        await db.execute(delete(FormSectionDefinition).where(FormSectionDefinition.form_family == fam))
        await db.execute(delete(FacultyProfile).where(FacultyProfile.email == fac_email))
        await db.commit()
    invalidate_form_schema_cache(fam)


@pytest.mark.asyncio
async def test_vc_gate_unblocked_for_dynamic_form_without_registrar_part(vc_override):
    """
    Verifies that when a dynamic form has no registrar part, Declaration.part_d_status is 'released',
    allowing the VC to finalize the review without triggering a 409 conflict.
    """
    transport = ASGITransport(app=app)
    fam = "dynamic_vc_unblocked_fam"
    sec_code = "dyn_vc_sec_1"
    fac_email = "dynamic_vc_fac@test.com"
    academic_year = "2025-2026"

    # Setup DB
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Declaration).where(Declaration.faculty_email == fac_email))
        await db.execute(delete(AppraisalSnapshot).where(AppraisalSnapshot.faculty_email == fac_email))
        await db.execute(delete(AppraisalReview).where(AppraisalReview.faculty_email == fac_email))
        await db.execute(delete(FormSectionDefinition).where(FormSectionDefinition.form_family == fam))
        await db.execute(delete(FacultyProfile).where(FacultyProfile.email == fac_email))

        sec = FormSectionDefinition(
            code=sec_code,
            form_family=fam,
            part="Core Part",
            section_key="core_sec",
            title="Core Academic Evaluation",
            max_marks=100.0,
            active=True,
            order=1,
            registrar_part=False,
            fields=[{"id": "f1", "key": "c1", "label": "Column 1", "type": "text", "active": True}]
        )
        db.add(sec)

        prof = FacultyProfile(
            email=fac_email,
            full_name="Dynamic VC Faculty",
            school="School of Law",
            department="Law",
            appraisal_role="Faculty"
        )
        db.add(prof)
        await db.commit()

    invalidate_form_schema_cache(fam)

    # 1. Faculty submits dynamic form
    app.dependency_overrides[get_current_user] = make_faculty_override(fac_email, "School of Law")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        submit_payload = {
            "academic_year": academic_year,
            "form_family": fam,
            "form": {"form_family": fam, "core_sec": [{"c1": "Data"}]},
            "totals": {"grandTotal": 90.0}
        }
        res_sub = await client.post("/api/v1/appraisal/submit", json=submit_payload)
        assert res_sub.status_code == 200

    # 2. Insert prior Dean review so approval chain allows VC review
    async with AsyncSessionLocal() as db:
        dean_review = AppraisalReview(
            faculty_email=fac_email,
            academic_year=academic_year,
            reviewer_email="dean@test.com",
            reviewer_role="dean",
            part_a_score=85.0,
            part_b_score=0.0,
            part_c_score=0.0,
            part_d_score=0.0,
            total_score=85.0,
            status="Reviewed",
        )
        db.add(dean_review)
        await db.commit()

    # 3. VC finalizes review -> Must NOT get 409 conflict
    app.dependency_overrides[get_current_user] = lambda: User(id="vc-id", email="vc@test.com", roles=["vc"])
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        vc_payload = {
            "academic_year": academic_year,
            "score": 92.0,
            "part_a_score": 92.0,
            "part_b_score": 0.0,
            "remarks": "Approved by VC without Part D gating"
        }
        res_vc = await client.put(f"/api/v1/appraisal-remarks/final/{fac_email}", json=vc_payload)
        assert res_vc.status_code == 200, res_vc.text
        assert res_vc.json()["status"] == "Reviewed"

    # Cleanup
    app.dependency_overrides.clear()
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Declaration).where(Declaration.faculty_email == fac_email))
        await db.execute(delete(AppraisalSnapshot).where(AppraisalSnapshot.faculty_email == fac_email))
        await db.execute(delete(AppraisalReview).where(AppraisalReview.faculty_email == fac_email))
        await db.execute(delete(FormSectionDefinition).where(FormSectionDefinition.form_family == fam))
        await db.execute(delete(FacultyProfile).where(FacultyProfile.email == fac_email))
        await db.commit()
    invalidate_form_schema_cache(fam)


@pytest.mark.asyncio
async def test_standard_appraisal_part_d_compatibility(registrar_override):
    """
    Verifies that Standard appraisal forms preserve the 25 max score limit and Part D gating.
    """
    transport = ASGITransport(app=app)
    fac_email = "standard_compat_fac@test.com"
    academic_year = "2025-2026"

    async with AsyncSessionLocal() as db:
        await db.execute(delete(Declaration).where(Declaration.faculty_email == fac_email))
        await db.execute(delete(AppraisalSnapshot).where(AppraisalSnapshot.faculty_email == fac_email))
        await db.execute(delete(AppraisalReview).where(AppraisalReview.faculty_email == fac_email))
        await db.execute(delete(FacultyProfile).where(FacultyProfile.email == fac_email))

        prof = FacultyProfile(
            email=fac_email,
            full_name="Standard Faculty",
            school="SoCSEA",
            department="Computer Science",
            appraisal_role="Faculty"
        )
        db.add(prof)

        decl = Declaration(
            faculty_email=fac_email,
            academic_year=academic_year,
            part_a_total=50.0,
            part_b_total=20.0,
            part_c_total=10.0,
            part_d_total=0.0,
            grand_total=80.0,
            status="Pending Review",
            part_d_status="pending"
        )
        db.add(decl)
        await db.commit()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Standard appraisal rejects score > 25
        res_fail = await client.post(
            f"/api/v1/dashboard/part-d-release/{fac_email}",
            json={"registrar_part_d_score": 30.0, "academic_year": academic_year}
        )
        assert res_fail.status_code == 400
        assert "between 0 and 25" in res_fail.json()["detail"]

        # 2. Standard appraisal accepts score <= 25 and computes grand total
        res_ok = await client.post(
            f"/api/v1/dashboard/part-d-release/{fac_email}",
            json={"registrar_part_d_score": 20.0, "academic_year": academic_year}
        )
        assert res_ok.status_code == 200
        assert res_ok.json()["grand_total"] == 100.0  # 50 + 20 + 10 + 20

    # Cleanup
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Declaration).where(Declaration.faculty_email == fac_email))
        await db.execute(delete(AppraisalSnapshot).where(AppraisalSnapshot.faculty_email == fac_email))
        await db.execute(delete(AppraisalReview).where(AppraisalReview.faculty_email == fac_email))
        await db.execute(delete(FacultyProfile).where(FacultyProfile.email == fac_email))
        await db.commit()

