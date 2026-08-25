from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
from src.setup.database import get_db
from src.setup.dependencies import CurrentUser
from src.setup.local_auth import create_access_token, verify_password, get_password_hash, decode_access_token
from src.models.core import FacultyProfile, PasswordResetToken, MfaOtp
from src.schema.core import FacultyProfileCreate, FacultyProfileUpdate
from src.crud.core import get_faculty_by_email
from src.setup.email_utils import send_verification_email, send_reset_email, send_mfa_email, send_sms_otp
from src.setup.activity_logger import log_activity
from typing import Optional
import uuid
from src.setup.rate_limit import check_rate_limit
from datetime import datetime, timedelta
from urllib.parse import urlparse
import hashlib
import secrets
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    mfa_required: bool = False
    mfa_token: Optional[str] = None
    token: Optional[str] = None
    profile: Optional[dict] = None

class VerifyMfaRequest(BaseModel):
    mfa_token: str
    code: str

async def _profile_dict(user: FacultyProfile, db: AsyncSession) -> dict:
    profile = {
        "email": user.email,
        "full_name": user.full_name,
        "appraisal_role": user.appraisal_role,
        "department": user.department,
        "school": user.school,
        "employee_id": user.employee_id,
        "designation": user.designation,
        "qualification": user.qualification,
        "teaching_experience": user.teaching_experience,
        "phone": user.phone,
        "avatar": user.avatar,
        "profile_picture_url": user.profile_picture_url,
        "departments": [],
        "schools": []
    }

    if user.appraisal_role == "hod":
        from src.models.core import RoleAssignment, Department
        from uuid import UUID
        asg_res = await db.execute(
            select(RoleAssignment.scope_id)
            .where(
                RoleAssignment.user_id == user.id,
                RoleAssignment.role_type == "HOD",
                RoleAssignment.status == "active"
            )
        )
        assigned_dept_ids = []
        for sid in asg_res.scalars().all():
            try:
                if isinstance(sid, UUID):
                    assigned_dept_ids.append(sid)
                elif isinstance(sid, str):
                    assigned_dept_ids.append(UUID(sid))
            except Exception:
                pass
        
        if assigned_dept_ids:
            dept_res = await db.execute(
                select(Department.name)
                .where(
                    Department.id.in_(assigned_dept_ids),
                    Department.status == "active"
                )
            )
            profile["departments"] = dept_res.scalars().all()
            
        # Fallback to user's registered department if no active assignment is found
        if not profile["departments"] and user.department:
            profile["departments"] = [user.department]

    elif user.appraisal_role == "director":
        from src.models.core import RoleAssignment
        asg_res = await db.execute(
            select(RoleAssignment.scope_id)
            .where(
                RoleAssignment.user_id == user.id,
                RoleAssignment.role_type == "DIRECTOR",
                RoleAssignment.status == "active"
            )
        )
        profile["schools"] = asg_res.scalars().all()
        
        # Fallback to user's registered school if no active assignment is found
        if not profile["schools"] and user.school:
            profile["schools"] = [user.school]

    return profile

@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    # Reload env vars dynamically on each request to pick up admin config changes immediately
    load_dotenv(override=True)
    
    await check_rate_limit(f"login:{data.email.lower()}", max_requests=5, window_seconds=60)

    # Intercept Isolated Experimental Sandbox Account login
    if data.email.lower() == "experimental@gmail.com":
        if data.password == "Ruhan@2003":
            token = create_access_token({
                "sub": "00000000-0000-0000-0000-000000000002",
                "email": "experimental@gmail.com",
                "appraisal_role": "admin",
                "department": "Computer Science",
                "school": "SoCSEA"
            })
            return {
                "mfa_required": False,
                "token": token,
                "profile": {
                    "id": "00000000-0000-0000-0000-000000000002",
                    "email": "experimental@gmail.com",
                    "full_name": "Experimental Sandbox Admin",
                    "appraisal_role": "admin",
                    "school": "SoCSEA",
                    "department": "Computer Science",
                    "designation": "Developer",
                    "employee_id": "EXP-001",
                    "phone": "",
                    "qualification": "",
                    "teaching_experience": "",
                    "is_verified": True,
                    "profile_picture_url": None
                }
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid email or password")

    user = await get_faculty_by_email(db, data.email)
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_verified:
        user.is_verified = True
        await db.commit()
        await db.refresh(user)

    mfa_enabled = os.getenv("MFA_ENABLED", "true").lower() == "true"
    if os.getenv("TWO_FACTOR_AUTH") is not None:
        mfa_enabled = os.getenv("TWO_FACTOR_AUTH").lower() == "true"

    if mfa_enabled:
        mfa_token = secrets.token_urlsafe(32)
        is_test = os.getenv("ENV") != "production" and data.email.lower().startswith("test")
        otp_code = "000000" if is_test else f"{secrets.randbelow(1000000):06d}"
        
        mfa_entry = MfaOtp(
            id=uuid.uuid4(),
            email=user.email,
            mfa_token=mfa_token,
            otp_code=otp_code,
            used=False,
            expires_at=datetime.utcnow() + timedelta(minutes=5)
        )
        db.add(mfa_entry)
        await db.commit()
        
        if not is_test:
            # Send to email
            try:
                await send_mfa_email(user.email, otp_code)
            except Exception as e:
                logger.error(f"Failed to send MFA email to {user.email}: {e}")
            
            # Send to phone (SMS) if available
            if user.phone:
                try:
                    await send_sms_otp(user.phone, otp_code)
                except Exception as e:
                    logger.error(f"Failed to send MFA SMS to {user.phone}: {e}")
                    
        return {
            "mfa_required": True,
            "mfa_token": mfa_token
        }

    # Bypassed/disabled MFA
    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "appraisal_role": user.appraisal_role,
        "department": user.department,
        "school": user.school
    })

    profile_data = await _profile_dict(user, db)

    await log_activity(
        type="login",
        title="Faculty Login",
        detail=f"{user.full_name} logged in to the appraisal portal",
        meta={"email": user.email, "role": user.appraisal_role, "school": user.school}
    )

    return {
        "mfa_required": False,
        "token": token,
        "profile": profile_data
    }

@router.post("/verify-mfa", response_model=LoginResponse)
async def verify_mfa(data: VerifyMfaRequest, db: AsyncSession = Depends(get_db)):
    await check_rate_limit(f"mfa:{data.mfa_token}", max_requests=10, window_seconds=60)
    
    result = await db.execute(
        select(MfaOtp).where(
            MfaOtp.mfa_token == data.mfa_token,
            MfaOtp.used == False,
            MfaOtp.expires_at > datetime.utcnow()
        )
    )
    mfa_entry = result.scalar_one_or_none()
    
    if not mfa_entry:
        raise HTTPException(status_code=400, detail="Invalid, expired, or already used verification code")
        
    if mfa_entry.otp_code != data.code.strip():
        raise HTTPException(status_code=400, detail="Incorrect verification code")
        
    mfa_entry.used = True
    
    user = await get_faculty_by_email(db, mfa_entry.email)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
        
    await db.commit()
    
    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "appraisal_role": user.appraisal_role,
        "department": user.department,
        "school": user.school
    })

    profile_data = await _profile_dict(user, db)
    
    await log_activity(
        type="login",
        title="Faculty Login",
        detail=f"{user.full_name} logged in to the appraisal portal (MFA verified)",
        meta={"email": user.email, "role": user.appraisal_role, "school": user.school}
    )

    return {
        "mfa_required": False,
        "token": token,
        "profile": profile_data
    }

@router.post("/register")
async def register(data: FacultyProfileCreate, db: AsyncSession = Depends(get_db)):
    existing = await get_faculty_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = FacultyProfile(
        email=data.email,
        password_hash=get_password_hash(data.password),
        full_name=data.full_name,
        appraisal_role=data.appraisal_role,
        school=data.school,
        department=data.department,
        designation=data.designation,
        employee_id=data.employee_id,
        phone=data.phone,
        qualification=data.qualification,
        teaching_experience=data.teaching_experience,
        is_verified=False
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    verify_token = create_access_token(
        {"sub": str(new_user.id), "email": new_user.email, "purpose": "email_verification"},
        expires_delta=timedelta(hours=24),
    )
    try:
        await send_verification_email(new_user.email, verify_token)
    except Exception as e:
        logger.error(f"Failed to send verification email to {new_user.email}: {e}")

    return {
        "message": "Registration successful. Please check your email to verify your account.",
        "email": new_user.email
    }

@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    frontend_login_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/") + "/login"
    try:
        logger.info("Email verification attempt started.")
        payload = decode_access_token(token)
        email = payload.get("email")
        if not email:
            logger.warning("Email verification failed: No email in token.")
            return RedirectResponse(url=f"{frontend_login_url}?error=invalid_token")

        user = await get_faculty_by_email(db, email)
        if not user:
            logger.warning(f"Email verification failed: User {email} not found.")
            return RedirectResponse(url=f"{frontend_login_url}?error=user_not_found")

        if not user.is_verified:
            user.is_verified = True
            await db.commit()
            logger.info(f"Email verification successful for {email}.")
        else:
            logger.info(f"Email already verified for {email}.")

        return RedirectResponse(url=f"{frontend_login_url}?verified=true")
    except Exception as e:
        logger.error(f"Email verification exception: {str(e)}")
        return RedirectResponse(url=f"{frontend_login_url}?error=verification_failed")

@router.get("/me")
async def get_me(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    if current_user.email.lower() == "experimental@gmail.com":
        return {
            "email": "experimental@gmail.com",
            "full_name": "Experimental Sandbox Admin",
            "appraisal_role": "admin",
            "school": "SoCSEA",
            "department": "Computer Science",
            "designation": "Developer",
            "employee_id": "EXP-001",
            "phone": "",
            "qualification": "",
            "teaching_experience": "",
            "is_verified": True,
            "profile_picture_url": None,
            "departments": [],
            "schools": []
        }
    user = await get_faculty_by_email(db, current_user.email)
    return await _profile_dict(user, db)

@router.put("/me")
async def update_me(data: FacultyProfileUpdate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    if current_user.email.lower() == "experimental@gmail.com":
        return {
            "email": "experimental@gmail.com",
            "full_name": data.full_name or "Experimental Sandbox Admin",
            "appraisal_role": "admin",
            "school": data.school or "SoCSEA",
            "department": data.department or "Computer Science",
            "designation": data.designation or "Developer",
            "employee_id": data.employee_id or "EXP-001",
            "phone": data.phone or "",
            "qualification": data.qualification or "",
            "teaching_experience": data.teaching_experience or "",
            "is_verified": True,
            "profile_picture_url": None,
            "departments": [],
            "schools": []
        }
    user = await get_faculty_by_email(db, current_user.email)
    if data.full_name is not None: user.full_name = data.full_name
    if data.employee_id is not None: user.employee_id = data.employee_id
    if data.qualification is not None: user.qualification = data.qualification
    if data.teaching_experience is not None: user.teaching_experience = data.teaching_experience
    if data.department is not None: user.department = data.department
    if data.school is not None: user.school = data.school
    if data.designation is not None: user.designation = data.designation
    if data.phone is not None: user.phone = data.phone
    if data.avatar is not None: user.avatar = data.avatar
    if "profile_picture_url" in data.model_fields_set:
        if data.profile_picture_url is None or (isinstance(data.profile_picture_url, str) and data.profile_picture_url.strip() == ""):
            user.profile_picture_url = None
        else:
            user.profile_picture_url = data.profile_picture_url
 
    await db.commit()
    await db.refresh(user)
    return await _profile_dict(user, db)

@router.post("/me/profile-picture")
async def upload_profile_picture(
    current_user: CurrentUser,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    filename = file.filename or "profile.png"
    safe_name = filename.replace(" ", "_")
    ext = os.path.splitext(safe_name.lower())[1].lstrip(".")
    if ext not in ["jpg", "jpeg", "png", "webp"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Allowed formats: jpg, jpeg, png, webp"
        )
    
    import aiofiles
    import hashlib
    
    # Read bytes
    raw_bytes = await file.read()
    content_hash = hashlib.sha256(raw_bytes).hexdigest()
    content_type = file.content_type or f"image/{ext}"
    
    # Get storage config
    use_local_storage = os.getenv("USE_LOCAL_STORAGE", "false").replace('"', '').replace("'", "").lower() == "true"
    local_storage_dir = os.getenv("LOCAL_STORAGE_DIR", "./uploads")
    gcp_bucket_name = os.getenv("GCP_STORAGE_BUCKET")
    gcp_project_id = os.getenv("GCP_PROJECT_ID")
    
    object_key = f"profile_pictures/{content_hash}_{safe_name}"
    
    if use_local_storage or not gcp_bucket_name:
        # Local storage fallback
        target_dir = os.path.join(local_storage_dir, "profile_pictures")
        os.makedirs(target_dir, exist_ok=True)
        local_path = os.path.join(target_dir, f"{content_hash}_{safe_name}")
        if not os.path.exists(local_path):
            async with aiofiles.open(local_path, "wb") as fh:
                await fh.write(raw_bytes)
        file_url = f"/api/v1/upload/view/profile_pictures/{content_hash}_{safe_name}"
    else:
        # GCS upload
        import asyncio
        from google.cloud import storage
        
        def _gcs_upsert_local(object_key: str, file_bytes: bytes, content_type: str) -> str:
            client = storage.Client(project=gcp_project_id)
            bucket = client.bucket(gcp_bucket_name)
            blob = bucket.blob(object_key)
            if not blob.exists():
                blob.upload_from_string(file_bytes, content_type=content_type)
            return blob.public_url

        try:
            await asyncio.to_thread(_gcs_upsert_local, object_key, raw_bytes, content_type)
            file_url = f"/api/v1/upload/view/{object_key}"
        except Exception as exc:
            logger.error(f"GCS profile picture upload failed: {exc}")
            raise HTTPException(
                status_code=500,
                detail=f"Storage upload failed: {str(exc)}"
            )

    # Persist the profile picture URL on the user profile
    user = await get_faculty_by_email(db, current_user.email)
    user.profile_picture_url = file_url
    await db.commit()
    await db.refresh(user)
    
    return {"profile_picture_url": file_url}

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@router.post("/change-password")
async def change_password(data: ChangePasswordRequest, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    user = await get_faculty_by_email(db, current_user.email)
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect current password")

    user.password_hash = get_password_hash(data.new_password)
    await db.commit()
    return {"message": "Password changed successfully"}

@router.post("/forgot-password")
async def forgot_password(request: Request, data: dict, db: AsyncSession = Depends(get_db)):
    email = data.get("email", "").strip().lower()
    await check_rate_limit(f"forgot:{email or request.client.host}", max_requests=5, window_seconds=60)
    # Always return 200 — no email enumeration
    if not email:
        return {"message": "If that email is registered, a reset link has been sent."}

    user = await get_faculty_by_email(db, email)
    if user:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(hours=1)

        db.add(PasswordResetToken(email=email, token_hash=token_hash, expires_at=expires_at))
        await db.commit()

        await log_activity(
            db,
            type="forgot_password",
            title="Forgot Password Request",
            detail=f"{user.full_name} ({user.email}) requested a password reset link",
            meta={"email": user.email, "school": user.school}
        )

        redirect_url = data.get("redirect_url", "").strip().rstrip("/")
        if redirect_url:
            allowed_hosts = [
                urlparse(os.getenv("FRONTEND_URL", "http://localhost:5173")).netloc,
                urlparse(os.getenv("APP_URL", "http://localhost:8000")).netloc,
                "pbas.dypiu.ac.in",
                "10.100.0.23",
                "10.100.0.23:3000",
                "150.129.156.37",
                "150.129.156.37:3000",
                "localhost:3000",
                "localhost:5173",
                "localhost:5174",
                "127.0.0.1:3000"
            ]
            cors_env = os.getenv("CORS_ALLOWED_ORIGINS")
            if cors_env:
                for url in cors_env.split(","):
                    parsed_env = urlparse(url.strip())
                    if parsed_env.netloc:
                        allowed_hosts.append(parsed_env.netloc)
            
            if urlparse(redirect_url).netloc not in allowed_hosts:
                redirect_url = ""
        if not redirect_url:
            redirect_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
        
        if not redirect_url.endswith("/reset-password"):
            redirect_url = f"{redirect_url}/reset-password"
 
        reset_url = f"{redirect_url}?token={raw_token}"
        try:
            sent = await send_reset_email(email, reset_url)
            if not sent:
                logger.warning(f"send_reset_email returned False for {email}. Check server email configuration.")
        except Exception as e:
            logger.error(f"Failed to send reset email to {email}: {e}")
    else:
        await log_activity(
            db,
            type="forgot_password",
            title="Forgot Password Request (Unregistered)",
            detail=f"Password reset link requested for unregistered email: {email}",
            meta={"email": email}
        )

    return {"message": "If that email is registered, a reset link has been sent."}

@router.post("/reset-password")
async def reset_password(data: dict, db: AsyncSession = Depends(get_db)):
    raw_token = data.get("token", "")
    new_password = data.get("new_password", "")

    if not raw_token or not new_password:
        raise HTTPException(status_code=400, detail="Token and new_password are required")

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        )
    )
    reset_token = result.scalar_one_or_none()

    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid, expired, or already used reset token")

    user = await get_faculty_by_email(db, reset_token.email)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    user.password_hash = get_password_hash(new_password)
    reset_token.used = True
    await db.commit()
    return {"message": "Password reset successfully."}
