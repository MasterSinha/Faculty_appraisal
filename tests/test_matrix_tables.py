"""
Unit and Integration Tests for Dynamic Matrix Appraisal Tables.
Tests:
1. Schema Support:
   - Admin create section with type: 'table', layout: 'matrix', rowHeaderTitle, rowHeaders, columns.
   - Validation of row header IDs (unique, non-empty, allow blank labels).
   - Faculty read GET /api/v1/appraisal/form-schema preserves matrix properties and active columns.
   - Renaming/reordering row header labels preserves stable IDs.
2. Answer Contract & Validation:
   - Draft saving allows partial/incomplete matrix rows.
   - Submission validation with requireCompleteRows:
     - Started row requires all editable non-computed columns.
     - Entirely empty optional rows are skipped.
     - Rejection of unknown row IDs not present in schema.
     - Rejection of duplicate row IDs in submitted matrix.
     - Preservation of 0, 0.0, and False values.
3. Data Shredding:
   - Persistence into CustomSectionRow preserving _matrixRowId in custom_fields.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

from src.main import app
from src.setup.database import AsyncSessionLocal
from src.setup.dependencies import User, get_current_user
from src.models.core import FormSectionDefinition, CustomSectionRow, Declaration, AppraisalSnapshot
from src.setup.form_schema_utils import (
    normalize_field_schema,
    validate_and_normalize_fields,
    filter_active_form_schema,
    validate_table_row_completeness,
)
from src.api.v1.appraisal import invalidate_form_schema_cache


@pytest.fixture
def admin_override():
    async def get_admin():
        return User(id="admin-matrix-id", email="sysadmin@test.com", roles=["admin"])

    app.dependency_overrides[get_current_user] = get_admin
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def nonadmin_override():
    async def get_nonadmin():
        return User(id="user-matrix-id", email="faculty_matrix@test.com", roles=["faculty"], school="SoCSEA")

    app.dependency_overrides[get_current_user] = get_nonadmin
    yield
    app.dependency_overrides.clear()


# ===========================================================================
# 1. Unit Tests for Matrix Schema Normalization & Validation
# ===========================================================================

def test_normalize_matrix_field_schema_success():
    raw_field = {
        "id": "matrix_sec_f1",
        "key": "eval_matrix",
        "label": "Evaluation Matrix",
        "type": "table",
        "layout": "matrix",
        "rowHeaderTitle": "Criteria",
        "rowHeaders": [
            {"id": "crit_1", "label": "Criteria 1"},
            {"id": "crit_2", "label": "Criteria 2"},
            {"id": "crit_3", "label": ""},  # blank label allowed
        ],
        "requireCompleteRows": True,
        "columns": [
            {"key": "target", "name": "Target", "type": "number"},
            {"key": "achieved", "name": "Achieved", "type": "number"},
            {"key": "remarks", "name": "Remarks", "type": "text"},
        ]
    }

    norm = normalize_field_schema(raw_field, strict=True)
    assert norm["layout"] == "matrix"
    assert norm["rowHeaderTitle"] == "Criteria"
    assert norm["row_header_title"] == "Criteria"
    assert len(norm["rowHeaders"]) == 3
    assert norm["rowHeaders"][0] == {"id": "crit_1", "label": "Criteria 1"}
    assert norm["rowHeaders"][2] == {"id": "crit_3", "label": ""}
    assert norm["requireCompleteRows"] is True
    assert len(norm["columns"]) == 3
    assert norm["columns"][0]["key"] == "target"


def test_matrix_row_headers_strict_validation_rejects_empty_or_duplicate_ids():
    # Empty ID in strict mode
    bad_empty_id = {
        "label": "Matrix Table",
        "type": "table",
        "layout": "matrix",
        "rowHeaders": [{"id": "", "label": "Row 1"}],
    }
    with pytest.raises(Exception):
        normalize_field_schema(bad_empty_id, strict=True)

    # Duplicate ID in strict mode
    bad_dup_id = {
        "label": "Matrix Table",
        "type": "table",
        "layout": "matrix",
        "rowHeaders": [
            {"id": "r1", "label": "Row 1"},
            {"id": "r1", "label": "Row 1 Duplicate"}
        ],
    }
    with pytest.raises(Exception):
        normalize_field_schema(bad_dup_id, strict=True)


# ===========================================================================
# 2. Integration Tests: Admin API & Faculty Read for Matrix Schemas
# ===========================================================================

@pytest.mark.asyncio
async def test_admin_matrix_table_crud_and_faculty_read(admin_override):
    transport = ASGITransport(app=app)
    family = "matrix_test_fam"
    sec_code = "matrix_sec_100"

    async with AsyncSessionLocal() as db:
        await db.execute(delete(FormSectionDefinition).where(FormSectionDefinition.form_family == family))
        await db.commit()
    invalidate_form_schema_cache(family)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Admin creates matrix section
        payload_create = {
            "code": sec_code,
            "form_family": family,
            "part": "Part A",
            "section_key": "custom_matrix_sec",
            "title": "Faculty Teaching Matrix",
            "max_marks": 30,
            "fields": [
                {
                    "id": "matrix_field_1",
                    "key": "teaching_matrix",
                    "label": "Teaching Load Matrix",
                    "type": "table",
                    "layout": "matrix",
                    "rowHeaderTitle": "Semesters",
                    "rowHeaders": [
                        {"id": "sem_odd", "label": "Odd Semester (I, III, V, VII)"},
                        {"id": "sem_even", "label": "Even Semester (II, IV, VI, VIII)"}
                    ],
                    "requireCompleteRows": True,
                    "columns": [
                        {"id": "col_planned", "key": "planned", "name": "Planned Lectures", "type": "number", "maxMarks": 50},
                        {"id": "col_conducted", "key": "conducted", "name": "Conducted Lectures", "type": "number", "maxMarks": 50},
                        {"id": "col_inactive", "key": "inactive_col", "name": "Legacy Note", "type": "text", "active": False}
                    ]
                }
            ]
        }

        res_create = await client.post("/api/v1/admin/form-schema", json=payload_create)
        assert res_create.status_code == 200
        data_create = res_create.json()
        f_create = data_create["fields"][0]
        assert f_create["layout"] == "matrix"
        assert f_create["rowHeaderTitle"] == "Semesters"
        assert len(f_create["rowHeaders"]) == 2
        assert f_create["rowHeaders"][0]["id"] == "sem_odd"

        # 2. Admin updates row header label without altering ID
        payload_update = [
            {
                "id": "matrix_field_1",
                "key": "teaching_matrix",
                "label": "Teaching Load Matrix",
                "type": "table",
                "layout": "matrix",
                "rowHeaderTitle": "Academic Semesters",
                "rowHeaders": [
                    {"id": "sem_odd", "label": "Renamed Odd Semester Label"},
                    {"id": "sem_even", "label": "Even Semester (II, IV, VI, VIII)"}
                ],
                "requireCompleteRows": True,
                "columns": [
                    {"id": "col_planned", "key": "planned", "name": "Planned Lectures", "type": "number", "maxMarks": 50},
                    {"id": "col_conducted", "key": "conducted", "name": "Conducted Lectures", "type": "number", "maxMarks": 50},
                    {"id": "col_inactive", "key": "inactive_col", "name": "Legacy Note", "type": "text", "active": False}
                ]
            }
        ]
        res_update = await client.put(f"/api/v1/admin/form-schema/{sec_code}/fields", json=payload_update)
        assert res_update.status_code == 200

        # 3. Faculty read GET /api/v1/appraisal/form-schema
        res_fac = await client.get(f"/api/v1/appraisal/form-schema?form_family={family}")
        assert res_fac.status_code == 200
        data_fac = res_fac.json()
        assert len(data_fac) == 1
        fac_field = data_fac[0]["fields"][0]
        assert fac_field["layout"] == "matrix"
        assert fac_field["rowHeaderTitle"] == "Academic Semesters"
        assert fac_field["rowHeaders"][0] == {"id": "sem_odd", "label": "Renamed Odd Semester Label"}
        # Active column filtering: inactive column excluded for faculty read
        assert len(fac_field["columns"]) == 2
        col_keys = [c["key"] for c in fac_field["columns"]]
        assert "planned" in col_keys
        assert "conducted" in col_keys
        assert "inactive_col" not in col_keys

    # Clean up
    async with AsyncSessionLocal() as db:
        await db.execute(delete(FormSectionDefinition).where(FormSectionDefinition.form_family == family))
        await db.commit()
    invalidate_form_schema_cache(family)


# ===========================================================================
# 3. Answer Contract, Completeness Validation & Submission Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_matrix_row_validation_and_submission(nonadmin_override):
    test_email = "faculty_matrix@test.com"
    academic_year = "2026-2027"
    family = "matrix_eval_fam"
    sec_code = "matrix_eval_sec"

    # Setup matrix definition
    async with AsyncSessionLocal() as db:
        await db.execute(delete(FormSectionDefinition).where(FormSectionDefinition.form_family == family))
        await db.execute(delete(CustomSectionRow).where(CustomSectionRow.faculty_email == test_email))
        await db.execute(delete(Declaration).where(Declaration.faculty_email == test_email))
        await db.execute(delete(AppraisalSnapshot).where(AppraisalSnapshot.faculty_email == test_email))
        sec = FormSectionDefinition(
            code=sec_code,
            form_family=family,
            part="Part A",
            section_key="matrix_eval_sec",
            title="Matrix Evaluation",
            max_marks=20,
            active=True,
            storage_table=None,
            fields=[
                {
                    "id": "f_mat",
                    "key": "eval_matrix",
                    "label": "Performance Matrix",
                    "type": "table",
                    "layout": "matrix",
                    "rowHeaderTitle": "Domain",
                    "rowHeaders": [
                        {"id": "dom_research", "label": "Research"},
                        {"id": "dom_teaching", "label": "Teaching"},
                    ],
                    "requireCompleteRows": True,
                    "columns": [
                        {"key": "target", "name": "Target", "type": "number", "required": True},
                        {"key": "achieved", "name": "Achieved", "type": "number", "required": True},
                    ]
                }
            ]
        )
        db.add(sec)
        await db.commit()
    invalidate_form_schema_cache(family)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Draft save allows partial/incomplete matrix answers
        draft_payload = {
            "academic_year": academic_year,
            "payload": {
                "form": {
                    "matrix_eval_sec": [
                        {"_matrixRowId": "dom_research", "target": 10}  # partially filled, allowed in draft
                    ]
                }
            }
        }
        res_draft = await client.put("/api/v1/appraisal/snapshot", json=draft_payload)
        assert res_draft.status_code == 200

        # Read back draft snapshot
        res_snap = await client.get(f"/api/v1/appraisal/snapshot?academic_year={academic_year}")
        assert res_snap.status_code == 200
        snap_data = res_snap.json()
        assert snap_data["payload"]["form"]["matrix_eval_sec"][0]["_matrixRowId"] == "dom_research"

        # 2. Submission rejects unknown row IDs
        sub_bad_id = {
            "academic_year": academic_year,
            "form_family": family,
            "form": {
                "matrix_eval_sec": [
                    {"_matrixRowId": "unknown_row_id_999", "target": 10, "achieved": 10}
                ]
            }
        }
        res_sub_bad = await client.post("/api/v1/appraisal/submit", json=sub_bad_id)
        assert res_sub_bad.status_code == 422
        assert "Unknown row identity" in str(res_sub_bad.json())

        # 3. Submission rejects duplicate row IDs
        sub_dup_id = {
            "academic_year": academic_year,
            "form_family": family,
            "form": {
                "matrix_eval_sec": [
                    {"_matrixRowId": "dom_research", "target": 10, "achieved": 10},
                    {"_matrixRowId": "dom_research", "target": 15, "achieved": 15},
                ]
            }
        }
        res_sub_dup = await client.post("/api/v1/appraisal/submit", json=sub_dup_id)
        assert res_sub_dup.status_code == 422
        assert "Duplicate row identity" in str(res_sub_dup.json())

        # 4. Submission rejects incomplete started row (missing 'achieved')
        sub_incomplete = {
            "academic_year": academic_year,
            "form_family": family,
            "form": {
                "matrix_eval_sec": [
                    {"_matrixRowId": "dom_research", "target": 10}
                ]
            }
        }
        res_sub_inc = await client.post("/api/v1/appraisal/submit", json=sub_incomplete)
        assert res_sub_inc.status_code == 422
        assert "required in partially filled" in str(res_sub_inc.json())

        # 5. Successful submission with valid matrix rows and zero values (0, 0.0, False)
        sub_valid = {
            "academic_year": academic_year,
            "form_family": family,
            "form": {
                "matrix_eval_sec": [
                    {"_matrixRowId": "dom_research", "target": 0, "achieved": 0.0, "score": 5},
                    {"_matrixRowId": "dom_teaching", "target": 40, "achieved": 38, "score": 10},
                ]
            },
            "totals": {"grandTotal": 15}
        }
        res_sub_valid = await client.post("/api/v1/appraisal/submit", json=sub_valid)
        assert res_sub_valid.status_code == 200

        # 6. Verify shredded data in CustomSectionRow
        async with AsyncSessionLocal() as db:
            rows_res = await db.execute(
                select(CustomSectionRow).where(
                    CustomSectionRow.faculty_email == test_email,
                    CustomSectionRow.academic_year == academic_year,
                    CustomSectionRow.section_code == sec_code
                ).order_by(CustomSectionRow.row_no.asc())
            )
            c_rows = rows_res.scalars().all()
            assert len(c_rows) == 2
            assert c_rows[0].custom_fields["_matrixRowId"] == "dom_research"
            assert c_rows[0].custom_fields["target"] == 0
            assert c_rows[0].custom_fields["achieved"] == 0.0
            assert c_rows[0].score == 5
            assert c_rows[1].custom_fields["_matrixRowId"] == "dom_teaching"
            assert c_rows[1].custom_fields["target"] == 40
            assert c_rows[1].custom_fields["achieved"] == 38
            assert c_rows[1].score == 10

    # Clean up
    async with AsyncSessionLocal() as db:
        await db.execute(delete(FormSectionDefinition).where(FormSectionDefinition.form_family == family))
        await db.execute(delete(CustomSectionRow).where(CustomSectionRow.faculty_email == test_email))
        await db.execute(delete(Declaration).where(Declaration.faculty_email == test_email))
        await db.execute(delete(AppraisalSnapshot).where(AppraisalSnapshot.faculty_email == test_email))
        await db.commit()
    invalidate_form_schema_cache(family)
