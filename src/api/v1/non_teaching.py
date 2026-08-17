from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.setup.database import get_db
from src.setup.dependencies import CurrentUser
from src.models.non_teaching import (
    NonTeachingAppraisal,
    NTWorkflowTemplate, NTWorkflowTemplateStep, NTWorkflowAssignment,
    NTWorkflowInstance, NTWorkflowInstanceStep, NTDesignation,
)
from src.crud import non_teaching as crud
from src.models.core import FacultyProfile
from sqlalchemy import select
from datetime import datetime
from typing import Optional, Dict, Any

_DRAFT_STATUSES = {'Draft', 'Pending Registrar Review'}
_SUBMITTED_STATUSES = {'Pending RO Review', 'Pending Registrar Review'}

router = APIRouter(prefix="/non-teaching", tags=["Non-Teaching"])


async def _resolve_template(
    db: AsyncSession,
    staff_email: Optional[str],
    appraisal_role: Optional[str],
    department: Optional[str],
) -> Optional[NTWorkflowTemplate]:
    """Priority: individual > department > role > default"""
    _step_chain = (
        selectinload(NTWorkflowTemplate.steps)
        .selectinload(NTWorkflowTemplateStep.designation_obj)
    )
    _assign_chain = (
        selectinload(NTWorkflowAssignment.template)
        .selectinload(NTWorkflowTemplate.steps)
        .selectinload(NTWorkflowTemplateStep.designation_obj)
    )

    if staff_email is not None:
        res = await db.execute(
            select(NTWorkflowAssignment).options(_assign_chain)
            .where(NTWorkflowAssignment.staff_email == staff_email)
        )
        a = res.scalar_one_or_none()
        if a:
            return a.template

    if department:
        res = await db.execute(
            select(NTWorkflowAssignment).options(_assign_chain)
            .where(NTWorkflowAssignment.department == department)
        )
        a = res.scalar_one_or_none()
        if a:
            return a.template

    if appraisal_role:
        res = await db.execute(
            select(NTWorkflowAssignment).options(_assign_chain)
            .where(NTWorkflowAssignment.appraisal_role == appraisal_role)
        )
        a = res.scalar_one_or_none()
        if a:
            return a.template

    res = await db.execute(
        select(NTWorkflowTemplate)
        .options(_step_chain)
        .where(NTWorkflowTemplate.is_default == True, NTWorkflowTemplate.is_active == True)
    )
    return res.scalar_one_or_none()


@router.get("/workflow-template")
async def get_workflow_template(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    role: str = Query(...),
    reports_directly: bool = Query(False),
):
    """Returns the configured approval chain for a given NT role (used by admin preview)."""
    template = await _resolve_template(db, staff_email=None, appraisal_role=role, department=None)
    if not template:
        return {"workflowName": "Non Teaching Approval Flow", "steps": []}
    return {
        "workflowName": template.name,
        "steps": [
            {
                "stepNo":      s.step_no,
                "designation": s.designation_obj.name if s.designation_obj else "Unknown",
                "status":      "WAITING",
            }
            for s in (template.steps or [])
        ],
    }


@router.get("/workflow/{email}")
async def get_workflow_for_staff(
    email: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    academic_year: str = Query(...),
):
    """Returns live workflow status for a specific NT staff member."""
    clean_email = email.strip().lower()
    profile_res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == clean_email))
    profile = profile_res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Staff not found")

    inst_res = await db.execute(
        select(NTWorkflowInstance)
        .options(selectinload(NTWorkflowInstance.instance_steps))
        .where(NTWorkflowInstance.staff_email == clean_email, NTWorkflowInstance.academic_year == academic_year)
    )
    instance = inst_res.scalar_one_or_none()

    if not instance:
        template = await _resolve_template(db, email, profile.appraisal_role, profile.department)
        return {
            "workflowId":   None,
            "workflowName": template.name if template else "Non Teaching Approval Flow",
            "currentStep":  None,
            "status":       "NOT_STARTED",
            "profile_picture_url": profile.profile_picture_url,
            "steps": [
                {
                    "stepNo":      s.step_no,
                    "designation": s.designation_obj.name if s.designation_obj else "?",
                    "status":      "WAITING",
                }
                for s in (template.steps if template else [])
            ],
        }

    isteps = sorted(instance.instance_steps, key=lambda s: s.step_no)
    return {
        "workflowId":   str(instance.id),
        "workflowName": "Non Teaching Approval Flow",
        "currentStep":  instance.current_step,
        "status":       instance.status,
        "profile_picture_url": profile.profile_picture_url,
        "steps": [
            {"stepNo": s.step_no, "designation": s.designation, "status": s.status}
            for s in isteps
        ],
    }


@router.get("/appraisal")
async def get_my_appraisal(academic_year: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    appr = await crud.get_non_teaching_appraisal(db, current_user.email, academic_year)
    if not appr:
        return None
    
    res_dict = {c.name: getattr(appr, c.name) for c in appr.__table__.columns}
    profile_res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == current_user.email))
    profile = profile_res.scalar_one_or_none()
    res_dict["profile_picture_url"] = profile.profile_picture_url if profile else None
    return res_dict


@router.put("/appraisal")
async def upsert_my_appraisal(data: Dict[str, Any], current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    data['staff_email'] = current_user.email

    profile_res = await db.execute(
        select(FacultyProfile).where(FacultyProfile.email == current_user.email)
    )
    profile = profile_res.scalar_one_or_none()

    # For direct-to-registrar staff, route Draft → Pending Registrar Review
    if data.get('status') in (None, 'Draft', 'Pending RO Review'):
        if profile and profile.reports_to_registrar:
            academic_year = data.get('academic_year')
            if academic_year:
                existing = await crud.get_non_teaching_appraisal(db, current_user.email, academic_year)
                if not existing or existing.status in _DRAFT_STATUSES:
                    data['status'] = 'Pending Registrar Review'

    appraisal = await crud.create_or_update_non_teaching_appraisal(db, data)

    # Create workflow instance on first submission (idempotent)
    if data.get('status') in _SUBMITTED_STATUSES:
        academic_year = data.get('academic_year')
        if academic_year:
            inst_check = await db.execute(
                select(NTWorkflowInstance).where(
                    NTWorkflowInstance.staff_email == current_user.email,
                    NTWorkflowInstance.academic_year == academic_year,
                )
            )
            if not inst_check.scalar_one_or_none():
                template = await _resolve_template(
                    db, current_user.email,
                    profile.appraisal_role if profile else None,
                    profile.department if profile else None,
                )
                if template and template.steps:
                    instance = NTWorkflowInstance(
                        appraisal_id=appraisal.id,
                        template_id=template.id,
                        staff_email=current_user.email,
                        academic_year=academic_year,
                        current_step=template.steps[0].step_no,
                        status="PENDING",
                    )
                    db.add(instance)
                    await db.flush()
                    for step in template.steps:
                        db.add(NTWorkflowInstanceStep(
                            instance_id=instance.id,
                            step_no=step.step_no,
                            designation=step.designation_obj.name if step.designation_obj else "?",
                            status="PENDING" if step.step_no == template.steps[0].step_no else "WAITING",
                        ))
                    await db.commit()

    return appraisal


@router.get("/subordinates")
async def get_non_teaching_subordinates(
    academic_year: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    query = select(NonTeachingAppraisal, FacultyProfile).join(
        FacultyProfile, NonTeachingAppraisal.staff_email == FacultyProfile.email
    ).where(NonTeachingAppraisal.academic_year == academic_year)

    allowed_roles = {"registrar", "vc", "reporting_officer", "admin", "super_admin"}
    if not any(r in current_user.roles for r in allowed_roles):
        return []

    if "vc" in current_user.roles:
        pass
    elif "registrar" in current_user.roles:
        query = query.where(FacultyProfile.registrar_email == current_user.email)
    elif "reporting_officer" in current_user.roles:
        query = query.where(
            FacultyProfile.reporting_officer_email == current_user.email,
            FacultyProfile.reports_to_registrar == False,
        )

    result = await db.execute(query)
    rows = result.all()

    # Get reviewer's own designation for workflow-step matching
    reviewer_res = await db.execute(
        select(FacultyProfile).where(FacultyProfile.email == current_user.email)
    )
    reviewer_profile = reviewer_res.scalar_one_or_none()
    reviewer_designation = reviewer_profile.designation if reviewer_profile else None

    subordinates = []
    for appr, profile in rows:
        if reviewer_designation:
            inst_res = await db.execute(
                select(NTWorkflowInstance)
                .options(selectinload(NTWorkflowInstance.instance_steps))
                .where(
                    NTWorkflowInstance.staff_email == appr.staff_email,
                    NTWorkflowInstance.academic_year == academic_year,
                )
            )
            instance = inst_res.scalar_one_or_none()
            if instance:
                pending = next(
                    (s for s in instance.instance_steps if s.status == "PENDING"), None
                )
                if not pending or pending.designation != reviewer_designation:
                    continue

        subordinates.append({
            "staff_email":    appr.staff_email,
            "name":           profile.full_name,
            "designation":    profile.designation,
            "department":     profile.department,
            "appraisalRole":  profile.appraisal_role,
            "status":         appr.status,
            "submittedOn":    appr.submitted_at.date() if appr.submitted_at else None,
            "selfTotal":      appr.self_total,
            "roTotal":        appr.ro_total or 0,
            "registrarTotal": appr.registrar_total or 0,
            "vcTotal":        appr.vc_total or 0,
            "payload":        appr.payload,
            "profile_picture_url": profile.profile_picture_url,
        })

    return subordinates


@router.put("/review/{email}")
async def review_non_teaching(email: str, data: Dict[str, Any], current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    clean_email = email.strip().lower()
    target_res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == clean_email))
    target = target_res.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Staff profile not found")

    is_assigned_ro = (
        "reporting_officer" in current_user.roles
        and target.reporting_officer_email == current_user.email
    )
    is_assigned_registrar = (
        "registrar" in current_user.roles
        and target.registrar_email == current_user.email
    )
    if not is_assigned_ro and not is_assigned_registrar and not current_user.has_authority_over(
        email, target.appraisal_role, target.department, target.school
    ):
        raise HTTPException(status_code=403, detail="Not authorized to view this staff's data")

    academic_year = data.get('academic_year')
    if not academic_year:
        raise HTTPException(status_code=422, detail="academic_year is required")
    appr = await crud.get_non_teaching_appraisal(db, email, academic_year)
    if not appr:
        raise HTTPException(status_code=404, detail="Appraisal not found")

    role_config = {
        "reporting_officer": ("ro_total", "Reporting Officer Reviewed", "ro_reviewed_at"),
        "registrar":         ("registrar_total", "Registrar Reviewed",  "registrar_reviewed_at"),
        "vc":                ("vc_total",        "VC Approved",          "vc_reviewed_at"),
    }

    primary_role = next((r for r in current_user.roles if r in role_config), None)
    if not primary_role and "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Invalid reviewer role")
    if "admin" in current_user.roles and not primary_role:
        primary_role = "registrar"

    field, next_status, time_field = role_config[primary_role]

    if primary_role == "reporting_officer" and target.reports_to_registrar:
        raise HTTPException(
            status_code=403,
            detail="This staff member reports directly to the Registrar. Reporting Officer review does not apply."
        )

    appr.status = next_status
    setattr(appr, time_field, datetime.utcnow())

    if 'payload' in data:
        appr.payload = data['payload']
    if 'total_score' in data:
        setattr(appr, field, data['total_score'])

    if data.get('payload'):
        await crud.update_reviewer_marks(db, email, academic_year, data['payload'], primary_role)

    # Advance workflow instance
    inst_res = await db.execute(
        select(NTWorkflowInstance)
        .options(selectinload(NTWorkflowInstance.instance_steps))
        .where(NTWorkflowInstance.staff_email == email, NTWorkflowInstance.academic_year == academic_year)
    )
    instance = inst_res.scalar_one_or_none()
    if instance:
        for istep in instance.instance_steps:
            if istep.step_no == instance.current_step:
                istep.status = "APPROVED"
                istep.reviewer_email = current_user.email
                istep.reviewed_at = datetime.utcnow()
                if 'total_score' in data:
                    istep.score = data['total_score']
                break

        waiting = sorted(
            [s for s in instance.instance_steps if s.status == "WAITING"],
            key=lambda s: s.step_no,
        )
        if waiting:
            waiting[0].status = "PENDING"
            instance.current_step = waiting[0].step_no
        else:
            instance.current_step = None
            instance.status = "COMPLETED"
        instance.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(appr)
    return appr
