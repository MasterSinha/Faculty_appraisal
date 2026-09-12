"""
Comprehensive Test Suite for Dynamic Appraisal Form Builder Backend.
Tests:
- Column maximum normalization (§2)
- Field key locking (§4)
- Part creation, sequencing, and deletion semantics (§1 & §3)
- Table-order sorting with stable fallback (§1)
- Admin schema endpoints: GET, POST, PUT, DELETE (§5)
- Faculty schema read endpoint with server-side active filtering (§5)
- Custom section row persistence and custom_fields JSONB (§3)
"""

import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

from src.main import app
from src.setup.database import AsyncSessionLocal
from src.setup.dependencies import User, get_current_user
from src.models.core import FormSectionDefinition, CustomSectionRow, FacultyProfile
from src.models.part_a import TeachingProcess
from src.setup.form_schema_utils import (
    slugify_key,
    normalize_column_schema,
    normalize_field_schema,
    validate_and_normalize_fields,
    sort_sections_with_table_order,
    filter_active_form_schema
)


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
        return User(id="user-test-id", email="faculty1@test.com", roles=["faculty"], school="SoCSEA")

    app.dependency_overrides[get_current_user] = get_nonadmin
    yield
    app.dependency_overrides.clear()


# ===========================================================================
# 1. Unit Tests for Normalization & Schema Helpers (§2, §4, §1)
# ===========================================================================

def test_slugify_key():
    assert slugify_key("Publication Title") == "publication_title"
    assert slugify_key("Research / Consultancy Projects") == "research_consultancy_projects"
    assert slugify_key("  Special & Characters #123!  ") == "special_characters_123"
    assert slugify_key("") == "field"
    assert slugify_key(None) == "field"


def test_column_maximum_unbounded_numeric():
    # Unbounded numeric column: maxMarks = null or omitted -> stored as null, not 0
    col1 = {"name": "Count", "type": "integer"}
    norm1 = normalize_column_schema(col1)
    assert norm1["maxMarks"] is None
    assert norm1["max_marks"] is None

    col2 = {"name": "Score", "type": "number", "maxMarks": None}
    norm2 = normalize_column_schema(col2)
    assert norm2["maxMarks"] is None
    assert norm2["max_marks"] is None

    col3 = {"name": "Blank", "type": "number", "maxMarks": ""}
    norm3 = normalize_column_schema(col3)
    assert norm3["maxMarks"] is None
    assert norm3["max_marks"] is None


def test_column_maximum_configured_numeric():
    # Configured numeric maximum: maxMarks = 10 -> preserved
    col = {"name": "Marks", "type": "number", "maxMarks": 10}
    norm = normalize_column_schema(col)
    assert norm["maxMarks"] == 10
    assert norm["max_marks"] == 10

    # Decimal maximum
    col_dec = {"name": "Score", "type": "number", "maxMarks": 15.5}
    norm_dec = normalize_column_schema(col_dec)
    assert norm_dec["maxMarks"] == 15.5
    assert norm_dec["max_marks"] == 15.5


def test_column_maximum_explicit_zero():
    # Explicit zero: maxMarks = 0 -> preserved as 0, NOT null
    col = {"name": "Zero Max", "type": "integer", "maxMarks": 0}
    norm = normalize_column_schema(col)
    assert norm["maxMarks"] == 0
    assert norm["max_marks"] == 0
    assert norm["maxMarks"] is not None


def test_column_maximum_numeric_to_text_clears_maximum():
    # Changing a numeric column to non-numeric type clears maximum to null
    col_text = {"name": "Description", "type": "text", "maxMarks": 25}
    norm = normalize_column_schema(col_text)
    assert norm["maxMarks"] is None
    assert norm["max_marks"] is None


def test_column_maximum_between_numeric_types_preserves():
    # Changing between integer and number preserves configured maximum
    col_int = {"name": "Count", "type": "integer", "maxMarks": 40}
    norm_int = normalize_column_schema(col_int)
    assert norm_int["maxMarks"] == 40

    col_num = {"name": "Count", "type": "number", "maxMarks": norm_int["maxMarks"]}
    norm_num = normalize_column_schema(col_num)
    assert norm_num["maxMarks"] == 40


def test_column_maximum_stale_legacy_nonnumeric():
    # Tolerate stale non-numeric maximum in legacy data by normalizing to null
    col_legacy = {"name": "Old Col", "type": "number", "maxMarks": "invalid_string"}
    norm = normalize_column_schema(col_legacy, strict=False)
    assert norm["maxMarks"] is None
    assert norm["max_marks"] is None


def test_field_key_locking_validation():
    # First save: derive stable wire key
    existing_fields = [
        {
            "id": "f_1",
            "key": "publication_title",
            "label": "Publication Title",
            "type": "text",
            "isCustom": False,
            "active": True
        },
        {
            "id": "f_2",
            "key": "custom_metric",
            "label": "Custom Metric",
            "type": "number",
            "isCustom": True,
            "active": True
        }
    ]

    # Valid update: same keys, label updated
    updated_valid = [
        {
            "id": "f_1",
            "key": "publication_title",
            "label": "Updated Publication Title",
            "type": "text",
            "isCustom": False,
            "active": True
        },
        {
            "id": "f_2",
            "key": "custom_metric",
            "label": "Custom Metric Updated",
            "type": "number",
            "isCustom": True,
            "active": True
        }
    ]
    res_valid = validate_and_normalize_fields(existing_fields, updated_valid, strict=True)
    assert len(res_valid) == 2
    assert res_valid[0]["label"] == "Updated Publication Title"

    # Invalid update: attempting to rename key 'publication_title' to 'pub_name' -> raises 400
    updated_invalid = [
        {
            "id": "f_1",
            "key": "pub_name",  # Renamed key!
            "label": "Publication Title",
            "type": "text",
            "isCustom": False,
            "active": True
        }
    ]
    with pytest.raises(Exception) as exc_info:
        validate_and_normalize_fields(existing_fields, updated_invalid, strict=True)
    assert "locked and cannot be renamed" in str(exc_info.value)


def test_core_field_retire_semantics():
    # Core fields (isCustom: False) cannot be hard deleted; they become active: False
    existing_fields = [
        {
            "id": "f_core",
            "key": "semester",
            "label": "Semester",
            "type": "text",
            "isCustom": False,
            "active": True
        },
        {
            "id": "f_custom",
            "key": "extra_note",
            "label": "Extra Note",
            "type": "text",
            "isCustom": True,
            "active": True
        }
    ]

    # User omits both f_core and f_custom, adds new field
    updated = [
        {
            "key": "brand_new",
            "label": "Brand New Field",
            "type": "text",
            "isCustom": True,
            "active": True
        }
    ]

    res = validate_and_normalize_fields(existing_fields, updated, strict=True)
    # Core field 'semester' must be retained with active: False
    core_retired = next(f for f in res if f["key"] == "semester")
    assert core_retired["active"] is False
    assert core_retired["isCustom"] is False

    # Custom field 'extra_note' can be removed
    assert not any(f["key"] == "extra_note" for f in res)


def test_table_order_sorting():
    sections = [
        {"code": "sec_c", "title": "Section C"},
        {"code": "sec_a", "title": "Section A"},
        {"code": "sec_b", "title": "Section B"},
        {"code": "sec_d", "title": "Section D"},
    ]
    # tableOrder explicitly orders sec_b, then sec_a. Missing IDs (sec_c, sec_d) follow in stable order.
    table_order = ["sec_b", "sec_a"]
    sorted_res = sort_sections_with_table_order(sections, table_order)
    codes = [s["code"] for s in sorted_res]
    assert codes == ["sec_b", "sec_a", "sec_c", "sec_d"]


# ===========================================================================
# 2. Integration Tests for Admin Form Schema Endpoints (§5)
# ===========================================================================

@pytest.mark.asyncio
async def test_admin_create_custom_section(admin_override):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "code": "custom_research_metrics_50",
            "form_family": "standard",
            "part": "Part F",
            "section_key": "customMetrics",
            "title": "F1. Custom Research Metrics",
            "max_marks": 50,
            "fields": [
                {
                    "label": "Metric Name",
                    "type": "text",
                    "required": True
                },
                {
                    "label": "Metric Table",
                    "type": "table",
                    "columns": [
                        {"name": "Parameter", "type": "text", "maxMarks": None},
                        {"name": "Count", "type": "integer", "maxMarks": None},
                        {"name": "Score", "type": "number", "maxMarks": 25}
                    ]
                }
            ]
        }
        resp = await client.post("/api/v1/admin/form-schema", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "custom_research_metrics_50"
        assert data["part"] == "Part F"
        assert data["storage_table"] is None  # Custom section has storage_table NULL
        assert len(data["fields"]) == 2
        assert data["fields"][0]["key"] == "metric_name"
        assert data["fields"][0]["isCustom"] is True
        assert data["fields"][1]["columns"][2]["maxMarks"] == 25


@pytest.mark.asyncio
async def test_admin_list_form_schemas(admin_override):
    async with AsyncSessionLocal() as db:
        sec = FormSectionDefinition(
            code="test_sec_list_1",
            form_family="test_family",
            part="Bonus Section",
            section_key="bonusSec",
            title="Bonus Activities",
            max_marks=20,
            storage_table=None,
            fields=[{"key": "activity", "label": "Activity", "type": "text", "active": True}],
            active=True,
            order=1
        )
        db.add(sec)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Filter by form_family
        resp = await client.get("/api/v1/admin/form-schema?form_family=test_family")
        assert resp.status_code == 200
        items = resp.json()
        assert any(item["code"] == "test_sec_list_1" for item in items)
        matched = next(item for item in items if item["code"] == "test_sec_list_1")
        assert matched["part"] == "Bonus Section"
        assert matched["maxMarks"] == 20


@pytest.mark.asyncio
async def test_admin_update_section_metadata(admin_override):
    async with AsyncSessionLocal() as db:
        sec = FormSectionDefinition(
            code="test_sec_update_meta",
            form_family="standard",
            part="Part A",
            section_key="testMeta",
            title="Initial Title",
            max_marks=10,
            active=True
        )
        db.add(sec)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        update_payload = {
            "title": "Renamed Title",
            "maxMarks": 15,
            "part": "Part G",
            "active": False
        }
        resp = await client.put("/api/v1/admin/form-schema/test_sec_update_meta", json=update_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Renamed Title"
        assert data["maxMarks"] == 15
        assert data["part"] == "Part G"
        assert data["active"] is False


@pytest.mark.asyncio
async def test_admin_update_section_fields_key_lock_enforcement(admin_override):
    async with AsyncSessionLocal() as db:
        sec = FormSectionDefinition(
            code="test_sec_fields_lock",
            form_family="standard",
            part="Part B",
            section_key="testLock",
            title="Lock Test Section",
            max_marks=10,
            fields=[
                {"id": "col_1", "key": "locked_key", "label": "Locked Field", "type": "text", "isCustom": True, "active": True}
            ]
        )
        db.add(sec)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Attempt to rename 'locked_key' -> must fail with 400
        bad_payload = {
            "fields": [
                {"id": "col_1", "key": "renamed_key", "label": "Locked Field", "type": "text", "isCustom": True, "active": True}
            ]
        }
        resp = await client.put("/api/v1/admin/form-schema/test_sec_fields_lock/fields", json=bad_payload)
        assert resp.status_code == 400
        assert "locked and cannot be renamed" in resp.text

        # Valid update: keep same key, update type & columns
        good_payload = {
            "fields": [
                {
                    "id": "col_1",
                    "key": "locked_key",
                    "label": "Locked Field Updated",
                    "type": "table",
                    "columns": [
                        {"name": "Col A", "type": "integer", "maxMarks": 5}
                    ]
                }
            ]
        }
        resp_good = await client.put("/api/v1/admin/form-schema/test_sec_fields_lock/fields", json=good_payload)
        assert resp_good.status_code == 200
        assert resp_good.json()["fields"][0]["key"] == "locked_key"
        assert resp_good.json()["fields"][0]["columns"][0]["maxMarks"] == 5


@pytest.mark.asyncio
async def test_admin_delete_custom_vs_core_section(admin_override):
    async with AsyncSessionLocal() as db:
        # 1. Custom section (storage_table IS NULL)
        custom_sec = FormSectionDefinition(
            code="test_custom_sec_del",
            form_family="standard",
            part="Part X",
            section_key="custDel",
            title="Custom to Delete",
            max_marks=10,
            storage_table=None,
            active=True
        )
        # 2. Core section (storage_table IS NOT NULL)
        core_sec = FormSectionDefinition(
            code="test_core_sec_del",
            form_family="standard",
            part="Part A",
            section_key="coreDel",
            title="Core to Retire",
            max_marks=50,
            storage_table="teaching_process",
            active=True
        )
        db.add_all([custom_sec, core_sec])
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Delete custom section -> deleted from DB
        resp_cust = await client.delete("/api/v1/admin/form-schema/test_custom_sec_del")
        assert resp_cust.status_code == 200
        assert resp_cust.json()["action"] == "deleted"

        # Delete core section -> retired (active = False)
        resp_core = await client.delete("/api/v1/admin/form-schema/test_core_sec_del")
        assert resp_core.status_code == 200
        assert resp_core.json()["action"] == "retired"

    # Verify DB state
    async with AsyncSessionLocal() as db:
        c_res = await db.execute(select(FormSectionDefinition).where(FormSectionDefinition.code == "test_custom_sec_del"))
        assert c_res.scalar_one_or_none() is None

        core_res = await db.execute(select(FormSectionDefinition).where(FormSectionDefinition.code == "test_core_sec_del"))
        core_obj = core_res.scalar_one_or_none()
        assert core_obj is not None
        assert core_obj.active is False


@pytest.mark.asyncio
async def test_non_admin_forbidden(nonadmin_override):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/admin/form-schema")
        assert resp.status_code == 403


# ===========================================================================
# 3. Faculty Read Endpoint & Active Server-Side Filtering (§5)
# ===========================================================================

@pytest.mark.asyncio
async def test_faculty_read_form_schema_active_filtering(nonadmin_override):
    async with AsyncSessionLocal() as db:
        # Active section with 1 active field and 1 inactive field
        sec_active = FormSectionDefinition(
            code="test_fac_active_sec",
            form_family="standard",
            part="Part A",
            section_key="activeSec",
            title="Active Section",
            max_marks=30,
            active=True,
            fields=[
                {"key": "f_act", "label": "Active Field", "type": "text", "active": True},
                {"key": "f_inact", "label": "Inactive Field", "type": "text", "active": False}
            ]
        )
        # Inactive section
        sec_inactive = FormSectionDefinition(
            code="test_fac_inactive_sec",
            form_family="standard",
            part="Part A",
            section_key="inactSec",
            title="Inactive Section",
            max_marks=20,
            active=False,
            fields=[{"key": "f1", "label": "F1", "type": "text", "active": True}]
        )
        db.add_all([sec_active, sec_inactive])
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/appraisal/form-schema?form_family=standard")
        assert resp.status_code == 200
        data = resp.json()

        # Inactive section should NOT be present
        assert not any(s["code"] == "test_fac_inactive_sec" for s in data)

        # Active section should be present, but only with active fields
        matched = next(s for s in data if s["code"] == "test_fac_active_sec")
        field_keys = [f["key"] for f in matched["fields"]]
        assert "f_act" in field_keys
        assert "f_inact" not in field_keys


# ===========================================================================
# 4. Submission & Data Shredding into custom_section_rows & custom_fields (§3)
# ===========================================================================

@pytest.mark.asyncio
async def test_submit_custom_section_rows_and_custom_fields(nonadmin_override):
    test_email = "faculty1@test.com"
    academic_year = "2026-2027"

    async with AsyncSessionLocal() as db:
        # Register custom section definition
        c_sec = FormSectionDefinition(
            code="custom_innovations_30",
            form_family="standard",
            part="Part F",
            section_key="customInnovations",
            title="Custom Innovations",
            max_marks=30,
            storage_table=None,
            active=True,
            fields=[
                {"key": "innovation_title", "label": "Title", "type": "text"},
                {"key": "impact_level", "label": "Impact Level", "type": "text"}
            ]
        )
        db.add(c_sec)

        # Create faculty profile
        prof = FacultyProfile(
            email=test_email,
            full_name="Dr. Test User",
            appraisal_role="faculty",
            school="SoCSEA",
            department="CS",
            academic_year=academic_year
        )
        db.add(prof)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        submit_payload = {
            "academic_year": academic_year,
            "form": {
                # 1. Physical table (teaching_process) with core SQL columns + extra custom field
                "lectures": [
                    {
                        "semester": "Semester 1",
                        "course_code": "CS101",
                        "planned_classes": 40,
                        "conducted_classes": 38,
                        "score": 45,
                        "admin_custom_note": "Extra admin added column note"
                    }
                ],
                # 2. Custom dynamic section
                "customInnovations": [
                    {
                        "innovation_title": "AI Tutoring Engine",
                        "impact_level": "University Wide",
                        "score": 25,
                        "hod_score": 25
                    }
                ]
            },
            "totals": {
                "partATotal": 45,
                "partBTotal": 0,
                "partCTotal": 0,
                "partDTotal": 0,
                "grandTotal": 70
            }
        }
        resp = await client.post("/api/v1/appraisal/submit", json=submit_payload)
        assert resp.status_code == 200

    # Verify Database Shredding
    async with AsyncSessionLocal() as db:
        # Check physical table custom_fields JSONB
        tp_res = await db.execute(
            select(TeachingProcess).where(
                TeachingProcess.faculty_email == test_email,
                TeachingProcess.academic_year == academic_year
            )
        )
        tp_row = tp_res.scalar_one_or_none()
        assert tp_row is not None
        assert tp_row.course_code == "CS101"
        assert tp_row.custom_fields.get("admin_custom_note") == "Extra admin added column note"

        # Check custom_section_rows table
        c_res = await db.execute(
            select(CustomSectionRow).where(
                CustomSectionRow.faculty_email == test_email,
                CustomSectionRow.academic_year == academic_year,
                CustomSectionRow.section_code == "custom_innovations_30"
            )
        )
        c_row = c_res.scalar_one_or_none()
        assert c_row is not None
        assert c_row.score == 25
        assert c_row.hod_score == 25
        assert c_row.custom_fields["innovation_title"] == "AI Tutoring Engine"
        assert c_row.custom_fields["impact_level"] == "University Wide"
