import pytest
from httpx import AsyncClient
from sqlalchemy import select
from src.setup.database import AsyncSessionLocal
from src.models.core import FacultyProfile
from src.setup.local_auth import get_password_hash

FACULTY_EMAIL = "profile_pic_faculty@test.com"
PASSWORD = "password"

async def _seed_faculty():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FacultyProfile).where(FacultyProfile.email == FACULTY_EMAIL)
        )
        if not result.scalar_one_or_none():
            db.add(
                FacultyProfile(
                    email=FACULTY_EMAIL,
                    password_hash=get_password_hash(PASSWORD),
                    full_name="Profile Pic Faculty",
                    appraisal_role="faculty",
                    school="SoCSEA",
                    department="Computer Science",
                    is_verified=True,
                )
            )
            await db.commit()

@pytest.fixture
async def auth_headers(client: AsyncClient):
    await _seed_faculty()
    login = await client.post(
        "/api/v1/auth/login", json={"email": FACULTY_EMAIL, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['token']}"}

@pytest.mark.asyncio
async def test_get_me_includes_profile_picture_url(client: AsyncClient, auth_headers: dict):
    # GET /auth/me
    res = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert res.status_code == 200
    assert "profile_picture_url" in res.json()
    assert res.json()["profile_picture_url"] is None

@pytest.mark.asyncio
async def test_update_me_accepts_profile_picture_url(client: AsyncClient, auth_headers: dict):
    # PUT /auth/me
    test_url = "https://example.com/some-image.png"
    res = await client.put(
        "/api/v1/auth/me",
        json={"profile_picture_url": test_url},
        headers=auth_headers
    )
    assert res.status_code == 200
    assert res.json()["profile_picture_url"] == test_url

    # Verify GET returns it
    res = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert res.json()["profile_picture_url"] == test_url

@pytest.mark.asyncio
async def test_upload_profile_picture_success(client: AsyncClient, auth_headers: dict):
    # POST /auth/me/profile-picture
    files = {"file": ("avatar.png", b"fake image content", "image/png")}
    res = await client.post(
        "/api/v1/auth/me/profile-picture",
        files=files,
        headers=auth_headers
    )
    assert res.status_code == 200
    assert "profile_picture_url" in res.json()
    assert res.json()["profile_picture_url"].startswith("/api/v1/upload/view/profile_pictures/")

    # Verify database state
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(FacultyProfile).where(FacultyProfile.email == FACULTY_EMAIL)
        )
        user = result.scalar_one()
        assert user.profile_picture_url == res.json()["profile_picture_url"]

@pytest.mark.asyncio
async def test_upload_profile_picture_invalid_type(client: AsyncClient, auth_headers: dict):
    # POST /auth/me/profile-picture with a text file
    files = {"file": ("document.txt", b"plain text", "text/plain")}
    res = await client.post(
        "/api/v1/auth/me/profile-picture",
        files=files,
        headers=auth_headers
    )
    assert res.status_code == 400
    assert "Invalid file type" in res.json()["user_message"]
