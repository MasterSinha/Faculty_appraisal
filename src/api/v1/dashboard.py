from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.setup.database import get_db
from src.setup.dependencies import CurrentUser, ENGINEERING_SCHOOLS, NON_ENGINEERING_SCHOOLS
from src.models.core import FacultyProfile, Declaration, AppraisalSnapshot, AppraisalReview
from sqlalchemy import select, and_
from collections import defaultdict
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/subordinates")
async def get_subordinates(
    current_user: CurrentUser,
    academic_year: str = Query(...),
    reviewer_role: Optional[str] = Query(None),
    pending_status: Optional[str] = Query(None),
    reviewer_school: Optional[str] = Query(None),
    reviewer_department: Optional[str] = Query(None),
    schools: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    # Use query-param school/dept as fallback when current_user fields are not populated
    effective_school = current_user.school or reviewer_school
    effective_dept = current_user.department or reviewer_department

    query = select(FacultyProfile, Declaration).outerjoin(
        Declaration,
        and_(
            FacultyProfile.email == Declaration.faculty_email,
            Declaration.academic_year == academic_year
        )
    )

    # Authority-based filtering (security comes from current_user, not query params)
    if any(r in current_user.roles for r in ("super_admin", "admin")):
        if schools:
            school_list = [s.strip() for s in schools.split(",")]
            query = query.where(FacultyProfile.school.in_(school_list))
    elif "vc" in current_user.roles or "registrar" in current_user.roles:
        if schools:
            school_list = [s.strip() for s in schools.split(",")]
            query = query.where(FacultyProfile.school.in_(school_list))
    elif "dean" in current_user.roles:
        dean_school = effective_school
        if dean_school == "engineering" or dean_school in ENGINEERING_SCHOOLS:
            query = query.where(FacultyProfile.school.in_(ENGINEERING_SCHOOLS))
        elif dean_school == "non_engineering" or dean_school in NON_ENGINEERING_SCHOOLS:
            query = query.where(FacultyProfile.school.in_(NON_ENGINEERING_SCHOOLS))
        else:
            logger.warning(f"Dean {current_user.email} has unrecognised school value '{dean_school}' — returning empty")
            return []
    elif "center_head" in current_user.roles:
        query = query.where(FacultyProfile.school == "CISR")
    elif "director" in current_user.roles or "reporting_officer" in current_user.roles:
        query = query.where(FacultyProfile.school == effective_school)
    elif "hod" in current_user.roles:
        query = query.where(
            FacultyProfile.school == effective_school,
            FacultyProfile.department == effective_dept
        )
    else:
        return []

    result = await db.execute(query)
    rows = result.all()

    faculty_emails = [faculty.email for faculty, _ in rows]
    reviews_by_email: dict[str, list] = defaultdict(list)
    if faculty_emails:
        rev_res = await db.execute(
            select(AppraisalReview).where(
                AppraisalReview.faculty_email.in_(faculty_emails),
                AppraisalReview.academic_year == academic_year
            )
        )
        for rev in rev_res.scalars().all():
            reviews_by_email[rev.faculty_email].append(rev)

    subordinates = []
    for faculty, decl in rows:
        sub = {
            "email": faculty.email,
            "name": faculty.full_name,
            "department": faculty.department,
            "school": faculty.school,
            "appraisal_role": faculty.appraisal_role,
            "designation": faculty.designation,
            "status": decl.status if decl else "pending",
            "submitted_at": decl.submitted_at.isoformat() if decl and decl.submitted_at else None,
            "part_a_total": float(decl.part_a_total) if decl and decl.part_a_total is not None else 0,
            "part_b_total": float(decl.part_b_total) if decl and decl.part_b_total is not None else 0,
            "grand_total": float(decl.grand_total) if decl and decl.grand_total is not None else 0,
            "hod_total": 0, "hod_part_a": 0, "hod_part_b": 0, "hod_remarks": "",
            "director_total": 0, "director_part_a": 0, "director_part_b": 0, "director_remarks": "",
            "dean_total": 0, "dean_part_a": 0, "dean_part_b": 0, "dean_remarks": "",
            "vc_total": 0, "vc_part_a": 0, "vc_part_b": 0, "vc_remarks": "",
        }

        for rev in reviews_by_email[faculty.email]:
            role = rev.reviewer_role
            sub[f"{role}_total"] = float(rev.total_score) if rev.total_score is not None else 0
            sub[f"{role}_part_a"] = float(rev.part_a_score) if rev.part_a_score is not None else 0
            sub[f"{role}_part_b"] = float(rev.part_b_score) if rev.part_b_score is not None else 0
            sub[f"{role}_remarks"] = rev.remarks or ""

        subordinates.append(sub)

    # Overlay NT staff statuses from non_teaching_appraisals
    from src.models.non_teaching import NonTeachingAppraisal as _NTA
    _NT_ROLES = {'non_teaching_staff', 'reporting_officer', 'registrar'}
    nt_emails = [s["email"] for s in subordinates if s.get("appraisal_role") in _NT_ROLES]
    if nt_emails:
        nt_res = await db.execute(
            select(_NTA.staff_email, _NTA.status, _NTA.submitted_at)
            .where(_NTA.staff_email.in_(nt_emails), _NTA.academic_year == academic_year)
        )
        nt_map = {email: (status, submitted_at) for email, status, submitted_at in nt_res.all()}
        for sub in subordinates:
            if sub["email"] in nt_map:
                nt_s, nt_at = nt_map[sub["email"]]
                sub["status"]       = nt_s
                sub["submitted_at"] = nt_at.isoformat() if nt_at else None

    return subordinates

@router.get("/faculty/{email}")
async def get_faculty_snapshot(email: str, academic_year: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    target_res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == email))
    target = target_res.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Faculty not found")

    if not current_user.has_authority_over(email, target.appraisal_role, target.department, target.school):
        raise HTTPException(status_code=403, detail="Not authorized to view this faculty's data")

    snapshot_res = await db.execute(select(AppraisalSnapshot).where(
        AppraisalSnapshot.faculty_email == email,
        AppraisalSnapshot.academic_year == academic_year
    ))
    snapshot = snapshot_res.scalar_one_or_none()

    rev_res = await db.execute(select(AppraisalReview).where(
        AppraisalReview.faculty_email == email,
        AppraisalReview.academic_year == academic_year
    ))
    reviews = rev_res.scalars().all()
    reviews_data = [
        {
            "reviewer_role": r.reviewer_role,
            "reviewer_email": r.reviewer_email,
            "part_a_score": float(r.part_a_score) if r.part_a_score is not None else 0,
            "part_b_score": float(r.part_b_score) if r.part_b_score is not None else 0,
            "total_score": float(r.total_score) if r.total_score is not None else 0,
            "section_scores": r.section_scores or {},
            "remarks": r.remarks,
            "status": r.status,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        }
        for r in reviews
    ]

    if snapshot is None:
        return {"reviews": reviews_data}

    import copy
    import os
    from src.api.v1.appraisal import _rewrite_payload_urls
    payload = copy.deepcopy(snapshot.payload)
    app_url = os.getenv("APP_URL", "").rstrip("/")
    _rewrite_payload_urls(payload, app_url)

    return {
        "id": str(snapshot.id),
        "faculty_email": snapshot.faculty_email,
        "academic_year": snapshot.academic_year,
        "payload": payload,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "updated_at": snapshot.updated_at.isoformat() if snapshot.updated_at else None,
        "reviews": reviews_data,
    }
