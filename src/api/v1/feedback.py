import os
import re
import uuid
import logging
from typing import Optional, Dict, Any

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.setup.database import get_db
from src.setup.dependencies import CurrentUser
from src.models.core import Feedback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["Feedback"])

VALID_CATEGORIES = frozenset({"query", "feedback", "bug", "suggestion", "other"})
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

ALLOWED_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".pdf", ".txt", ".log"})
ALLOWED_MIME_TYPES = frozenset({
    "image/png",
    "image/jpeg",
    "image/pjpeg",
    "image/webp",
    "application/pdf",
    "text/plain",
    "text/x-log",
    "text/log",
    "application/octet-stream",
})
MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024  # 5 MiB (5,242,880 bytes)
LOCAL_STORAGE_DIR = os.getenv("LOCAL_STORAGE_DIR", "./uploads")


def _get_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _validate(data: Dict[str, Any]) -> Dict[str, str]:
    errors: Dict[str, str] = {}

    email = (data.get("email") or "").strip()
    category = (data.get("category") or "").strip()
    subject = (data.get("subject") or "").strip()
    message = (data.get("message") or "").strip()
    name = (data.get("name") or "").strip()

    if not email:
        errors["email"] = "Email is required."
    elif len(email) > 254:
        errors["email"] = "Email must be 254 characters or less."
    elif not _EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."

    if not category:
        errors["category"] = "Category is required."
    elif category not in VALID_CATEGORIES:
        errors["category"] = f"Category must be one of: {', '.join(sorted(VALID_CATEGORIES))}."

    if not subject:
        errors["subject"] = "Subject is required."
    elif len(subject) > 120:
        errors["subject"] = "Subject must be 120 characters or less."

    if not message:
        errors["message"] = "Message is required."
    elif len(message) > 5000:
        errors["message"] = "Message must be 5000 characters or less."

    if name and len(name) > 80:
        errors["name"] = "Name must be 80 characters or less."

    return errors


def _require_admin(current_user):
    if not any(r in current_user.roles for r in ("admin", "super_admin")):
        raise HTTPException(status_code=403, detail="Admin role required")


# --- Public endpoint: anyone can submit ---

@router.post("")
async def create_feedback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    content_type = request.headers.get("content-type", "").lower()
    data: Dict[str, Any] = {}
    attachment_file: Optional[UploadFile] = None

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        data = {
            "name": form.get("name"),
            "email": form.get("email"),
            "category": form.get("category"),
            "subject": form.get("subject"),
            "message": form.get("message"),
        }
        raw_attachment = form.get("attachment")
        if raw_attachment is not None and hasattr(raw_attachment, "filename") and raw_attachment.filename and raw_attachment.filename.strip():
            attachment_file = raw_attachment
    else:
        try:
            data = await request.json()
            if not isinstance(data, dict):
                return JSONResponse(status_code=422, content={"success": False, "errors": {"body": "Invalid payload."}})
        except Exception:
            return JSONResponse(status_code=422, content={"success": False, "errors": {"body": "Invalid JSON payload."}})

    errors = _validate(data)

    attachment_content: Optional[bytes] = None
    file_content_type: Optional[str] = None
    if attachment_file is not None:
        attachment_content = await attachment_file.read()
        file_size = len(attachment_content)
        file_content_type = getattr(attachment_file, "content_type", None)
        if not file_content_type and hasattr(attachment_file, "headers"):
            file_content_type = attachment_file.headers.get("content-type")

        if file_size == 0:
            errors["attachment"] = "Attachment file cannot be empty."
        elif file_size > MAX_ATTACHMENT_SIZE:
            errors["attachment"] = "Attachment size must not exceed 5 MB."
        else:
            orig_filename = attachment_file.filename or ""
            ext = os.path.splitext(orig_filename)[1].lower()
            if not ext or ext not in ALLOWED_EXTENSIONS:
                errors["attachment"] = "Unsupported file type. Allowed formats: PNG, JPEG, WebP, PDF, TXT, LOG."
            elif file_content_type and file_content_type.lower() not in ALLOWED_MIME_TYPES:
                errors["attachment"] = f"Unsupported file content type: {file_content_type}."

    if errors:
        return JSONResponse(status_code=422, content={"success": False, "errors": errors})

    saved_file_path: Optional[str] = None
    rel_storage_path: Optional[str] = None
    orig_filename: Optional[str] = None
    file_size_val: Optional[int] = None
    content_type_str: Optional[str] = None

    if attachment_file is not None and attachment_content is not None:
        orig_filename = (attachment_file.filename or "attachment")[:255]
        content_type_str = file_content_type or "application/octet-stream"
        file_size_val = len(attachment_content)

        ext = os.path.splitext(orig_filename)[1].lower()
        unique_name = f"{uuid.uuid4().hex}{ext}"
        rel_storage_path = f"feedback/{unique_name}"

        target_dir = os.path.join(LOCAL_STORAGE_DIR, "feedback")
        os.makedirs(target_dir, exist_ok=True)
        saved_file_path = os.path.join(target_dir, unique_name)

        async with aiofiles.open(saved_file_path, "wb") as fh:
            await fh.write(attachment_content)

    try:
        feedback = Feedback(
            name=(data.get("name") or "").strip() or None,
            email=data["email"].strip().lower(),
            category=data["category"].strip(),
            subject=data["subject"].strip(),
            message=data["message"].strip(),
            ip_address=_get_client_ip(request),
            user_agent=(request.headers.get("user-agent") or "")[:512],
            attachment_filename=orig_filename,
            attachment_content_type=content_type_str,
            attachment_size=file_size_val,
            attachment_storage_path=rel_storage_path,
        )
        db.add(feedback)
        await db.commit()
        await db.refresh(feedback)
    except Exception as exc:
        await db.rollback()
        if saved_file_path and os.path.exists(saved_file_path):
            try:
                os.unlink(saved_file_path)
            except Exception as unlink_err:
                logger.error(f"Failed to remove attachment file {saved_file_path} on failure: {unlink_err}")
        logger.error(f"Failed to create feedback record: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save feedback.")

    feedback_response = {
        "id": str(feedback.id),
        "status": feedback.status,
        "submitted_at": feedback.submitted_at.isoformat() if feedback.submitted_at else None,
        "has_attachment": bool(feedback.attachment_storage_path),
    }
    if feedback.attachment_storage_path:
        feedback_response["attachment"] = {
            "filename": feedback.attachment_filename,
            "content_type": feedback.attachment_content_type,
            "size": feedback.attachment_size,
        }

    return {
        "success": True,
        "message": "Feedback saved.",
        "feedback": feedback_response,
    }


# --- Admin-only endpoints ---

@router.get("")
async def list_feedback(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    category: Optional[str] = None,
    status: Optional[str] = None,
):
    _require_admin(current_user)
    query = select(Feedback).order_by(Feedback.submitted_at.desc())
    if category:
        query = query.where(Feedback.category == category)
    if status:
        query = query.where(Feedback.status == status)
    query = query.limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return [
        {
            "id": str(f.id),
            "name": f.name,
            "email": f.email,
            "category": f.category,
            "subject": f.subject,
            "message": f.message,
            "status": f.status,
            "ip_address": f.ip_address,
            "submitted_at": f.submitted_at.isoformat() if f.submitted_at else None,
            "has_attachment": bool(f.attachment_storage_path),
            "attachment_filename": f.attachment_filename,
            "attachment_size": f.attachment_size,
            "attachment_content_type": f.attachment_content_type,
        }
        for f in items
    ]


@router.get("/{feedback_id}")
async def get_feedback(feedback_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    _require_admin(current_user)
    try:
        fb_uuid = uuid.UUID(feedback_id)
        result = await db.execute(select(Feedback).where(Feedback.id == fb_uuid))
    except (ValueError, AttributeError):
        result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return {
        "id": str(feedback.id),
        "name": feedback.name,
        "email": feedback.email,
        "category": feedback.category,
        "subject": feedback.subject,
        "message": feedback.message,
        "status": feedback.status,
        "ip_address": feedback.ip_address,
        "user_agent": feedback.user_agent,
        "submitted_at": feedback.submitted_at.isoformat() if feedback.submitted_at else None,
        "has_attachment": bool(feedback.attachment_storage_path),
        "attachment_filename": feedback.attachment_filename,
        "attachment_size": feedback.attachment_size,
        "attachment_content_type": feedback.attachment_content_type,
    }


@router.get("/{feedback_id}/attachment")
async def download_feedback_attachment(
    feedback_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    try:
        fb_uuid = uuid.UUID(feedback_id)
        result = await db.execute(select(Feedback).where(Feedback.id == fb_uuid))
    except (ValueError, AttributeError):
        result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    if not feedback.attachment_storage_path:
        raise HTTPException(status_code=404, detail="Feedback has no attachment")

    target_path = os.path.abspath(os.path.join(LOCAL_STORAGE_DIR, feedback.attachment_storage_path))
    abs_base = os.path.abspath(LOCAL_STORAGE_DIR)

    # Security check: prevent directory traversal
    if not target_path.startswith(abs_base):
        raise HTTPException(status_code=403, detail="Forbidden access to attachment")

    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="Attachment file not found on disk")

    filename = feedback.attachment_filename or os.path.basename(target_path)
    media_type = feedback.attachment_content_type or "application/octet-stream"

    return FileResponse(
        path=target_path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="attachment",
    )
