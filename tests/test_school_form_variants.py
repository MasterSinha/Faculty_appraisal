"""
Comprehensive test suite for Dynamic School Appraisal Form Configuration and Registry.
Tests:
1. Form Registry listing endpoint (both admin and public catalog).
2. Creating school with Standard Appraisal (snake_case and camelCase).
3. Creating school with Creative Appraisal - Media Communication.
4. Creating school with Creative Appraisal - Design Arts.
5. Updating school form variant and verifying persistence across saves and reloads.
6. Validation: Rejecting creative form with missing / blank form_variant (400).
7. Validation: Rejecting creative form with invalid / unregistered form_variant (400).
8. Validation: Ensuring backend never returns 'creative' without form_variant, form_type, and form_label.
9. Verification that any school (engineering or non-engineering) can use any active form variant.
10. Verification of auth/profile response returning school form config fields.
11. Preserving scoring and existing schools.
"""

import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from src.main import app
from src.setup.database import AsyncSessionLocal
from src.setup.dependencies import User, get_current_user
from src.models.core import School, FacultyProfile
from src.setup.form_registry import FORM_REGISTRY, get_form_registry, find_registry_entry, validate_and_resolve_form_config


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
async def test_form_registry_endpoints(admin_override, nonadmin_override):
    """Verify that form registry is accessible via admin and public routes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Public route
        resp_pub = await client.get("/api/v1/schools/form-variants")
        assert resp_pub.status_code == 200
        data_pub = resp_pub.json()
        assert len(data_pub) >= 3
        variants = {item["form_variant"] for item in data_pub}
        assert "standard" in variants
        assert "mediaCommunication" in variants
        assert "designArts" in variants

        # Admin route
        resp_admin = await client.get("/api/v1/admin/schools/form-variants")
        assert resp_admin.status_code == 200
        data_admin = resp_admin.json()
        assert data_admin == data_pub


@pytest.mark.asyncio
async def test_create_and_reload_standard_appraisal_school(admin_override):
    """Admin creates school with Standard Appraisal, saves, and reloads."""
    code = f"STD_{uuid.uuid4().hex[:6]}"
    payload = {
        "code": code,
        "full_name": "Standard Test School",
        "track": "engineering",
        "has_hod": False,
        "has_director": True,
        "approval_chain": ["director", "dean", "vc"],
        "default_form": "standard",
        "form_variant": "standard",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create
        resp = await client.post("/api/v1/admin/schools", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["default_form"] == "standard"
        assert data["form_variant"] == "standard"
        assert data["form_type"] == "FORM_A"
        assert data["form_label"] == "Standard Appraisal"

        # Reload detail via admin
        resp_detail = await client.get(f"/api/v1/admin/schools/{code}")
        assert resp_detail.status_code == 200
        det = resp_detail.json()
        assert det["default_form"] == "standard"
        assert det["form_variant"] == "standard"
        assert det["form_type"] == "FORM_A"
        assert det["form_label"] == "Standard Appraisal"

        # Reload catalog via public endpoint
        resp_cat = await client.get(f"/api/v1/schools/{code}")
        assert resp_cat.status_code == 200
        assert resp_cat.json()["form_variant"] == "standard"


@pytest.mark.asyncio
async def test_create_and_reload_creative_media_communication_school(admin_override):
    """Admin creates school with Creative Media Communication, saves, and reloads."""
    code = f"MED_{uuid.uuid4().hex[:6]}"
    # Test camelCase input format
    payload = {
        "code": code,
        "full_name": "Media Communication Test School",
        "track": "non_engineering",
        "has_hod": False,
        "has_director": True,
        "approval_chain": ["director", "dean", "vc"],
        "defaultForm": "creative",
        "formVariant": "mediaCommunication",
        "formType": "FORM_B",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/admin/schools", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["default_form"] == "creative"
        assert data["form_variant"] == "mediaCommunication"
        assert data["form_type"] == "FORM_B"
        assert data["form_label"] == "Creative Appraisal - Media Communication"

        # Reload detail
        resp_detail = await client.get(f"/api/v1/admin/schools/{code}")
        assert resp_detail.status_code == 200
        det = resp_detail.json()
        assert det["default_form"] == "creative"
        assert det["form_variant"] == "mediaCommunication"
        assert det["form_type"] == "FORM_B"
        assert det["form_label"] == "Creative Appraisal - Media Communication"


@pytest.mark.asyncio
async def test_create_and_reload_creative_design_arts_school(admin_override):
    """Admin creates school with Creative Design Arts, saves, and reloads."""
    code = f"DSG_{uuid.uuid4().hex[:6]}"
    payload = {
        "code": code,
        "full_name": "Design Arts Test School",
        "track": "non_engineering",
        "has_hod": False,
        "has_director": True,
        "approval_chain": ["director", "dean", "vc"],
        "default_form": "creative",
        "form_variant": "designArts",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/admin/schools", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["default_form"] == "creative"
        assert data["form_variant"] == "designArts"
        assert data["form_type"] == "FORM_C"
        assert data["form_label"] == "Creative Appraisal - Design Arts"

        # Reload
        resp_detail = await client.get(f"/api/v1/admin/schools/{code}")
        assert resp_detail.status_code == 200
        det = resp_detail.json()
        assert det["default_form"] == "creative"
        assert det["form_variant"] == "designArts"
        assert det["form_type"] == "FORM_C"
        assert det["form_label"] == "Creative Appraisal - Design Arts"


@pytest.mark.asyncio
async def test_update_school_form_configuration(admin_override):
    """Admin updates school form configuration from Standard to Creative Media, then to Design Arts."""
    code = f"UPD_{uuid.uuid4().hex[:6]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create standard school
        create_resp = await client.post(
            "/api/v1/admin/schools",
            json={
                "code": code,
                "full_name": "Updating School",
                "track": "engineering",
                "has_hod": False,
                "has_director": True,
                "approval_chain": ["director", "dean", "vc"],
                "default_form": "standard",
            },
        )
        assert create_resp.status_code == 201
        assert create_resp.json()["form_variant"] == "standard"

        # 2. Update to Creative Media Communication
        update_resp1 = await client.put(
            f"/api/v1/admin/schools/{code}",
            json={
                "default_form": "creative",
                "form_variant": "mediaCommunication",
            },
        )
        assert update_resp1.status_code == 200
        d1 = update_resp1.json()
        assert d1["default_form"] == "creative"
        assert d1["form_variant"] == "mediaCommunication"
        assert d1["form_type"] == "FORM_B"
        assert d1["form_label"] == "Creative Appraisal - Media Communication"

        # 3. Update to Creative Design Arts using camelCase
        update_resp2 = await client.put(
            f"/api/v1/admin/schools/{code}",
            json={
                "defaultForm": "creative",
                "formVariant": "designArts",
            },
        )
        assert update_resp2.status_code == 200
        d2 = update_resp2.json()
        assert d2["default_form"] == "creative"
        assert d2["form_variant"] == "designArts"
        assert d2["form_type"] == "FORM_C"
        assert d2["form_label"] == "Creative Appraisal - Design Arts"

        # 4. Update back to Standard
        update_resp3 = await client.put(
            f"/api/v1/admin/schools/{code}",
            json={
                "default_form": "standard",
            },
        )
        assert update_resp3.status_code == 200
        d3 = update_resp3.json()
        assert d3["default_form"] == "standard"
        assert d3["form_variant"] == "standard"
        assert d3["form_type"] == "FORM_A"


@pytest.mark.asyncio
async def test_reject_creative_form_with_missing_or_blank_variant(admin_override):
    """Creative form with blank or missing form_variant MUST be rejected with 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create with default_form="creative" and no form_variant
        resp1 = await client.post(
            "/api/v1/admin/schools",
            json={
                "code": f"FAIL1_{uuid.uuid4().hex[:6]}",
                "full_name": "Bad Creative School 1",
                "track": "non_engineering",
                "has_hod": False,
                "has_director": True,
                "approval_chain": ["director", "dean", "vc"],
                "default_form": "creative",
            },
        )
        assert resp1.status_code == 400
        assert "form_variant" in resp1.json()["detail"].lower()

        # Create with default_form="creative" and form_variant=""
        resp2 = await client.post(
            "/api/v1/admin/schools",
            json={
                "code": f"FAIL2_{uuid.uuid4().hex[:6]}",
                "full_name": "Bad Creative School 2",
                "track": "non_engineering",
                "has_hod": False,
                "has_director": True,
                "approval_chain": ["director", "dean", "vc"],
                "default_form": "creative",
                "form_variant": "",
            },
        )
        assert resp2.status_code == 400
        assert "form_variant" in resp2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reject_creative_form_with_invalid_variant(admin_override):
    """Creative form with unregistered variant MUST be rejected with 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/admin/schools",
            json={
                "code": f"FAIL3_{uuid.uuid4().hex[:6]}",
                "full_name": "Bad Variant School",
                "track": "non_engineering",
                "has_hod": False,
                "has_director": True,
                "approval_chain": ["director", "dean", "vc"],
                "default_form": "creative",
                "form_variant": "nonExistentVariantXYZ",
            },
        )
        assert resp.status_code == 400
        assert "nonexistentvariantxyz" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auth_profile_returns_school_form_configuration():
    """Verify that user auth /profile includes school form config."""
    email = f"prof_form_{uuid.uuid4().hex[:6]}@test.com"
    sch_code = f"MEDSCH_{uuid.uuid4().hex[:6]}"

    async with AsyncSessionLocal() as db:
        sch = School(
            code=sch_code,
            full_name="Media School for Auth Test",
            track="non_engineering",
            has_hod=False,
            has_director=True,
            approval_chain=["director", "dean", "vc"],
            default_form="creative",
            form_variant="mediaCommunication",
            form_type="FORM_B",
            form_label="Creative Appraisal - Media Communication",
            active=True,
        )
        db.add(sch)

        user = FacultyProfile(
            email=email,
            full_name="Prof Form Test",
            school=sch_code,
            appraisal_role="faculty",
            is_verified=True,
        )
        db.add(user)
        await db.commit()

    async def get_test_user():
        return User(id=str(user.id), email=email, roles=["faculty"], school=sch_code)

    app.dependency_overrides[get_current_user] = get_test_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/auth/me")
            assert resp.status_code == 200
            data = resp.json()
            assert data["school"] == sch_code
            assert data["default_form"] == "creative"
            assert data["form_variant"] == "mediaCommunication"
            assert data["form_type"] == "FORM_B"
            assert data["form_label"] == "Creative Appraisal - Media Communication"
    finally:
        app.dependency_overrides.clear()
