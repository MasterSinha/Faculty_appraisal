import asyncio
import hashlib
import io
import os

import aiofiles
from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import RedirectResponse, FileResponse
from google.cloud import storage

from src.setup.dependencies import CurrentUser
from src.setup.errors import AppError

router = APIRouter(tags=["Upload"])

GCP_BUCKET_NAME = os.getenv("GCP_STORAGE_BUCKET")
GCP_PROJECT_ID  = os.getenv("GCP_PROJECT_ID")
LOCAL_STORAGE_DIR = os.getenv("LOCAL_STORAGE_DIR", "./uploads")


# ── PDF optimisation ──────────────────────────────────────────────────────────

def _optimize_pdf(data: bytes) -> bytes:
    """
    Losslessly reduce a PDF's byte size using pikepdf.
    Falls back to the original bytes if pikepdf raises (e.g. encrypted PDF).
    """
    try:
        import pikepdf
        with pikepdf.open(io.BytesIO(data)) as pdf:
            out = io.BytesIO()
            pdf.save(
                out,
                compress_streams=True,
                recompress_streams=True,
                normalize_content=True,
                linearize=True,
            )
            return out.getvalue()
    except Exception:
        return data


# ── GCS helper (sync — called via asyncio.to_thread) ─────────────────────────

def _gcs_upsert(object_key: str, file_bytes: bytes, content_type: str) -> str:
    """
    Upload to GCS only when the object does not already exist.
    Returns the public URL in both cases (dedup or fresh upload).
    """
    client = storage.Client(project=GCP_PROJECT_ID)
    bucket = client.bucket(GCP_BUCKET_NAME)
    blob   = bucket.blob(object_key)
    if not blob.exists():
        blob.upload_from_string(file_bytes, content_type=content_type)
    return blob.public_url


# ── Upload endpoint ───────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_file(
    current_user: CurrentUser,
    request: Request = None,
    file: UploadFile = File(...),
    folder: str | None = Form(None),
):
    raw_bytes    = await file.read()
    content_type = file.content_type or "application/octet-stream"
    safe_name    = (file.filename or "file").replace(" ", "_")

    # Losslessly optimise PDFs before hashing so the stored file is always
    # the smallest valid representation of the same content.
    if content_type == "application/pdf":
        file_bytes = await asyncio.to_thread(_optimize_pdf, raw_bytes)
    else:
        file_bytes = raw_bytes

    # SHA-256 of the (possibly optimised) bytes is the deduplication key.
    # Two uploads of identical content → identical hash → same GCS object key
    # → no second write, same URL returned.
    content_hash = hashlib.sha256(file_bytes).hexdigest()

    if folder:
        object_key = f"{folder}/{content_hash}_{safe_name}"
    else:
        object_key = f"faculty/{current_user.email}/{content_hash}_{safe_name}"

    if request:
        app_url = str(request.base_url).rstrip("/")
    else:
        app_url = os.getenv("APP_URL", "").rstrip("/")

    # ── Local storage fallback ────────────────────────────────────────────────
    if os.getenv("USE_LOCAL_STORAGE", "false").lower() == "true":
        base_dir   = folder or f"faculty/{current_user.email}"
        target_dir = os.path.join(LOCAL_STORAGE_DIR, base_dir)
        os.makedirs(target_dir, exist_ok=True)
        local_path = os.path.join(target_dir, f"{content_hash}_{safe_name}")
        deduped    = os.path.exists(local_path)
        if not deduped:
            async with aiofiles.open(local_path, "wb") as fh:
                await fh.write(file_bytes)
        rel = os.path.relpath(local_path, LOCAL_STORAGE_DIR).replace("\\", "/")
        file_url = f"{app_url}/api/v1/upload/view/{rel}" if app_url else f"/api/v1/upload/view/{rel}"
        return {
            "url":      file_url,
            "publicId": rel,
            "name":     file.filename,
            "type":     content_type,
            "deduped":  deduped,
        }

    # ── Mock (no GCP configured) ──────────────────────────────────────────────
    if not GCP_BUCKET_NAME:
        file_url = f"{app_url}/api/v1/upload/view/{object_key}" if app_url else f"/api/v1/upload/view/{object_key}"
        return {
            "url":      file_url,
            "publicId": object_key,
            "name":     file.filename,
            "type":     content_type,
            "deduped":  False,
        }

    # ── GCS ───────────────────────────────────────────────────────────────────
    try:
        await asyncio.to_thread(
            _gcs_upsert, object_key, file_bytes, content_type
        )
        file_url = f"{app_url}/api/v1/upload/view/{object_key}" if app_url else f"/api/v1/upload/view/{object_key}"
        return {
            "url":      file_url,
            "publicId": object_key,
            "name":     file.filename,
            "type":     content_type,
        }
    except Exception as exc:
        raise AppError(
            "Your file could not be uploaded. Please try again.",
            detail=f"GCS upload failed: {type(exc).__name__}: {exc}",
            status_code=500,
        )


# ── View/Download proxy endpoint ──────────────────────────────────────────────

@router.get("/upload/view/{path:path}")
async def view_file(path: str):
    """
    Serve file from local storage or redirect to GCP Storage bucket.
    This hides bucket details and works dynamically in any environment.
    """
    use_local = os.getenv("USE_LOCAL_STORAGE", "false").lower() == "true"
    if use_local or not GCP_BUCKET_NAME:
        target_path = os.path.join(LOCAL_STORAGE_DIR, path)
        if not os.path.exists(target_path):
            raise HTTPException(status_code=404, detail="File not found")
        # Security check: prevent directory traversal
        abs_target = os.path.abspath(target_path)
        abs_base = os.path.abspath(LOCAL_STORAGE_DIR)
        if not abs_target.startswith(abs_base):
            raise HTTPException(status_code=403, detail="Forbidden")
        return FileResponse(target_path)
    else:
        # Redirect to GCP Storage public URL
        return RedirectResponse(url=f"https://storage.googleapis.com/{GCP_BUCKET_NAME}/{path}")
