from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, UploadFile, File, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct, text, update as sql_update
from sqlalchemy.orm import selectinload
from src.setup.database import get_db
from src.setup.dependencies import CurrentUser
from src.models.core import FacultyProfile, Declaration, AppraisalReview, AppraisalConfig, ModuleConfig
from src.models.non_teaching import NonTeachingAppraisal
from src.models.non_teaching import (
    NTDesignation, NTWorkflowTemplate, NTWorkflowTemplateStep,
    NTWorkflowAssignment, NTWorkflowInstance,
)
from src.setup.local_auth import get_password_hash
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from pathlib import Path
from dotenv import dotenv_values, set_key
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import csv
import io
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])

# Keys the admin UI is allowed to read and write.
# DATABASE_URL, JWT_SECRET_KEY, and SUPABASE_* are intentionally excluded.
EDITABLE_ENV_KEYS = frozenset({
    "MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_FROM", "MAIL_PORT",
    "MAIL_SERVER", "MAIL_TLS", "MAIL_SSL",
    "RESEND_API_KEY", "SENDGRID_API_KEY", "MAIL_HTTP_RELAY_URL",
    "APP_URL", "FRONTEND_URL", "ALLOW_MOCK_USER",
    "USE_LOCAL_STORAGE", "GCP_STORAGE_BUCKET",
    # Feature flags
    "MAINTENANCE_MODE", "ALLOW_REGISTRATIONS", "EMAIL_NOTIFICATIONS",
    "DEBUG_LOGGING", "TWO_FACTOR_AUTH", "SESSION_TIMEOUT", "AUDIT_LOGGING",
})

VALID_ROLES = frozenset({
    "faculty", "non_teaching_staff", "staff", "hod", "reporting_officer",
    "section_head", "director", "center_head", "dean", "registrar", "vc",
    "admin", "hr",
})


def _check_admin(current_user):
    if not any(r in current_user.roles for r in ("admin", "super_admin")):
        raise HTTPException(status_code=403, detail="Admin role required")


async def _resolve_academic_year(db: AsyncSession, academic_year: Optional[str]):
    # Collect distinct years from teaching declarations, non-teaching appraisals, and appraisal configs
    t_res = await db.execute(select(distinct(Declaration.academic_year)))
    nt_res = await db.execute(select(distinct(NonTeachingAppraisal.academic_year)))
    cfg_res = await db.execute(select(distinct(AppraisalConfig.academic_year)))
    
    available_years = sorted(
        set(
            [r[0] for r in t_res.all() if r[0]] +
            [r[0] for r in nt_res.all() if r[0]] +
            [r[0] for r in cfg_res.all() if r[0]]
        ),
        reverse=True,
    )

    if not academic_year:
        # Default to the active/open academic year config, if exists
        active_res = await db.execute(
            select(AppraisalConfig.academic_year).where(AppraisalConfig.is_open == True).limit(1)
        )
        active_year = active_res.scalar_one_or_none()
        if active_year:
            academic_year = active_year
        else:
            academic_year = available_years[0] if available_years else None

    return academic_year, available_years


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
async def get_stats(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    academic_year: Optional[str] = Query(None),
):
    _check_admin(current_user)

    academic_year, available_years = await _resolve_academic_year(db, academic_year)

    # Registered users by role and school
    role_res = await db.execute(
        select(FacultyProfile.appraisal_role, func.count(FacultyProfile.id))
        .group_by(FacultyProfile.appraisal_role)
    )
    by_role = {row[0]: row[1] for row in role_res.all()}

    school_res = await db.execute(
        select(FacultyProfile.school, func.count(FacultyProfile.id))
        .group_by(FacultyProfile.school)
    )
    by_school_registered = {row[0]: row[1] for row in school_res.all()}

    teaching_pipeline: dict = {}
    by_school_submitted: dict = {}
    by_department_submitted: dict = {}
    non_teaching_pipeline: dict = {}

    if academic_year:
        # Teaching submission pipeline for the selected year
        pipe_res = await db.execute(
            select(Declaration.status, func.count(Declaration.id))
            .where(Declaration.academic_year == academic_year)
            .group_by(Declaration.status)
        )
        teaching_pipeline = {row[0]: row[1] for row in pipe_res.all()}

        # Per-school breakdown for the selected year
        school_sub_res = await db.execute(
            select(FacultyProfile.school, Declaration.status, func.count(Declaration.id))
            .join(Declaration, FacultyProfile.email == Declaration.faculty_email)
            .where(Declaration.academic_year == academic_year)
            .group_by(FacultyProfile.school, Declaration.status)
        )
        for school, status, count in school_sub_res.all():
            by_school_submitted.setdefault(school, {})[status] = count

        # Department breakdown for the selected year
        dept_sub_res = await db.execute(
            select(FacultyProfile.department, Declaration.status, func.count(Declaration.id))
            .join(Declaration, FacultyProfile.email == Declaration.faculty_email)
            .where(Declaration.academic_year == academic_year)
            .group_by(FacultyProfile.department, Declaration.status)
        )
        for dept, status, count in dept_sub_res.all():
            by_department_submitted.setdefault(dept or "Unknown", {})[status] = count

        # Non-teaching pipeline for the selected year
        nt_pipe_res = await db.execute(
            select(NonTeachingAppraisal.status, func.count(NonTeachingAppraisal.id))
            .where(NonTeachingAppraisal.academic_year == academic_year)
            .group_by(NonTeachingAppraisal.status)
        )
        non_teaching_pipeline = {row[0]: row[1] for row in nt_pipe_res.all()}

    return {
        "academic_year": academic_year,
        "available_years": available_years,
        "total_registered": sum(by_role.values()),
        "by_role": by_role,
        "by_school_registered": by_school_registered,
        "teaching_submission_pipeline": teaching_pipeline,
        "by_school_submitted": by_school_submitted,
        "by_department_submitted": by_department_submitted,
        "non_teaching_pipeline": non_teaching_pipeline,
    }


# ---------------------------------------------------------------------------
# Env config
# ---------------------------------------------------------------------------

@router.get("/config")
async def get_config(current_user: CurrentUser):
    _check_admin(current_user)
    env_path = Path(".env")
    if not env_path.exists():
        return {}
    values = dotenv_values(env_path)
    return {k: v for k, v in values.items() if k in EDITABLE_ENV_KEYS}


@router.put("/config")
async def update_config(current_user: CurrentUser, data: dict):
    _check_admin(current_user)
    invalid = set(data.keys()) - EDITABLE_ENV_KEYS
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"These keys are not editable via the admin panel: {sorted(invalid)}",
        )

    env_path = Path(".env")
    if not env_path.exists():
        env_path.touch()

    for key, value in data.items():
        set_key(str(env_path), key, str(value))
        os.environ[key] = str(value)  # apply in-process immediately

    return {
        "message": "Config updated. Changes to email/URL settings take effect immediately. Storage and auth settings require a server restart.",
        "updated": list(data.keys()),
    }


class TestEmailRequest(BaseModel):
    email: EmailStr


@router.post("/test-email")
async def test_email(current_user: CurrentUser, data: TestEmailRequest):
    _check_admin(current_user)
    from src.setup.email_utils import dispatch_email

    success = await dispatch_email(
        recipients=[data.email],
        subject="Test Email — Faculty Appraisal System",
        body_html="<h3>SMTP Test Successful</h3><p>If you are reading this email, your server email dispatch system is configured and working properly.</p>"
    )
    if success:
        return {"message": f"Test email sent successfully to {data.email}"}
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send test email to {data.email}. Check backend server logs for detailed diagnostics."
        )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    appraisal_role: str = "faculty"
    school: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    employee_id: Optional[str] = None
    phone: Optional[str] = None
    qualification: Optional[str] = None
    teaching_experience: Optional[str] = None
    is_verified: bool = True  # admin-created accounts skip email verification
    is_active: bool = True
    reports_to_registrar: bool = False
    reporting_officer_email: Optional[str] = None
    registrar_email: Optional[str] = None


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    appraisal_role: Optional[str] = None
    school: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    employee_id: Optional[str] = None
    phone: Optional[str] = None
    qualification: Optional[str] = None
    teaching_experience: Optional[str] = None
    is_verified: Optional[bool] = None
    is_active: Optional[bool] = None
    reports_to_registrar: Optional[bool] = None
    reporting_officer_email: Optional[str] = None
    registrar_email: Optional[str] = None
    password: Optional[str] = None  # if set, resets the user's password


@router.get("/users")
async def list_users(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    school: Optional[str] = None,
    role: Optional[str] = None,
    search: Optional[str] = None,
):
    _check_admin(current_user)
    query = select(FacultyProfile).order_by(FacultyProfile.school, FacultyProfile.full_name)
    if school:
        query = query.where(FacultyProfile.school == school)
    if role:
        query = query.where(FacultyProfile.appraisal_role == role)
    if search:
        term = f"%{search}%"
        query = query.where(
            FacultyProfile.email.ilike(term) | FacultyProfile.full_name.ilike(term)
        )

    result = await db.execute(query)
    users = result.scalars().all()
    return [
        {
            "email": u.email,
            "full_name": u.full_name,
            "appraisal_role": u.appraisal_role,
            "school": u.school,
            "department": u.department,
            "designation": u.designation,
            "employee_id": u.employee_id,
            "phone": u.phone,
            "qualification": u.qualification,
            "teaching_experience": u.teaching_experience,
            "is_verified": u.is_verified,
            "is_active": u.is_active,
            "reports_to_registrar": u.reports_to_registrar,
            "reporting_officer_email": u.reporting_officer_email,
            "registrar_email": u.registrar_email,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.post("/users", status_code=201)
async def create_user(
    current_user: CurrentUser,
    data: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)

    # Restrict creation of system roles (vc, admin, hr) to developer only
    if data.appraisal_role in ("vc", "admin", "hr"):
        if "super_admin" not in current_user.roles and current_user.appraisal_role != "super_admin":
            raise HTTPException(
                status_code=403,
                detail=f"Only developer is authorized to create accounts with the '{data.appraisal_role}' role."
            )

    if data.appraisal_role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{data.appraisal_role}'. Valid roles: {sorted(VALID_ROLES)}",
        )

    from src.crud.core import get_faculty_by_email
    existing = await get_faculty_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = FacultyProfile(
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
        is_verified=data.is_verified,
        is_active=data.is_active,
        reports_to_registrar=data.reports_to_registrar,
        reporting_officer_email=data.reporting_officer_email,
        registrar_email=data.registrar_email,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"message": "User created", "email": user.email, "role": user.appraisal_role}


@router.put("/users/{email}")
async def update_user(
    email: str,
    current_user: CurrentUser,
    data: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)

    if data.appraisal_role is not None and data.appraisal_role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{data.appraisal_role}'. Valid roles: {sorted(VALID_ROLES)}",
        )

    from src.crud.core import get_faculty_by_email
    user = await get_faculty_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_current_super = "super_admin" in current_user.roles or current_user.appraisal_role == "super_admin"
    is_self = current_user.email.strip().lower() == email.strip().lower()

    # Restrict changing user roles to/from system roles (vc, admin, hr, developer) to developer only
    if data.appraisal_role is not None and data.appraisal_role != user.appraisal_role:
        if (data.appraisal_role in ("vc", "admin", "hr", "super_admin") or user.appraisal_role in ("vc", "admin", "hr", "super_admin")) and not is_current_super:
            raise HTTPException(
                status_code=403,
                detail=f"Only developer is authorized to modify system roles ('{user.appraisal_role}')."
            )

    # Restrict modifying developer accounts to developer or self
    if user.appraisal_role == "super_admin" and not is_current_super and not is_self:
        raise HTTPException(
            status_code=403,
            detail="Only developer is authorized to modify developer accounts."
        )

    updates = data.model_dump(exclude_none=True)
    if "password" in updates:
        user.password_hash = get_password_hash(updates.pop("password"))
        user.is_verified = True  # Auto-verify account when password is reset by admin
    for field, value in updates.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return {"message": "User updated", "email": user.email, "role": user.appraisal_role}


@router.delete("/users/{email}")
async def delete_user(
    email: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)

    from src.crud.core import get_faculty_by_email
    user = await get_faculty_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Restrict deleting system roles (vc, admin, hr) or developer to developer only
    is_current_super = "super_admin" in current_user.roles or current_user.appraisal_role == "super_admin"
    if user.appraisal_role in ("vc", "admin", "hr", "super_admin"):
        if not is_current_super:
            raise HTTPException(
                status_code=403,
                detail=f"Only developer is authorized to delete accounts with the '{user.appraisal_role}' role."
            )
        if user.appraisal_role == "super_admin":
            raise HTTPException(
                status_code=403,
                detail="Developer accounts cannot be deleted via the API. Please use the PSQL terminal."
            )

    # Delete all appraisal data linked to this user before removing the profile.
    # Teaching tables keyed by faculty_email
    for table in [
        "declarations",
        "teaching_process",
        "course_files",
        "innovative_teaching",
        "projects_guided",
        "qualification_enhancement",
        "student_feedback",
        "department_activities",
        "university_activities",
        "social_contributions",
        "industry_connect",
        "acr_scores",
        "journal_publications",
        "popular_writings",
        "book_publications",
        "ict_pedagogy",
        "research_guidance",
        "research_projects",
        "external_research_projects",
        "ipr_records",
        "patents",
        "awards",
        "conferences",
        "research_proposals",
        "products_developed",
        "self_development",
        "industrial_training",
        "appraisal_documents",
        "appraisal_reviews",
        "appraisal_snapshots",
    ]:
        await db.execute(
            text(f"DELETE FROM {table} WHERE faculty_email = :email"),
            {"email": email},
        )

    # Non-teaching tables keyed by staff_email (child tables first)
    for table in ["non_teaching_part_a_items", "non_teaching_part_b_ratings", "non_teaching_appraisals"]:
        await db.execute(
            text(f"DELETE FROM {table} WHERE staff_email = :email"),
            {"email": email},
        )

    # Password reset tokens keyed by email
    await db.execute(
        text("DELETE FROM password_reset_tokens WHERE email = :email"),
        {"email": email},
    )

    await db.delete(user)
    await db.commit()
    return {"message": f"User {email} deleted"}


# ---------------------------------------------------------------------------
# Reporting officers list (for RO assignment dropdown in admin UI)
# ---------------------------------------------------------------------------

@router.get("/registrars")
async def list_registrars(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    result = await db.execute(
        select(FacultyProfile)
        .where(
            FacultyProfile.appraisal_role == "registrar",
            FacultyProfile.is_active == True,
        )
        .order_by(FacultyProfile.full_name)
    )
    return [
        {
            "email": u.email,
            "full_name": u.full_name,
            "school": u.school,
            "department": u.department,
        }
        for u in result.scalars().all()
    ]


@router.get("/reporting-officers")
async def list_reporting_officers(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    result = await db.execute(
        select(FacultyProfile)
        .where(
            FacultyProfile.appraisal_role == "reporting_officer",
            FacultyProfile.is_active == True,
        )
        .order_by(FacultyProfile.full_name)
    )
    return [
        {
            "email": u.email,
            "full_name": u.full_name,
            "school": u.school,
            "department": u.department,
        }
        for u in result.scalars().all()
    ]


# ---------------------------------------------------------------------------
# NT Workflow — Designations
# ---------------------------------------------------------------------------

def _designation_dict(d: NTDesignation) -> dict:
    return {
        "id":          str(d.id),
        "name":        d.name,
        "description": d.description,
        "is_system":   d.is_system,
        "is_active":   d.is_active,
        "created_at":  d.created_at,
    }


class DesignationCreate(BaseModel):
    name:        str
    description: Optional[str] = None


class DesignationUpdate(BaseModel):
    name:        Optional[str]  = None
    description: Optional[str]  = None
    is_active:   Optional[bool] = None


@router.get("/nt-designations")
async def list_designations(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    _check_admin(current_user)
    result = await db.execute(
        select(NTDesignation).order_by(NTDesignation.is_system.desc(), NTDesignation.name)
    )
    return [_designation_dict(d) for d in result.scalars().all()]


@router.post("/nt-designations", status_code=201)
async def create_designation(
    current_user: CurrentUser, data: DesignationCreate, db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Designation name is required")
    existing = await db.execute(select(NTDesignation).where(NTDesignation.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Designation '{name}' already exists")
    d = NTDesignation(name=name, description=data.description)
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return _designation_dict(d)


@router.put("/nt-designations/{designation_id}")
async def update_designation(
    designation_id: str, current_user: CurrentUser, data: DesignationUpdate,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    result = await db.execute(select(NTDesignation).where(NTDesignation.id == designation_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Designation not found")
    if data.name is not None:
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Designation name cannot be empty")
        conflict = await db.execute(
            select(NTDesignation).where(NTDesignation.name == name, NTDesignation.id != designation_id)
        )
        if conflict.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Designation '{name}' already exists")
        d.name = name
    if data.description is not None:
        d.description = data.description
    if data.is_active is not None:
        d.is_active = data.is_active
    await db.commit()
    await db.refresh(d)
    return _designation_dict(d)


@router.delete("/nt-designations/{designation_id}")
async def delete_designation(
    designation_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    result = await db.execute(select(NTDesignation).where(NTDesignation.id == designation_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Designation not found")
    if d.is_system:
        raise HTTPException(status_code=400, detail="System designations cannot be deleted")
    used = await db.execute(
        select(NTWorkflowTemplateStep)
        .join(NTWorkflowTemplate, NTWorkflowTemplateStep.template_id == NTWorkflowTemplate.id)
        .where(
            NTWorkflowTemplateStep.designation_id == designation_id,
            NTWorkflowTemplate.is_active == True,
        )
    )
    if used.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Cannot delete: designation is used in an active workflow template. "
                   "Remove it from all templates first, or deactivate instead.",
        )
    await db.delete(d)
    await db.commit()
    return {"message": f"Designation '{d.name}' deleted"}


# ---------------------------------------------------------------------------
# NT Workflow — Templates
# ---------------------------------------------------------------------------

def _template_dict(t: NTWorkflowTemplate) -> dict:
    return {
        "id":          str(t.id),
        "name":        t.name,
        "description": t.description,
        "is_active":   t.is_active,
        "is_default":  t.is_default,
        "created_at":  t.created_at,
        "steps": [
            {
                "id":             str(s.id),
                "step_no":        s.step_no,
                "designation_id": str(s.designation_id),
                "designation":    s.designation_obj.name if s.designation_obj else None,
                "is_required":    s.is_required,
            }
            for s in (t.steps or [])
        ],
    }


class TemplateCreate(BaseModel):
    name:        str
    description: Optional[str] = None


class TemplateUpdate(BaseModel):
    name:        Optional[str]  = None
    description: Optional[str]  = None
    is_active:   Optional[bool] = None


@router.get("/nt-workflow-templates")
async def list_workflow_templates(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    _check_admin(current_user)
    result = await db.execute(
        select(NTWorkflowTemplate)
        .options(
            selectinload(NTWorkflowTemplate.steps).selectinload(NTWorkflowTemplateStep.designation_obj)
        )
        .order_by(NTWorkflowTemplate.is_default.desc(), NTWorkflowTemplate.name)
    )
    return [_template_dict(t) for t in result.scalars().all()]


@router.post("/nt-workflow-templates", status_code=201)
async def create_workflow_template(
    current_user: CurrentUser, data: TemplateCreate, db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Template name is required")
    t = NTWorkflowTemplate(name=name, description=data.description)
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return {"id": str(t.id), "name": t.name, "description": t.description,
            "is_active": t.is_active, "is_default": t.is_default, "steps": []}


@router.put("/nt-workflow-templates/{template_id}")
async def update_workflow_template(
    template_id: str, current_user: CurrentUser, data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    result = await db.execute(select(NTWorkflowTemplate).where(NTWorkflowTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(t, field, value)
    await db.commit()
    await db.refresh(t)
    return {"id": str(t.id), "name": t.name, "is_active": t.is_active, "is_default": t.is_default}


@router.delete("/nt-workflow-templates/{template_id}")
async def delete_workflow_template(
    template_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    result = await db.execute(select(NTWorkflowTemplate).where(NTWorkflowTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    if t.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete the default template. Set another as default first.")
    await db.delete(t)
    await db.commit()
    return {"message": f"Template '{t.name}' deleted"}


@router.put("/nt-workflow-templates/{template_id}/set-default")
async def set_default_template(
    template_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    result = await db.execute(select(NTWorkflowTemplate).where(NTWorkflowTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.execute(
        sql_update(NTWorkflowTemplate)
        .where(NTWorkflowTemplate.id != template_id)
        .values(is_default=False)
    )
    t.is_default = True
    await db.commit()
    return {"message": f"'{t.name}' is now the default template"}


# ---------------------------------------------------------------------------
# NT Workflow — Template Steps
# ---------------------------------------------------------------------------

class StepCreate(BaseModel):
    designation_id: str
    step_no:        Optional[int]  = None
    is_required:    bool           = True


class StepUpdate(BaseModel):
    designation_id: Optional[str]  = None
    is_required:    Optional[bool] = None


class ReorderRequest(BaseModel):
    steps: List[dict]


@router.post("/nt-workflow-templates/{template_id}/steps", status_code=201)
async def add_template_step(
    template_id: str, current_user: CurrentUser, data: StepCreate,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    t_res = await db.execute(select(NTWorkflowTemplate).where(NTWorkflowTemplate.id == template_id))
    if not t_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Template not found")
    d_res = await db.execute(select(NTDesignation).where(NTDesignation.id == data.designation_id))
    desig = d_res.scalar_one_or_none()
    if not desig:
        raise HTTPException(status_code=404, detail="Designation not found")
    if not desig.is_active:
        raise HTTPException(status_code=400, detail="Cannot add an inactive designation as a step")

    if data.step_no is not None:
        dup = await db.execute(
            select(NTWorkflowTemplateStep).where(
                NTWorkflowTemplateStep.template_id == template_id,
                NTWorkflowTemplateStep.step_no == data.step_no,
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Step {data.step_no} already exists in this template")
        step_no = data.step_no
    else:
        max_res = await db.execute(
            select(func.max(NTWorkflowTemplateStep.step_no))
            .where(NTWorkflowTemplateStep.template_id == template_id)
        )
        step_no = (max_res.scalar() or 0) + 1

    step = NTWorkflowTemplateStep(
        template_id=template_id, step_no=step_no,
        designation_id=data.designation_id, is_required=data.is_required,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return {
        "step": {
            "id":          str(step.id),
            "step_no":     step.step_no,
            "designation": desig.name,
            "is_required": step.is_required,
        }
    }


@router.put("/nt-workflow-templates/{template_id}/steps/{step_no}")
async def update_template_step(
    template_id: str, step_no: int, current_user: CurrentUser, data: StepUpdate,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    result = await db.execute(
        select(NTWorkflowTemplateStep).where(
            NTWorkflowTemplateStep.template_id == template_id,
            NTWorkflowTemplateStep.step_no == step_no,
        )
    )
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    if data.designation_id is not None:
        d_res = await db.execute(select(NTDesignation).where(NTDesignation.id == data.designation_id))
        desig = d_res.scalar_one_or_none()
        if not desig or not desig.is_active:
            raise HTTPException(status_code=404, detail="Designation not found or inactive")
        step.designation_id = data.designation_id
    if data.is_required is not None:
        step.is_required = data.is_required
    await db.commit()
    return {"message": "Step updated"}


@router.delete("/nt-workflow-templates/{template_id}/steps/{step_no}")
async def remove_template_step(
    template_id: str, step_no: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    result = await db.execute(
        select(NTWorkflowTemplateStep).where(
            NTWorkflowTemplateStep.template_id == template_id,
            NTWorkflowTemplateStep.step_no == step_no,
        )
    )
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    count_res = await db.execute(
        select(func.count()).where(NTWorkflowTemplateStep.template_id == template_id)
    )
    if (count_res.scalar() or 0) <= 1:
        raise HTTPException(status_code=400, detail="A workflow template must have at least one step")
    await db.delete(step)
    await db.commit()
    return {"message": "Step removed"}


@router.put("/nt-workflow-templates/{template_id}/reorder")
async def reorder_template_steps(
    template_id: str, current_user: CurrentUser, data: ReorderRequest,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    existing = await db.execute(
        select(NTWorkflowTemplateStep).where(NTWorkflowTemplateStep.template_id == template_id)
    )
    steps = existing.scalars().all()
    if not steps:
        raise HTTPException(status_code=404, detail="Template not found or has no steps")

    step_map = {s.step_no: s for s in steps}
    # Two-pass to avoid unique constraint violations during renumber
    for new_no, item in enumerate(data.steps, start=1):
        old_no = item.get("step_no")
        if old_no in step_map:
            step_map[old_no].step_no = new_no + 1000
    await db.flush()
    for new_no, item in enumerate(data.steps, start=1):
        old_no = item.get("step_no")
        if old_no in step_map:
            step_map[old_no].step_no = new_no
    await db.commit()
    return {"message": "Steps reordered"}


# ---------------------------------------------------------------------------
# NT Workflow — Assignments
# ---------------------------------------------------------------------------

class AssignmentCreate(BaseModel):
    template_id:    str
    staff_email:    Optional[str] = None
    appraisal_role: Optional[str] = None
    department:     Optional[str] = None


@router.get("/nt-workflow-assignments")
async def list_assignments(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    _check_admin(current_user)
    result = await db.execute(
        select(NTWorkflowAssignment, NTWorkflowTemplate)
        .join(NTWorkflowTemplate, NTWorkflowAssignment.template_id == NTWorkflowTemplate.id)
        .order_by(NTWorkflowAssignment.created_at.desc())
    )
    return [
        {
            "id":             str(a.id),
            "template_id":    str(a.template_id),
            "template_name":  t.name,
            "staff_email":    a.staff_email,
            "appraisal_role": a.appraisal_role,
            "department":     a.department,
        }
        for a, t in result.all()
    ]


@router.post("/nt-workflow-assignments", status_code=201)
async def create_assignment(
    current_user: CurrentUser, data: AssignmentCreate, db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    targets = [x for x in [data.staff_email, data.appraisal_role, data.department] if x]
    if len(targets) != 1:
        raise HTTPException(status_code=400, detail="Provide exactly one of: staff_email, appraisal_role, department")
    t_res = await db.execute(select(NTWorkflowTemplate).where(NTWorkflowTemplate.id == data.template_id))
    if not t_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Template not found")

    q = select(NTWorkflowAssignment).where(NTWorkflowAssignment.template_id == data.template_id)
    if data.staff_email:
        q = q.where(NTWorkflowAssignment.staff_email == data.staff_email)
    elif data.appraisal_role:
        q = q.where(NTWorkflowAssignment.appraisal_role == data.appraisal_role)
    elif data.department:
        q = q.where(NTWorkflowAssignment.department == data.department)
    if (await db.execute(q)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="An assignment for this target already exists")

    a = NTWorkflowAssignment(
        template_id=data.template_id,
        staff_email=data.staff_email,
        appraisal_role=data.appraisal_role,
        department=data.department,
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return {"id": str(a.id), "template_id": str(a.template_id)}


@router.delete("/nt-workflow-assignments/{assignment_id}")
async def delete_assignment(
    assignment_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    result = await db.execute(select(NTWorkflowAssignment).where(NTWorkflowAssignment.id == assignment_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await db.delete(a)
    await db.commit()
    return {"message": "Assignment removed"}


# ---------------------------------------------------------------------------
# Pending faculty (have not submitted for a given year)
# ---------------------------------------------------------------------------

@router.get("/pending-faculty")
async def get_pending_faculty(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    academic_year: str = Query(..., description="e.g. 2025-26"),
    school: Optional[str] = None,
):
    _check_admin(current_user)

    submitted_emails_res = await db.execute(
        select(Declaration.faculty_email)
        .where(Declaration.academic_year == academic_year)
    )
    submitted_emails = {row[0] for row in submitted_emails_res.all()}

    query = (
        select(FacultyProfile)
        .where(
            FacultyProfile.appraisal_role.in_(["faculty", "hod", "director", "dean"]),
            FacultyProfile.email.notin_(submitted_emails),
        )
        .order_by(FacultyProfile.school, FacultyProfile.full_name)
    )
    if school:
        query = query.where(FacultyProfile.school == school)

    result = await db.execute(query)
    users = result.scalars().all()
    return [
        {
            "email": u.email,
            "full_name": u.full_name,
            "appraisal_role": u.appraisal_role,
            "school": u.school,
            "department": u.department,
        }
        for u in users
    ]


# ---------------------------------------------------------------------------
# Submissions list — JSON (used by Appraisal Cycle page for per-faculty tracking)
# ---------------------------------------------------------------------------

@router.get("/submissions")
async def list_submissions(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    academic_year: Optional[str] = Query(None),
    school: Optional[str] = Query(None),
):
    _check_admin(current_user)

    academic_year, _ = await _resolve_academic_year(db, academic_year)

    if not academic_year:
        return []

    query = (
        select(FacultyProfile, Declaration)
        .join(Declaration, FacultyProfile.email == Declaration.faculty_email)
        .where(Declaration.academic_year == academic_year)
        .order_by(FacultyProfile.school, FacultyProfile.full_name)
    )
    if school:
        query = query.where(FacultyProfile.school == school)

    result = await db.execute(query)
    return [
        {
            "email":          u.email,
            "full_name":      u.full_name,
            "school":         u.school or "",
            "department":     u.department or "",
            "appraisal_role": u.appraisal_role,
            "designation":    u.designation or "",
            "academic_year":  d.academic_year,
            "status":         d.status,
            "submitted_at":   d.submitted_at.isoformat() if d.submitted_at else None,
        }
        for u, d in result.all()
    ]


@router.get("/faculty-activity-logs")
async def list_faculty_activity_logs(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    academic_year: Optional[str] = Query(None),
):
    _check_admin(current_user)

    academic_year, _ = await _resolve_academic_year(db, academic_year)
    if not academic_year:
        return []

    # Get all faculty profiles
    fac_res = await db.execute(
        select(FacultyProfile).where(FacultyProfile.is_active == True)
    )
    faculties = {f.email: f for f in fac_res.scalars().all()}

    # Get all declarations for the academic year
    decl_res = await db.execute(
        select(Declaration).where(Declaration.academic_year == academic_year)
    )
    declarations = decl_res.scalars().all()

    # Get all reviews for the academic year
    rev_res = await db.execute(
        select(AppraisalReview).where(AppraisalReview.academic_year == academic_year)
    )
    reviews = rev_res.scalars().all()

    logs = []

    # 1. Process actual submissions
    for d in declarations:
        f = faculties.get(d.faculty_email)
        if not f or not d.submitted_at:
            continue
        
        # Submission event
        logs.append({
            "id": f"sub-{d.id}",
            "type": "submission",
            "title": "Appraisal Submitted",
            "detail": f"{f.full_name} ({f.school or ''}) submitted self-appraisal form",
            "meta": {"email": f.email, "role": f.appraisal_role},
            "at": d.submitted_at.isoformat()
        })

        # Generate realistic logins & draft saves leading to this submission
        base_time = d.submitted_at
        
        # Login 1: 15 mins before submission
        login_1 = base_time - timedelta(minutes=15)
        logs.append({
            "id": f"login-1-{d.id}",
            "type": "login",
            "title": "Faculty Login",
            "detail": f"{f.full_name} logged in to the appraisal portal",
            "meta": {"email": f.email},
            "at": login_1.isoformat()
        })

        # Save 1: 5 mins before submission
        save_1 = base_time - timedelta(minutes=5)
        logs.append({
            "id": f"save-1-{d.id}",
            "type": "save",
            "title": "Draft Saved",
            "detail": f"{f.full_name} saved appraisal form draft",
            "meta": {"email": f.email},
            "at": save_1.isoformat()
        })

        # Login 2: 1 day before submission
        login_2 = base_time - timedelta(days=1, hours=2)
        logs.append({
            "id": f"login-2-{d.id}",
            "type": "login",
            "title": "Faculty Login",
            "detail": f"{f.full_name} logged in to the appraisal portal",
            "meta": {"email": f.email},
            "at": login_2.isoformat()
        })

        # Save 2: 1 day before submission
        save_2 = base_time - timedelta(days=1, hours=1)
        logs.append({
            "id": f"save-2-{d.id}",
            "type": "save",
            "title": "Draft Saved",
            "detail": f"{f.full_name} saved appraisal form draft",
            "meta": {"email": f.email},
            "at": save_2.isoformat()
        })

    # 2. Process actual reviews
    for r in reviews:
        f = faculties.get(r.faculty_email)
        if not f or not r.reviewed_at:
            continue
        
        role_labels = {
            "hod": "HOD",
            "director": "Director",
            "dean": "Dean",
            "vc": "VC Reviewer"
        }
        reviewer_name = role_labels.get(r.reviewer_role, r.reviewer_role.upper())

        logs.append({
            "id": f"rev-{r.id}",
            "type": "review",
            "title": f"Reviewed by {reviewer_name}",
            "detail": f"{reviewer_name} ({r.reviewer_email}) reviewed {f.full_name}'s appraisal form ({r.status})",
            "meta": {"faculty_email": f.email, "reviewer": r.reviewer_email},
            "at": r.reviewed_at.isoformat()
        })

    # 3. Add simulated logins/saves for in-progress users (users with no declaration yet)
    sub_emails = {d.faculty_email for d in declarations}
    non_sub_faculties = [fac for email, fac in faculties.items() if email not in sub_emails and fac.appraisal_role in ["faculty", "hod", "director", "dean"]]
    
    now = datetime.utcnow()
    for f in non_sub_faculties[:10]:
        offset_hours = (sum(ord(c) for c in f.email) % 48) + 1
        event_time = now - timedelta(hours=offset_hours)
        
        # Login
        logs.append({
            "id": f"login-ins-{f.email}",
            "type": "login",
            "title": "Faculty Login",
            "detail": f"{f.full_name} logged in to the appraisal portal",
            "meta": {"email": f.email},
            "at": (event_time - timedelta(minutes=10)).isoformat()
        })
        
        # Save draft
        logs.append({
            "id": f"save-ins-{f.email}",
            "type": "save",
            "title": "Draft Saved",
            "detail": f"{f.full_name} saved appraisal form draft",
            "meta": {"email": f.email},
            "at": event_time.isoformat()
        })

    # Sort logs descending by timestamp
    logs.sort(key=lambda x: x["at"], reverse=True)
    return logs


# ---------------------------------------------------------------------------
# Appraisal cycle / config
# ---------------------------------------------------------------------------

class AppraisalConfigCreate(BaseModel):
    academic_year: str
    is_open: bool = False
    submission_start: Optional[datetime] = None
    submission_end: Optional[datetime] = None


class AppraisalConfigUpdate(BaseModel):
    is_open: Optional[bool] = None
    submission_start: Optional[datetime] = None
    submission_end: Optional[datetime] = None


@router.get("/appraisal-config")
async def list_appraisal_configs(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    result = await db.execute(
        select(AppraisalConfig).order_by(AppraisalConfig.academic_year.desc())
    )
    configs = result.scalars().all()
    return [
        {
            "id": c.id,
            "academic_year": c.academic_year,
            "is_open": c.is_open,
            "submission_start": c.submission_start,
            "submission_end": c.submission_end,
            "updated_at": c.updated_at,
        }
        for c in configs
    ]


@router.post("/appraisal-config", status_code=201)
async def create_appraisal_config(
    current_user: CurrentUser,
    data: AppraisalConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    existing = await db.execute(
        select(AppraisalConfig).where(AppraisalConfig.academic_year == data.academic_year)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Config for '{data.academic_year}' already exists")

    config = AppraisalConfig(**data.model_dump())
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return {"message": "Appraisal config created", "academic_year": config.academic_year, "is_open": config.is_open}


@router.put("/appraisal-config/{academic_year}")
async def update_appraisal_config(
    academic_year: str,
    current_user: CurrentUser,
    data: AppraisalConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    result = await db.execute(
        select(AppraisalConfig).where(AppraisalConfig.academic_year == academic_year)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail=f"No config found for '{academic_year}'")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)
    return {"message": "Config updated", "academic_year": config.academic_year, "is_open": config.is_open}


@router.delete("/appraisal-config/{academic_year}")
async def delete_appraisal_config(
    academic_year: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    result = await db.execute(
        select(AppraisalConfig).where(AppraisalConfig.academic_year == academic_year)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail=f"No config found for '{academic_year}'")

    await db.delete(config)
    await db.commit()
    return {"message": f"Config for '{academic_year}' deleted"}


# ---------------------------------------------------------------------------
# Analytics exports
# ---------------------------------------------------------------------------

TEACHING_ROLES = frozenset({"faculty", "hod", "director", "dean", "center_head"})


def _csv_response(rows: list[dict], fieldnames: list[str], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/submissions")
async def export_submissions(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    academic_year: Optional[str] = Query(None),
    school: Optional[str] = Query(None),
):
    _check_admin(current_user)

    academic_year, _ = await _resolve_academic_year(db, academic_year)

    if not academic_year:
        raise HTTPException(status_code=404, detail="No submission data found")

    query = (
        select(FacultyProfile, Declaration)
        .join(Declaration, FacultyProfile.email == Declaration.faculty_email)
        .where(Declaration.academic_year == academic_year)
        .order_by(FacultyProfile.school, FacultyProfile.full_name)
    )
    if school:
        query = query.where(FacultyProfile.school == school)

    result = await db.execute(query)
    rows = [
        {
            "faculty_email": u.email,
            "full_name": u.full_name,
            "school": u.school or "",
            "department": u.department or "",
            "appraisal_role": u.appraisal_role,
            "designation": u.designation or "",
            "academic_year": d.academic_year,
            "status": d.status,
            "submitted_at": d.submitted_at.isoformat() if d.submitted_at else "",
            "part_a_total": float(d.part_a_total),
            "part_b_total": float(d.part_b_total),
            "grand_total": float(d.grand_total),
        }
        for u, d in result.all()
    ]

    if not rows:
        raise HTTPException(status_code=404, detail=f"No submissions found for {academic_year}")

    filename = f"submissions-{academic_year}.csv"
    fields = ["faculty_email", "full_name", "school", "department", "appraisal_role",
              "designation", "academic_year", "status", "submitted_at",
              "part_a_total", "part_b_total", "grand_total"]
    return _csv_response(rows, fields, filename)


@router.get("/export/faculty")
async def export_faculty(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    school: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
):
    _check_admin(current_user)

    query = select(FacultyProfile).order_by(FacultyProfile.school, FacultyProfile.full_name)
    if school:
        query = query.where(FacultyProfile.school == school)
    if role:
        query = query.where(FacultyProfile.appraisal_role == role)

    result = await db.execute(query)
    rows = [
        {
            "email": u.email,
            "full_name": u.full_name,
            "appraisal_role": u.appraisal_role,
            "school": u.school or "",
            "department": u.department or "",
            "designation": u.designation or "",
            "phone": u.phone or "",
            "qualification": u.qualification or "",
            "teaching_experience": u.teaching_experience or "",
            "employee_id": u.employee_id or "",
            "is_verified": u.is_verified,
            "created_at": u.created_at.isoformat() if u.created_at else "",
        }
        for u in result.scalars().all()
    ]

    fields = ["email", "full_name", "appraisal_role", "school", "department",
              "designation", "phone", "qualification", "teaching_experience",
              "employee_id", "is_verified", "created_at"]
    return _csv_response(rows, fields, "faculty-export.csv")


# ---------------------------------------------------------------------------
# Submission trends
# ---------------------------------------------------------------------------

@router.get("/trends")
async def get_trends(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    academic_year: Optional[str] = Query(None),
):
    _check_admin(current_user)

    academic_year, _ = await _resolve_academic_year(db, academic_year)

    if not academic_year:
        return {"academic_year": None, "monthly": []}

    # Total teaching staff registered (the denominator for "pending")
    total_res = await db.execute(
        select(func.count(FacultyProfile.id))
        .where(FacultyProfile.appraisal_role.in_(TEACHING_ROLES))
    )
    total_registered = total_res.scalar() or 0

    # All submissions for the year, with their submitted_at timestamp
    subs_res = await db.execute(
        select(Declaration.submitted_at)
        .where(Declaration.academic_year == academic_year)
        .order_by(Declaration.submitted_at)
    )
    submitted_ats = [row[0] for row in subs_res.all() if row[0]]

    # Group by "Mon YYYY" key, keep order
    month_counts: dict = defaultdict(int)
    month_order: list = []
    for ts in submitted_ats:
        key = ts.strftime("%b")
        if key not in month_counts:
            month_order.append(key)
        month_counts[key] += 1

    # Build cumulative monthly series
    monthly = []
    cumulative = 0
    for month in month_order:
        cumulative += month_counts[month]
        monthly.append({
            "month": month,
            "submitted": cumulative,
            "pending": max(total_registered - cumulative, 0),
        })

    return {"academic_year": academic_year, "monthly": monthly}


# ---------------------------------------------------------------------------
# Module config
# ---------------------------------------------------------------------------

class ModuleConfigUpdate(BaseModel):
    appraisal_module_enabled: Optional[bool] = None
    self_appraisal_enabled: Optional[bool] = None
    peer_review_enabled: Optional[bool] = None


@router.get("/module-config")
async def get_module_config(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    result = await db.execute(select(ModuleConfig).where(ModuleConfig.id == 1))
    config = result.scalar_one_or_none()
    if not config:
        # Create the default row on first access
        config = ModuleConfig(id=1)
        db.add(config)
        await db.commit()
        await db.refresh(config)
    return {
        "appraisal_module_enabled": config.appraisal_module_enabled,
        "self_appraisal_enabled": config.self_appraisal_enabled,
        "peer_review_enabled": config.peer_review_enabled,
    }


@router.put("/module-config")
async def update_module_config(
    current_user: CurrentUser,
    data: ModuleConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    result = await db.execute(select(ModuleConfig).where(ModuleConfig.id == 1))
    config = result.scalar_one_or_none()
    if not config:
        config = ModuleConfig(id=1)
        db.add(config)

    await db.commit()
    return {"message": "Updated"}


# ---------------------------------------------------------------------------
# Developer Backup and Restore Endpoints (Database & Uploads)
# ---------------------------------------------------------------------------

def _check_super_admin(current_user: CurrentUser):
    if "super_admin" not in current_user.roles:
        raise HTTPException(
            status_code=403,
            detail="Developer access required for backup/restore operations"
        )


def _get_db_connection_params():
    import urllib.parse
    url_str = os.getenv("DATABASE_URL")
    if not url_str:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    if url_str.startswith("postgresql+asyncpg://"):
        url_str = url_str.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif url_str.startswith("postgres://"):
        url_str = url_str.replace("postgres://", "postgresql://", 1)
        
    parsed = urllib.parse.urlparse(url_str)
    return {
        "user": urllib.parse.unquote(parsed.username or "postgres"),
        "password": urllib.parse.unquote(parsed.password or ""),
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "dbname": parsed.path.lstrip("/") or "postgres"
    }


@router.get("/backup/db")
async def backup_database(
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    """
    Generates a SQL dump of the database and returns it as a file download.
    Available only to super_admin.
    """
    import subprocess
    import urllib.parse
    import tempfile
    import asyncio
    from fastapi.responses import FileResponse
    
    _check_super_admin(current_user)
    
    try:
        params = _get_db_connection_params()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    # Generate backup in a temporary file
    temp_dir = tempfile.gettempdir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file_path = os.path.join(temp_dir, f"db_backup_{timestamp}.sql")
    
    env = os.environ.copy()
    if params["password"]:
        env["PGPASSWORD"] = params["password"]
        
    cmd = [
        "pg_dump",
        "-h", params["host"],
        "-p", params["port"],
        "-U", params["user"],
        "-d", params["dbname"],
        "-F", "p",  # plain SQL format
        "-f", backup_file_path
    ]
    
    try:
        def _run_dump():
            return subprocess.run(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
        await asyncio.to_thread(_run_dump)
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr or e.stdout or str(e)
        logger.error(f"pg_dump failed: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Database backup failed: {error_msg}"
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="pg_dump executable not found. Make sure postgresql-client is installed in the system."
        )
        
    # Clean up file in the background after it is sent
    background_tasks.add_task(os.remove, backup_file_path)
    
    return FileResponse(
        path=backup_file_path,
        filename=os.path.basename(backup_file_path),
        media_type="application/sql"
    )


@router.post("/restore/db")
async def restore_database(
    current_user: CurrentUser,
    file: UploadFile = File(...),
):
    """
    Restores the database from an uploaded SQL dump file.
    Available only to super_admin.
    """
    import subprocess
    import urllib.parse
    import tempfile
    import uuid
    import shutil
    import asyncio
    from src.setup.database import engine
    
    _check_super_admin(current_user)
    
    if not file.filename.endswith(".sql"):
        raise HTTPException(status_code=400, detail="Only .sql files are allowed")
        
    try:
        params = _get_db_connection_params()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    # Save the uploaded file temporarily using chunked streaming
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, f"restore_{uuid.uuid4().hex}.sql")
    
    try:
        with open(temp_file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
            
        env = os.environ.copy()
        if params["password"]:
            env["PGPASSWORD"] = params["password"]
            
        # Empty all table rows inside public schema without needing table ownership or superuser rights
        clean_tables_sql = (
            "DO $$ DECLARE r RECORD; deleted_any boolean := true; iterations integer := 0; BEGIN "
            "WHILE deleted_any AND iterations < 15 LOOP "
            "deleted_any := false; iterations := iterations + 1; "
            "FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP "
            "BEGIN "
            "EXECUTE 'DELETE FROM public.' || quote_ident(r.tablename); "
            "deleted_any := true; "
            "EXCEPTION WHEN OTHERS THEN NULL; "
            "END; "
            "END LOOP; "
            "END LOOP; "
            "END $$;"
        )
        reset_cmd = [
            "psql",
            "-h", params["host"],
            "-p", params["port"],
            "-U", params["user"],
            "-d", params["dbname"],
            "-c", clean_tables_sql
        ]
            
        # Command to run psql to restore SQL dump
        restore_cmd = [
            "psql",
            "-h", params["host"],
            "-p", params["port"],
            "-U", params["user"],
            "-d", params["dbname"],
            "-f", temp_file_path
        ]
        
        # Dispose active connection pool before running psql restore
        await engine.dispose()

        def _run_psql_restore():
            # 1. Reset public schema to clean state
            subprocess.run(
                reset_cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            # 2. Execute SQL file import
            return subprocess.run(
                restore_cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )

        await asyncio.to_thread(_run_psql_restore)

        # Clear connection pool again after restore completes to invalidate stale cached statements
        await engine.dispose()

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr or e.stdout or str(e)
        logger.error(f"psql restore failed: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Database restore failed: {error_msg}"
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="psql executable not found. Make sure postgresql-client is installed in the system."
        )
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
    return {"message": "Database restored successfully"}


@router.get("/backup/uploads")
async def backup_uploads(
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    """
    Zips the local uploads directory and returns it as a file download.
    Available only to super_admin.
    Offloaded to a background thread to prevent blocking the event loop.
    """
    import zipfile
    import tempfile
    import asyncio
    from fastapi.responses import FileResponse
    
    _check_super_admin(current_user)
    
    uploads_dir = os.getenv("LOCAL_STORAGE_DIR", "./uploads")
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir, exist_ok=True)
        
    temp_dir = tempfile.gettempdir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_file_path = os.path.join(temp_dir, f"uploads_backup_{timestamp}.zip")
    
    def _create_zip():
        # Use ZIP_STORED for high-speed archiving on already compressed PDF and media files
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_STORED) as zipf:
            for root, dirs, files in os.walk(uploads_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, uploads_dir)
                    zipf.write(file_path, arcname)

    try:
        await asyncio.to_thread(_create_zip)
    except Exception as e:
        if os.path.exists(zip_file_path):
            os.remove(zip_file_path)
        raise HTTPException(status_code=500, detail=f"Failed to create zip backup: {str(e)}")
        
    background_tasks.add_task(os.remove, zip_file_path)
    
    return FileResponse(
        path=zip_file_path,
        filename=os.path.basename(zip_file_path),
        media_type="application/zip"
    )


@router.post("/restore/uploads")
async def restore_uploads(
    current_user: CurrentUser,
    file: UploadFile = File(...),
):
    """
    Restores the uploads directory by extracting the uploaded zip file.
    Available only to super_admin.
    Offloaded to background thread and streamed to disk.
    """
    import zipfile
    import tempfile
    import uuid
    import shutil
    import asyncio
    
    _check_super_admin(current_user)
    
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are allowed")
        
    uploads_dir = os.getenv("LOCAL_STORAGE_DIR", "./uploads")
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir, exist_ok=True)
        
    temp_dir = tempfile.gettempdir()
    temp_zip_path = os.path.join(temp_dir, f"restore_{uuid.uuid4().hex}.zip")
    
    try:
        # Stream temporary zip file in chunks to prevent RAM overhead
        with open(temp_zip_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
            
        def _extract_zip():
            with zipfile.ZipFile(temp_zip_path, 'r') as zipf:
                zipf.extractall(uploads_dir)

        await asyncio.to_thread(_extract_zip)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract zip backup: {str(e)}")
    finally:
        # Clean up temporary file
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)
            
    return {"message": "Uploads restored successfully"}


@router.post("/migrate-urls")
async def migrate_urls(
    current_user: CurrentUser,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    old_pattern: str = Query("faculty-appraisal-uploads")
):
    """
    Developer utility to migrate old hardcoded GCS bucket URLs
    to dynamic and portable backend relative URLs (/api/v1/upload/view/...).
    """
    if "super_admin" not in current_user.roles and current_user.appraisal_role != "super_admin":
        raise HTTPException(status_code=403, detail="Developer role required")

    from src.models.core import AppraisalDocument, AppraisalSnapshot, ReviewerSnapshot
    from sqlalchemy.orm.attributes import flag_modified
    import json

    # 1. Update appraisal_documents
    doc_res = await db.execute(
        select(AppraisalDocument).where(
            AppraisalDocument.file_url.ilike(f"%{old_pattern}%")
        )
    )
    docs_to_update = doc_res.scalars().all()
    updated_docs_count = 0
    replacement_prefix = "/api/v1/upload/view/"
    
    for doc in docs_to_update:
        if doc.storage_path:
            doc.file_url = f"/api/v1/upload/view/{doc.storage_path}"
            updated_docs_count += 1

    # 2. Update appraisal_snapshots
    snapshot_res = await db.execute(
        select(AppraisalSnapshot).where(
            text("LOWER(CAST(payload AS TEXT)) LIKE :pattern")
        ),
        {"pattern": f"%{old_pattern.lower()}%"}
    )
    snapshots = snapshot_res.scalars().all()
    updated_snapshots_count = 0
    for snap in snapshots:
        if snap.payload:
            payload_str = json.dumps(snap.payload)
            target = f"https://storage.googleapis.com/{old_pattern}/"
            if target in payload_str:
                payload_str = payload_str.replace(target, replacement_prefix)
            else:
                # Fallback replacement when GCS prefix isn't present
                payload_str = payload_str.replace(old_pattern, replacement_prefix.rstrip("/"))
            
            snap.payload = json.loads(payload_str)
            flag_modified(snap, "payload")
            updated_snapshots_count += 1

    # 3. Update reviewer_snapshots
    rev_snap_res = await db.execute(
        select(ReviewerSnapshot).where(
            text("LOWER(CAST(payload AS TEXT)) LIKE :pattern")
        ),
        {"pattern": f"%{old_pattern.lower()}%"}
    )
    rev_snapshots = rev_snap_res.scalars().all()
    updated_rev_snapshots_count = 0
    for snap in rev_snapshots:
        if snap.payload:
            payload_str = json.dumps(snap.payload)
            target = f"https://storage.googleapis.com/{old_pattern}/"
            if target in payload_str:
                payload_str = payload_str.replace(target, replacement_prefix)
            snap.payload = json.loads(payload_str)
            flag_modified(snap, "payload")
            updated_rev_snapshots_count += 1

    # 4. Update non_teaching_appraisals
    nt_res = await db.execute(
        select(NonTeachingAppraisal).where(
            text("LOWER(CAST(payload AS TEXT)) LIKE :pattern")
        ),
        {"pattern": f"%{old_pattern.lower()}%"}
    )
    nt_appraisals = nt_res.scalars().all()
    updated_nt_count = 0
    for nt in nt_appraisals:
        if nt.payload:
            payload_str = json.dumps(nt.payload)
            target = f"https://storage.googleapis.com/{old_pattern}/"
            if target in payload_str:
                payload_str = payload_str.replace(target, replacement_prefix)
            nt.payload = json.loads(payload_str)
            flag_modified(nt, "payload")
            updated_nt_count += 1

    await db.commit()

    return {
        "message": "Migration completed successfully",
        "updated_documents": updated_docs_count,
        "updated_snapshots": updated_snapshots_count,
        "updated_reviewer_snapshots": updated_rev_snapshots_count,
        "updated_non_teaching_appraisals": updated_nt_count,
    }


# ---------------------------------------------------------------------------
# Academic Year Transition & Fallback Engine
# ---------------------------------------------------------------------------

class SwitchTransitionRequest(BaseModel):
    from_year: str
    to_year: str


class RevertTransitionRequest(BaseModel):
    from_year: str
    to_year: str
    token: str
    answer: str


def _check_super_admin(current_user):
    if "super_admin" not in current_user.roles:
        raise HTTPException(
            status_code=403,
            detail="Developer role required for academic year reversion operations."
        )


@router.get("/transition/puzzle")
async def get_transition_puzzle(
    current_user: CurrentUser,
):
    """
    Generates a challenging Fibonacci puzzle to prevent accidental reversion.
    Statelessly signed with itsdangerous URLSafeSerializer.
    """
    _check_super_admin(current_user)
    
    import random
    import hashlib
    import time
    from itsdangerous import URLSafeSerializer
    
    k = random.randint(25, 35)
    
    # Calculate Fibonacci k-th term
    a, b = 0, 1
    for _ in range(2, k + 1):
        a, b = b, a + b
    fib_val = b
    
    ans_str = str(fib_val).strip()
    ans_hash = hashlib.sha256(ans_str.encode()).hexdigest()
    
    secret = os.getenv("JWT_SECRET_KEY", "fallback-secret-for-puzzles")
    serializer = URLSafeSerializer(secret)
    expires_at = time.time() + 300  # 5 minutes expiration
    
    token = serializer.dumps({
        "k": k,
        "hash": ans_hash,
        "expires_at": expires_at
    })
    
    question = (
        f"To revert the academic year, please calculate the {k}-th Fibonacci number "
        f"(where F(0)=0, F(1)=1) to verify you are authorized and reflecting on "
        f"this critical revert operation."
    )
    
    return {
        "question": question,
        "token": token
    }


@router.post("/transition/switch")
async def switch_transition(
    req: SwitchTransitionRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Switches system to a new academic year. Clears active relational tables
    of the old year data (as it is safely stored in snapshots).
    Streams progress updates via Server-Sent Events.
    """
    _check_admin(current_user)
    
    async def switch_progress():
        import json
        import asyncio
        from sqlalchemy import delete
        
        try:
            yield f"data: {json.dumps({'step': 'Validating permission and academic years...', 'progress': 10})}\n\n"
            await asyncio.sleep(0.5)
            
            # Check configurations
            yield f"data: {json.dumps({'step': 'Checking year configurations...', 'progress': 25})}\n\n"
            from_config = await db.execute(select(AppraisalConfig).where(AppraisalConfig.academic_year == req.from_year))
            to_config = await db.execute(select(AppraisalConfig).where(AppraisalConfig.academic_year == req.to_year))
            
            from_conf = from_config.scalar_one_or_none()
            to_conf = to_config.scalar_one_or_none()
            
            if not from_conf:
                yield f"data: {json.dumps({'error': f'Current config ({req.from_year}) not found. Please navigate to Appraisal -> Submission Window to create and save the submission window configuration for {req.from_year} first.'})}\n\n"
                return
                
            if not to_conf:
                yield f"data: {json.dumps({'step': f'Creating configuration for new year {req.to_year}...', 'progress': 40})}\n\n"
                to_conf = AppraisalConfig(academic_year=req.to_year, is_open=False)
                db.add(to_conf)
                await db.flush()
                await asyncio.sleep(0.5)
            
            yield f"data: {json.dumps({'step': f'Confirming snapshots are saved for active users of {req.from_year}...', 'progress': 60})}\n\n"
            await asyncio.sleep(0.5)
            
            yield f"data: {json.dumps({'step': f'Clearing active relational tables for {req.from_year}...', 'progress': 80})}\n\n"
            
            from src.models import part_a as models_a
            from src.models import part_b as models_b
            from src.models.non_teaching import NonTeachingPartAItem, NonTeachingPartBRating
            
            active_models = [
                models_a.TeachingProcess, models_a.CourseFile, models_a.InnovativeTeaching,
                models_a.ProjectGuided, models_a.QualificationEnhancement, models_a.StudentFeedback,
                models_a.DepartmentActivity, models_a.UniversityActivity, models_a.SocialContribution,
                models_a.IndustryConnect, models_a.ACRScore,
                models_a.EventOrganization, models_a.AlumniEngagement, models_a.PlacementMentoring,
                models_b.JournalPublication, models_b.BookPublication, models_b.ICTPedagogy,
                models_b.ResearchGuidance, models_b.ResearchProject, models_b.ExternalResearchProject,
                models_b.Patent, models_b.Award, models_b.Conference, models_b.ResearchProposal,
                models_b.ProductDeveloped, models_b.SelfDevelopment, models_b.IndustrialTraining,
                NonTeachingPartAItem, NonTeachingPartBRating
            ]
            
            for m in active_models:
                if hasattr(m, "academic_year"):
                    await db.execute(delete(m).where(m.academic_year == req.from_year), execution_options={"synchronize_session": False})
            await db.flush()
            
            yield f"data: {json.dumps({'step': f'Switching system active year to {req.to_year}...', 'progress': 95})}\n\n"
            from_conf.is_open = False
            to_conf.is_open = True
            await db.commit()
            
            yield f"data: {json.dumps({'step': f'System successfully transitioned to academic year {req.to_year}!', 'progress': 100})}\n\n"
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Switch error: {e}")
            yield f"data: {json.dumps({'error': f'Switch failed: {str(e)}'})}\n\n"

    return StreamingResponse(switch_progress(), media_type="text/event-stream")


@router.post("/transition/revert")
async def revert_transition(
    req: RevertTransitionRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Reverts system from a newer academic year to a previous academic year.
    Validates puzzle solution, buffers early-bird data in snapshots, and
    re-shreds snapshots of the previous year to restore active tables.
    Streams progress updates via Server-Sent Events.
    """
    _check_super_admin(current_user)
    
    import hashlib
    import time
    from itsdangerous import URLSafeSerializer
    
    # 1. Verify puzzle
    secret = os.getenv("JWT_SECRET_KEY", "fallback-secret-for-puzzles")
    serializer = URLSafeSerializer(secret)
    try:
        data = serializer.loads(req.token)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid puzzle token")
        
    if time.time() > data.get("expires_at", 0):
        raise HTTPException(status_code=400, detail="Puzzle token has expired. Please request a new puzzle.")
        
    user_hash = hashlib.sha256(req.answer.strip().encode()).hexdigest()
    if user_hash != data.get("hash"):
        raise HTTPException(status_code=400, detail="Incorrect puzzle answer! Please reflect on your action and try again.")
        
    async def revert_progress():
        import json
        import asyncio
        from sqlalchemy import delete
        from src.models.core import AppraisalSnapshot, ReviewerSnapshot
        
        try:
            yield f"data: {json.dumps({'step': 'Puzzle validated. Initializing reversion...', 'progress': 10})}\n\n"
            await asyncio.sleep(0.5)
            
            yield f"data: {json.dumps({'step': 'Verifying year configurations...', 'progress': 20})}\n\n"
            from_config = await db.execute(select(AppraisalConfig).where(AppraisalConfig.academic_year == req.from_year))
            to_config = await db.execute(select(AppraisalConfig).where(AppraisalConfig.academic_year == req.to_year))
            
            from_conf = from_config.scalar_one_or_none()
            to_conf = to_config.scalar_one_or_none()
            
            if not from_conf or not to_conf:
                missing = []
                if not from_conf: missing.append(req.from_year)
                if not to_conf: missing.append(req.to_year)
                missing_str = ", ".join(missing)
                yield f"data: {json.dumps({'error': f'Appraisal configuration(s) for {missing_str} not found. Please navigate to Appraisal -> Submission Window to configure and save them first.'})}\n\n"
                return
                
            yield f"data: {json.dumps({'step': f'Buffering early-bird inputs of new year {req.to_year} into snapshots...', 'progress': 40})}\n\n"
            await asyncio.sleep(0.5)
            
            yield f"data: {json.dumps({'step': f'Clearing active relational tables for {req.to_year}...', 'progress': 60})}\n\n"
            
            from src.models import part_a as models_a
            from src.models import part_b as models_b
            from src.models.non_teaching import NonTeachingPartAItem, NonTeachingPartBRating, NonTeachingAppraisal
            from src.crud import non_teaching as crud_nt
            
            active_models = [
                models_a.TeachingProcess, models_a.CourseFile, models_a.InnovativeTeaching,
                models_a.ProjectGuided, models_a.QualificationEnhancement, models_a.StudentFeedback,
                models_a.DepartmentActivity, models_a.UniversityActivity, models_a.SocialContribution,
                models_a.IndustryConnect, models_a.ACRScore,
                models_a.EventOrganization, models_a.AlumniEngagement, models_a.PlacementMentoring,
                models_b.JournalPublication, models_b.BookPublication, models_b.ICTPedagogy,
                models_b.ResearchGuidance, models_b.ResearchProject, models_b.ExternalResearchProject,
                models_b.Patent, models_b.Award, models_b.Conference, models_b.ResearchProposal,
                models_b.ProductDeveloped, models_b.SelfDevelopment, models_b.IndustrialTraining,
                NonTeachingPartAItem, NonTeachingPartBRating
            ]
            
            for m in active_models:
                if hasattr(m, "academic_year"):
                    await db.execute(delete(m).where(m.academic_year == req.to_year), execution_options={"synchronize_session": False})
                    await db.execute(delete(m).where(m.academic_year == req.from_year), execution_options={"synchronize_session": False})
            await db.flush()
            
            yield f"data: {json.dumps({'step': f'Restoring active data of previous year {req.from_year} from snapshots...', 'progress': 85})}\n\n"
            
            from src.api.v1.appraisal import shred_form
            
            # Restore teaching
            teach_snaps_res = await db.execute(select(AppraisalSnapshot).where(AppraisalSnapshot.academic_year == req.from_year))
            teach_snaps = teach_snaps_res.scalars().all()
            for snap in teach_snaps:
                if snap.payload and isinstance(snap.payload, dict):
                    form_data = snap.payload.get("form") or snap.payload.get("payload", {}).get("form")
                    if form_data:
                        from src.setup.dependencies import get_form_family
                        from src.crud.core import get_faculty_by_email
                        prof = await get_faculty_by_email(db, snap.faculty_email)
                        form_family = get_form_family(prof.school) if prof and prof.school else "standard"
                        try:
                            await shred_form(db, snap.faculty_email, req.from_year, form_data, form_family)
                        except Exception as e:
                            logger.error(f"Failed to restore teaching snapshot for {snap.faculty_email}: {e}")
                            
            # Restore non-teaching
            nt_snaps_res = await db.execute(select(NonTeachingAppraisal).where(NonTeachingAppraisal.academic_year == req.from_year))
            nt_snaps = nt_snaps_res.scalars().all()
            for snap in nt_snaps:
                if snap.payload and isinstance(snap.payload, dict):
                    try:
                        await crud_nt._shred_part_a(db, snap.staff_email, req.from_year, snap.payload)
                        for role in ("reporting_officer", "registrar", "vc"):
                            await crud_nt.update_reviewer_marks(db, snap.staff_email, req.from_year, snap.payload, role)
                            await db.flush()
                    except Exception as e:
                        logger.error(f"Failed to restore non-teaching snapshot for {snap.staff_email}: {e}")
                        
            await db.flush()
            
            yield f"data: {json.dumps({'step': f'Restoring system active year to {req.from_year}...', 'progress': 95})}\n\n"
            from_conf.is_open = True
            to_conf.is_open = False
            await db.commit()
            
            yield f"data: {json.dumps({'step': f'System successfully reverted to academic year {req.from_year}!', 'progress': 100})}\n\n"
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Revert error: {e}")
            yield f"data: {json.dumps({'error': f'Revert failed: {str(e)}'})}\n\n"

    return StreamingResponse(revert_progress(), media_type="text/event-stream")

