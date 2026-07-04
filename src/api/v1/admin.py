from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, UploadFile, File
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
from datetime import datetime, timezone
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
    "APP_URL", "FRONTEND_URL", "ALLOW_MOCK_USER",
    "USE_LOCAL_STORAGE", "GCP_STORAGE_BUCKET",
    # Feature flags
    "MAINTENANCE_MODE", "ALLOW_REGISTRATIONS", "EMAIL_NOTIFICATIONS",
    "DEBUG_LOGGING", "TWO_FACTOR_AUTH", "SESSION_TIMEOUT", "AUDIT_LOGGING",
})

VALID_ROLES = frozenset({
    "faculty", "non_teaching_staff", "staff", "hod", "reporting_officer",
    "section_head", "director", "center_head", "dean", "registrar", "vc",
    "admin", "hr", "super_admin",
})


def _check_admin(current_user):
    if not any(r in current_user.roles for r in ("admin", "super_admin")):
        raise HTTPException(status_code=403, detail="Admin role required")


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

    # Collect distinct years from both teaching and non-teaching tables
    t_years = await db.execute(
        select(distinct(Declaration.academic_year)).order_by(Declaration.academic_year.desc())
    )
    nt_years = await db.execute(
        select(distinct(NonTeachingAppraisal.academic_year)).order_by(NonTeachingAppraisal.academic_year.desc())
    )
    available_years = sorted(
        set([r[0] for r in t_years.all()] + [r[0] for r in nt_years.all()]),
        reverse=True,
    )

    if not academic_year:
        academic_year = available_years[0] if available_years else None

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

    if data.appraisal_role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{data.appraisal_role}'. Valid roles: {sorted(VALID_ROLES)}",
        )

    existing = await db.execute(select(FacultyProfile).where(FacultyProfile.email == data.email))
    if existing.scalar_one_or_none():
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

    result = await db.execute(select(FacultyProfile).where(FacultyProfile.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updates = data.model_dump(exclude_none=True)
    if "password" in updates:
        user.password_hash = get_password_hash(updates.pop("password"))
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

    result = await db.execute(select(FacultyProfile).where(FacultyProfile.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

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

    if not academic_year:
        years_res = await db.execute(
            select(distinct(Declaration.academic_year))
            .order_by(Declaration.academic_year.desc())
        )
        years = [r[0] for r in years_res.all()]
        academic_year = years[0] if years else None

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

    if not academic_year:
        years_res = await db.execute(
            select(distinct(Declaration.academic_year)).order_by(Declaration.academic_year.desc())
        )
        years = [r[0] for r in years_res.all()]
        academic_year = years[0] if years else None

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

    if not academic_year:
        years_res = await db.execute(
            select(distinct(Declaration.academic_year)).order_by(Declaration.academic_year.desc())
        )
        years = [r[0] for r in years_res.all()]
        academic_year = years[0] if years else None

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
# Super Admin Backup and Restore Endpoints (Database & Uploads)
# ---------------------------------------------------------------------------

def _check_super_admin(current_user: CurrentUser):
    if "super_admin" not in current_user.roles:
        raise HTTPException(
            status_code=403,
            detail="Super Admin access required for backup/restore operations"
        )


def _get_db_connection_params():
    url_str = os.getenv("DATABASE_URL")
    if not url_str:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    if url_str.startswith("postgresql+asyncpg://"):
        url_str = url_str.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif url_str.startswith("postgres://"):
        url_str = url_str.replace("postgres://", "postgresql://", 1)
        
    parsed = urllib.parse.urlparse(url_str)
    return {
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
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
        # Run pg_dump process
        subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
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
    
    _check_super_admin(current_user)
    
    if not file.filename.endswith(".sql"):
        raise HTTPException(status_code=400, detail="Only .sql files are allowed")
        
    try:
        params = _get_db_connection_params()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    # Save the uploaded file temporarily
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, f"restore_{uuid.uuid4().hex}.sql")
    
    try:
        content = await file.read()
        with open(temp_file_path, "wb") as f:
            f.write(content)
            
        env = os.environ.copy()
        if params["password"]:
            env["PGPASSWORD"] = params["password"]
            
        # Run psql command to execute SQL
        cmd = [
            "psql",
            "-h", params["host"],
            "-p", params["port"],
            "-U", params["user"],
            "-d", params["dbname"],
            "-f", temp_file_path
        ]
        
        subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
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
    """
    import zipfile
    import tempfile
    from fastapi.responses import FileResponse
    
    _check_super_admin(current_user)
    
    uploads_dir = os.getenv("LOCAL_STORAGE_DIR", "./uploads")
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir, exist_ok=True)
        
    temp_dir = tempfile.gettempdir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_file_path = os.path.join(temp_dir, f"uploads_backup_{timestamp}.zip")
    
    try:
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(uploads_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, uploads_dir)
                    zipf.write(file_path, arcname)
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
    """
    import zipfile
    import tempfile
    import uuid
    
    _check_super_admin(current_user)
    
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are allowed")
        
    uploads_dir = os.getenv("LOCAL_STORAGE_DIR", "./uploads")
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir, exist_ok=True)
        
    temp_dir = tempfile.gettempdir()
    temp_zip_path = os.path.join(temp_dir, f"restore_{uuid.uuid4().hex}.zip")
    
    try:
        # Save temporary zip file
        content = await file.read()
        with open(temp_zip_path, "wb") as f:
            f.write(content)
            
        # Extract files (merge / overwrite existing)
        with zipfile.ZipFile(temp_zip_path, 'r') as zipf:
            zipf.extractall(uploads_dir)
            
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
    db: AsyncSession = Depends(get_db),
    old_pattern: str = Query("faculty-appraisal-uploads")
):
    """
    Super Admin utility to migrate old hardcoded GCS bucket URLs
    to dynamic and portable backend relative URLs (/api/v1/upload/view/...).
    """
    if "super_admin" not in current_user.roles and current_user.appraisal_role != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin role required")

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
                payload_str = payload_str.replace(target, "/api/v1/upload/view/")
            else:
                payload_str = payload_str.replace(old_pattern, "api/v1/upload/view")
            
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
                payload_str = payload_str.replace(target, "/api/v1/upload/view/")
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
                payload_str = payload_str.replace(target, "/api/v1/upload/view/")
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
