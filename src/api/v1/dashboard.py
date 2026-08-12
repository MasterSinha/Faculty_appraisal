from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from src.setup.database import get_db
from src.setup.dependencies import CurrentUser, ENGINEERING_SCHOOLS, NON_ENGINEERING_SCHOOLS, normalize_school
from src.models.core import FacultyProfile, Declaration, AppraisalSnapshot, AppraisalReview
from sqlalchemy import select, and_
from collections import defaultdict
from typing import List, Optional
import logging
from src.setup.score_utils import compute_effective_max

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

def _extract_snapshot_form(snapshot: AppraisalSnapshot | None) -> dict:
    if not snapshot or not isinstance(snapshot.payload, dict):
        return {}

    payload = snapshot.payload
    if isinstance(payload.get("form"), dict):
        return payload["form"]

    nested = payload.get("payload")
    if isinstance(nested, dict) and isinstance(nested.get("form"), dict):
        return nested["form"]

    return {}


def _extract_snapshot_applicability(snapshot: AppraisalSnapshot | None) -> dict:
    if not snapshot or not isinstance(snapshot.payload, dict):
        return {}

    payload = snapshot.payload
    form = payload.get("form") if isinstance(payload.get("form"), dict) else None
    nested = payload.get("payload") if isinstance(payload.get("payload"), dict) else None

    if isinstance(payload.get("sectionApplicability"), dict):
        return payload["sectionApplicability"]
    if form and isinstance(form.get("sectionApplicability"), dict):
        return form["sectionApplicability"]
    if nested and isinstance(nested.get("sectionApplicability"), dict):
        return nested["sectionApplicability"]
    if nested and isinstance(nested.get("form"), dict) and isinstance(nested["form"].get("sectionApplicability"), dict):
        return nested["form"]["sectionApplicability"]

    return {}


def _extract_review_applicability(section_scores: dict | None) -> dict:
    if not isinstance(section_scores, dict):
        return {}
    value = section_scores.get("sectionApplicability")
    return value if isinstance(value, dict) else {}


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
    effective_school = normalize_school(current_user.school or reviewer_school)
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
            school_list = [normalize_school(s.strip()) for s in schools.split(",")]
            query = query.where(FacultyProfile.school.in_(school_list))
    elif "vc" in current_user.roles or "registrar" in current_user.roles:
        if schools:
            school_list = [normalize_school(s.strip()) for s in schools.split(",")]
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
    snapshots_by_email: dict[str, AppraisalSnapshot] = {}
    if faculty_emails:
        rev_res = await db.execute(
            select(AppraisalReview).where(
                AppraisalReview.faculty_email.in_(faculty_emails),
                AppraisalReview.academic_year == academic_year
            )
        )
        for rev in rev_res.scalars().all():
            reviews_by_email[rev.faculty_email].append(rev)

        snap_res = await db.execute(
            select(AppraisalSnapshot).where(
                AppraisalSnapshot.faculty_email.in_(faculty_emails),
                AppraisalSnapshot.academic_year == academic_year
            )
        )
        snapshots_by_email = {
            snap.faculty_email: snap
            for snap in snap_res.scalars().all()
        }

    subordinates = []
    for faculty, decl in rows:
        snapshot = snapshots_by_email.get(faculty.email)
        self_form = _extract_snapshot_form(snapshot)
        self_app = _extract_snapshot_applicability(snapshot)
        # Check if CreativeSchool (SoMCS, SoHSS, SoD, SoAA)
        school_norm = normalize_school(faculty.school)
        is_creative = school_norm in NON_ENGINEERING_SCHOOLS
        
        has_c_d = (academic_year >= "2025-2026") if academic_year else False

        if is_creative:
            part_a_max = 150
            part_b_max = 350
            part_c_max = 150 if has_c_d else 0
            part_d_max = 50 if has_c_d else 0
            total_max = part_a_max + part_b_max + part_c_max + part_d_max
            
            faculty_part_a_max = 150
            faculty_part_b_max = 350
            faculty_part_c_max = 150 if has_c_d else 0
            faculty_part_d_max = 50 if has_c_d else 0
            faculty_total_max = total_max
        else:
            self_max = compute_effective_max(self_form, self_app, mode="self")
            part_a_max = 200
            part_b_max = 375
            part_c_max = 150 if has_c_d else 0
            part_d_max = 50 if has_c_d else 0
            total_max = part_a_max + part_b_max + part_c_max + part_d_max
            
            faculty_part_a_max = self_max["part_a_max"]
            faculty_part_b_max = self_max["part_b_max"]
            faculty_part_c_max = 150 if has_c_d else 0
            faculty_part_d_max = 50 if has_c_d else 0
            faculty_total_max = faculty_part_a_max + faculty_part_b_max + faculty_part_c_max + faculty_part_d_max

        sub = {
            "email": faculty.email,
            "name": faculty.full_name,
            "department": faculty.department,
            "school": faculty.school,
            "appraisal_role": faculty.appraisal_role,
            "designation": faculty.designation,
            "profile_picture_url": faculty.profile_picture_url,
            "status": decl.status if decl else "pending",
            "submitted_at": decl.submitted_at.isoformat() if decl and decl.submitted_at else None,
            "part_a_total": float(decl.part_a_total) if decl and decl.part_a_total is not None else 0,
            "part_b_total": float(decl.part_b_total) if decl and decl.part_b_total is not None else 0,
            "part_c_total": float(decl.part_c_total) if decl and decl.part_c_total is not None else 0,
            "part_d_total": float(decl.part_d_total) if decl and decl.part_d_total is not None else 0,
            "grand_total": float(decl.grand_total) if decl and decl.grand_total is not None else 0,
            "hod_total": 0, "hod_part_a": 0, "hod_part_b": 0, "hod_part_c": 0, "hod_part_d": 0, "hod_remarks": "",
            "center_head_total": 0, "center_head_part_a": 0, "center_head_part_b": 0, "center_head_part_c": 0, "center_head_part_d": 0, "center_head_remarks": "",
            "director_total": 0, "director_part_a": 0, "director_part_b": 0, "director_part_c": 0, "director_part_d": 0, "director_remarks": "",
            "dean_total": 0, "dean_part_a": 0, "dean_part_b": 0, "dean_part_c": 0, "dean_part_d": 0, "dean_remarks": "",
            "vc_total": 0, "vc_part_a": 0, "vc_part_b": 0, "vc_part_c": 0, "vc_part_d": 0, "vc_remarks": "",
            "faculty_section_scores": self_form,
            "faculty_section_applicability": self_app,
            "faculty_part_a_max": faculty_part_a_max,
            "faculty_part_b_max": faculty_part_b_max,
            "faculty_part_c_max": faculty_part_c_max,
            "faculty_part_d_max": faculty_part_d_max,
            "faculty_total_max": faculty_total_max,
            "hod_part_a_max": part_a_max, "hod_part_b_max": part_b_max, "hod_part_c_max": part_c_max, "hod_part_d_max": part_d_max, "hod_total_max": total_max,
            "center_head_part_a_max": part_a_max, "center_head_part_b_max": part_b_max, "center_head_part_c_max": part_c_max, "center_head_part_d_max": part_d_max, "center_head_total_max": total_max,
            "director_part_a_max": part_a_max, "director_part_b_max": part_b_max, "director_part_c_max": part_c_max, "director_part_d_max": part_d_max, "director_total_max": total_max,
            "dean_part_a_max": part_a_max, "dean_part_b_max": part_b_max, "dean_part_c_max": part_c_max, "dean_part_d_max": part_d_max, "dean_total_max": total_max,
            "vc_part_a_max": part_a_max, "vc_part_b_max": part_b_max, "vc_part_c_max": part_c_max, "vc_part_d_max": part_d_max, "vc_total_max": total_max,
            "hod_section_scores": {},
            "hod_section_applicability": {},
            "center_head_section_scores": {},
            "center_head_section_applicability": {},
            "director_section_scores": {},
            "director_section_applicability": {},
            "dean_section_scores": {},
            "dean_section_applicability": {},
            "vc_section_scores": {},
            "vc_section_applicability": {},
        }

        for rev in reviews_by_email[faculty.email]:
            role = rev.reviewer_role
            section_scores = rev.section_scores or {}
            app = _extract_review_applicability(section_scores)
            if is_creative:
                rev_a_max, rev_b_max, rev_c_max, rev_d_max, rev_total_max = 150.0, 350.0, 150.0, 50.0, 700.0
            else:
                maxes = compute_effective_max(section_scores, app, mode="reviewer")
                rev_a_max = maxes["part_a_max"]
                rev_b_max = maxes["part_b_max"]
                rev_c_max = 150.0
                rev_d_max = 50.0
                rev_total_max = rev_a_max + rev_b_max + rev_c_max + rev_d_max

            sub[f"{role}_total"] = float(rev.total_score) if rev.total_score is not None else 0
            sub[f"{role}_part_a"] = float(rev.part_a_score) if rev.part_a_score is not None else 0
            sub[f"{role}_part_b"] = float(rev.part_b_score) if rev.part_b_score is not None else 0
            sub[f"{role}_part_c"] = float(rev.part_c_score) if rev.part_c_score is not None else 0
            sub[f"{role}_part_d"] = float(rev.part_d_score) if rev.part_d_score is not None else 0
            sub[f"{role}_remarks"] = rev.remarks or ""
            sub[f"{role}_section_scores"] = section_scores
            sub[f"{role}_section_applicability"] = app
            sub[f"{role}_part_a_max"] = rev_a_max
            sub[f"{role}_part_b_max"] = rev_b_max
            sub[f"{role}_part_c_max"] = rev_c_max
            sub[f"{role}_part_d_max"] = rev_d_max
            sub[f"{role}_total_max"] = rev_total_max

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
async def get_faculty_snapshot(request: Request, email: str, academic_year: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
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

    # Fetch declaration
    decl_res = await db.execute(select(Declaration).where(
        Declaration.faculty_email == email,
        Declaration.academic_year == academic_year
    ))
    decl = decl_res.scalar_one_or_none()
    
    from src.setup.score_utils import generate_scoring_metadata
    metadata = generate_scoring_metadata(target, snapshot, reviews, decl)

    if snapshot is None:
        return {
            "reviews": reviews_data,
            **metadata
        }

    import copy
    import os
    from src.api.v1.appraisal import _rewrite_payload_urls
    payload = copy.deepcopy(snapshot.payload)
    if request:
        app_url = str(request.base_url).rstrip("/")
    else:
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
        "profile_picture_url": target.profile_picture_url,
        **metadata
    }
