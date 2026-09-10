"""
Tests for the feedback endpoints.
POST /feedback                 — public, no auth required (JSON & multipart/form-data with optional attachments)
GET  /feedback                 — admin only
GET  /feedback/{id}            — admin only
GET  /feedback/{id}/attachment — admin only (file download)
"""

import os
import io
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete

from src.main import app
from src.setup.dependencies import User, get_current_user
from src.setup.database import AsyncSessionLocal
from src.models.core import Feedback
from src.api.v1.feedback import LOCAL_STORAGE_DIR

SENDER_EMAIL = "testfeedback@test.com"

VALID_PAYLOAD = {
    "name": "Test Sender",
    "email": SENDER_EMAIL,
    "category": "feedback",
    "subject": "Test subject line",
    "message": "This is a test feedback message.",
}


@pytest.fixture(autouse=True)
async def cleanup_feedback():
    yield
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(Feedback).where(Feedback.email == SENDER_EMAIL)
            )
            await db.commit()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# POST /feedback — public endpoint (JSON & Form)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_feedback_success_json():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/feedback", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "id" in body["feedback"]
    assert body["feedback"]["status"] == "new"
    assert body["feedback"]["has_attachment"] is False


@pytest.mark.asyncio
async def test_post_feedback_invalid_category():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/feedback", json={**VALID_PAYLOAD, "category": "totally_invalid"}
        )
    assert resp.status_code == 422
    assert "category" in resp.json()["errors"]


@pytest.mark.asyncio
async def test_post_feedback_missing_required_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/feedback", json={"name": "Only Name"})
    assert resp.status_code == 422
    errors = resp.json()["errors"]
    assert "email" in errors
    assert "category" in errors
    assert "subject" in errors
    assert "message" in errors


@pytest.mark.asyncio
async def test_post_feedback_invalid_email_format():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/feedback", json={**VALID_PAYLOAD, "email": "not-an-email"}
        )
    assert resp.status_code == 422
    assert "email" in resp.json()["errors"]


@pytest.mark.asyncio
async def test_post_feedback_all_valid_categories():
    valid_categories = ["query", "feedback", "bug", "suggestion", "other"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for cat in valid_categories:
            resp = await client.post(
                "/api/v1/feedback", json={**VALID_PAYLOAD, "category": cat}
            )
            assert resp.status_code == 200, f"Category '{cat}' should be accepted"


@pytest.mark.asyncio
async def test_post_feedback_multipart_no_file():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/feedback",
            data=VALID_PAYLOAD,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["feedback"]["has_attachment"] is False


@pytest.mark.asyncio
async def test_post_feedback_multipart_with_png():
    file_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/feedback",
            data=VALID_PAYLOAD,
            files={"attachment": ("error_screenshot.png", file_bytes, "image/png")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["feedback"]["has_attachment"] is True
    assert body["feedback"]["attachment"]["filename"] == "error_screenshot.png"
    assert body["feedback"]["attachment"]["content_type"] == "image/png"
    assert body["feedback"]["attachment"]["size"] == len(file_bytes)


@pytest.mark.asyncio
async def test_post_feedback_multipart_with_pdf_and_log():
    pdf_bytes = b"%PDF-1.4 test pdf content"
    log_bytes = b"2026-09-10 10:00:00 [ERROR] Null pointer exception"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Test PDF
        resp_pdf = await client.post(
            "/api/v1/feedback",
            data={**VALID_PAYLOAD, "category": "bug"},
            files={"attachment": ("error_report.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp_pdf.status_code == 200
        assert resp_pdf.json()["feedback"]["has_attachment"] is True

        # Test LOG
        resp_log = await client.post(
            "/api/v1/feedback",
            data={**VALID_PAYLOAD, "category": "bug"},
            files={"attachment": ("console.log", log_bytes, "text/plain")},
        )
        assert resp_log.status_code == 200
        assert resp_log.json()["feedback"]["has_attachment"] is True


@pytest.mark.asyncio
async def test_post_feedback_empty_file_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/feedback",
            data=VALID_PAYLOAD,
            files={"attachment": ("empty.png", b"", "image/png")},
        )
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert "attachment" in body["errors"]
    assert "empty" in body["errors"]["attachment"].lower()


@pytest.mark.asyncio
async def test_post_feedback_oversized_file_rejected():
    oversized_bytes = b"0" * (5 * 1024 * 1024 + 10)  # > 5 MB
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/feedback",
            data=VALID_PAYLOAD,
            files={"attachment": ("large.png", oversized_bytes, "image/png")},
        )
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert "attachment" in body["errors"]
    assert "5 mb" in body["errors"]["attachment"].lower()


@pytest.mark.asyncio
async def test_post_feedback_unsupported_file_extension_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/feedback",
            data=VALID_PAYLOAD,
            files={"attachment": ("exploit.exe", b"MZ\x90\x00", "application/octet-stream")},
        )
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert "attachment" in body["errors"]
    assert "unsupported" in body["errors"]["attachment"].lower()


# ---------------------------------------------------------------------------
# GET /feedback — admin only
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_feedback_no_auth_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/feedback")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_feedback_non_admin_returns_403():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        try:
            async def get_faculty():
                return User(id="fac-id", email="faculty_fb@test.com", roles=["faculty"])

            app.dependency_overrides[get_current_user] = get_faculty
            resp = await client.get("/api/v1/feedback")
        finally:
            app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_feedback_admin_returns_list_with_attachment_metadata():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Submit an entry with an attachment
        file_bytes = b"some test text file"
        post_resp = await client.post(
            "/api/v1/feedback",
            data=VALID_PAYLOAD,
            files={"attachment": ("note.txt", file_bytes, "text/plain")},
        )
        assert post_resp.status_code == 200
        fb_id = post_resp.json()["feedback"]["id"]

        try:
            async def get_admin():
                return User(id="admin-id", email="admin_fb@test.com", roles=["admin"])

            app.dependency_overrides[get_current_user] = get_admin
            resp = await client.get("/api/v1/feedback")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    target = next((item for item in items if item["id"] == fb_id), None)
    assert target is not None
    assert target["has_attachment"] is True
    assert target["attachment_filename"] == "note.txt"
    assert target["attachment_size"] == len(file_bytes)
    assert target["attachment_content_type"] == "text/plain"


@pytest.mark.asyncio
async def test_get_feedback_detail_admin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        file_bytes = b"detailed test file"
        post_resp = await client.post(
            "/api/v1/feedback",
            data=VALID_PAYLOAD,
            files={"attachment": ("info.txt", file_bytes, "text/plain")},
        )
        fb_id = post_resp.json()["feedback"]["id"]

        try:
            async def get_admin():
                return User(id="admin-id", email="admin_fb@test.com", roles=["admin"])

            app.dependency_overrides[get_current_user] = get_admin
            resp = await client.get(f"/api/v1/feedback/{fb_id}")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == fb_id
    assert data["has_attachment"] is True
    assert data["attachment_filename"] == "info.txt"
    assert data["attachment_size"] == len(file_bytes)


# ---------------------------------------------------------------------------
# GET /feedback/{feedback_id}/attachment — Download endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_download_feedback_attachment_success():
    file_bytes = b"binary attachment test content for download"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        post_resp = await client.post(
            "/api/v1/feedback",
            data=VALID_PAYLOAD,
            files={"attachment": ("test_doc.txt", file_bytes, "text/plain")},
        )
        fb_id = post_resp.json()["feedback"]["id"]

        try:
            async def get_admin():
                return User(id="admin-id", email="admin_fb@test.com", roles=["admin"])

            app.dependency_overrides[get_current_user] = get_admin
            resp = await client.get(f"/api/v1/feedback/{fb_id}/attachment")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.content == file_bytes
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert "test_doc.txt" in resp.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_download_feedback_attachment_non_admin_returns_403():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        post_resp = await client.post(
            "/api/v1/feedback",
            data=VALID_PAYLOAD,
            files={"attachment": ("doc.txt", b"content", "text/plain")},
        )
        fb_id = post_resp.json()["feedback"]["id"]

        try:
            async def get_faculty():
                return User(id="fac-id", email="faculty_fb@test.com", roles=["faculty"])

            app.dependency_overrides[get_current_user] = get_faculty
            resp = await client.get(f"/api/v1/feedback/{fb_id}/attachment")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_download_feedback_attachment_no_attachment_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        post_resp = await client.post("/api/v1/feedback", json=VALID_PAYLOAD)
        fb_id = post_resp.json()["feedback"]["id"]

        try:
            async def get_admin():
                return User(id="admin-id", email="admin_fb@test.com", roles=["admin"])

            app.dependency_overrides[get_current_user] = get_admin
            resp = await client.get(f"/api/v1/feedback/{fb_id}/attachment")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 404
    assert "has no attachment" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_download_feedback_attachment_nonexistent_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        try:
            async def get_admin():
                return User(id="admin-id", email="admin_fb@test.com", roles=["admin"])

            app.dependency_overrides[get_current_user] = get_admin
            resp = await client.get("/api/v1/feedback/00000000-0000-0000-0000-000000000000/attachment")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_feedback_rollback_cleans_up_file():
    from sqlalchemy.ext.asyncio import AsyncSession
    file_bytes = b"temporary file that should be cleaned up on error"

    with patch.object(AsyncSession, "commit", side_effect=Exception("Database commit error")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/feedback",
                data=VALID_PAYLOAD,
                files={"attachment": ("cleanup_test.txt", file_bytes, "text/plain")},
            )
            assert resp.status_code == 500

    feedback_dir = os.path.join(LOCAL_STORAGE_DIR, "feedback")
    if os.path.exists(feedback_dir):
        for f in os.listdir(feedback_dir):
            file_p = os.path.join(feedback_dir, f)
            if os.path.isfile(file_p):
                with open(file_p, "rb") as fh:
                    assert fh.read() != file_bytes, f"Found leaked file {file_p} after failed commit!"
