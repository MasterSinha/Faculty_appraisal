from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from urllib.parse import unquote
from sqlalchemy.ext.asyncio import AsyncSession
from src.setup.database import get_db
from src.setup.dependencies import CurrentUser, NON_ENGINEERING_SCHOOLS, normalize_school
from src.models.core import AppraisalReview, Declaration, FacultyProfile, ReviewerSnapshot, AppraisalSnapshot
from src.crud.core import create_or_update_review
from src.schema.core import AppraisalReviewBase
from typing import Dict, Any, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.orm.attributes import flag_modified
from src.models import part_a as models_a
from src.models import part_b as models_b
from src.setup.score_utils import compute_effective_max
from src.api.v1.dashboard import _extract_snapshot_form, _extract_snapshot_applicability
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/appraisal-remarks", tags=["Appraisal Remarks"])

# ── Rejection constants ──────────────────────────────────────────────────────

REJECTED_STATUSES = frozenset({
    "HOD Rejected",
    "Center Head Rejected",
    "Director Rejected",
    "Dean Rejected",
    "VC Rejected",
    "Registrar Rejected",
    "Reporting Officer Rejected",
})

_ROLE_DISPLAY = {
    "hod":                "HOD",
    "center_head":        "Center Head",
    "director":           "Director",
    "dean":               "Dean",
    "vc":                 "VC",
    "registrar":          "Registrar",
    "reporting_officer":  "Reporting Officer",
}

# All roles that are permitted to save/submit reviews
_VALID_REVIEWER_ROLES = frozenset({
    "hod", "center_head", "director", "dean", "vc",
    "registrar", "reporting_officer", "section_head",
})

_FIRST_REVIEWER_FOR_ROLE = {
    "faculty":      frozenset({"hod", "center_head"}),
    "hod":          frozenset({"director"}),
    "section_head": frozenset({"director", "center_head"}),
    "director":     frozenset({"dean"}),
    "dean":         frozenset({"vc"}),
    "center_head":  frozenset({"vc"}),
}

_ACTIVE_REVIEWER_FOR_STATUS = {
    "Pending HOD Review":          frozenset({"hod"}),
    "Pending Center Head Review":  frozenset({"center_head"}),
    "Pending Director Review":     frozenset({"director"}),
    "Pending Dean Review":         frozenset({"dean"}),
    "Pending VC Review":           frozenset({"vc"}),
    "Pending Registrar Review":    frozenset({"registrar"}),
    "Pending RO Review":           frozenset({"reporting_officer"}),
}

_STATUS_MAP = {
    "hod":         "Pending Director Review",
    "center_head": "Pending VC Review",
    "director":    "Pending Dean Review",
    "dean":        "Pending VC Review",
    "vc":          "Reviewed",
}


def _is_rejection_request(data: Dict[str, Any]) -> bool:
    """
    Returns True if the payload signals a rejection using any supported field convention.
    Accepts: decision="rejected", action="reject", review_decision="rejected",
             rejected=True, is_rejected=True.
    """
    if (data.get('decision') or '').strip().lower() == 'rejected':
        return True
    if (data.get('action') or '').strip().lower() == 'reject':
        return True
    if (data.get('review_decision') or '').strip().lower() == 'rejected':
        return True
    if data.get('rejected') is True:
        return True
    if data.get('is_rejected') is True:
        return True
    return False


def _get_rejection_remarks(data: Dict[str, Any]) -> str:
    """Returns the rejection remarks/reason from whichever field the frontend used."""
    return (data.get('remarks') or data.get('rejection_reason') or '').strip()


def normalize_status(status: str) -> str:
    if not status:
        return status
    s = status.strip().lower().replace("_", " ")
    
    # Check for rejection status first
    if "reject" in s:
        return "Rejected"
        
    # Check for finalized status
    if s in {"reviewed", "finalised", "completed", "done", "reviewed / reviewed"}:
        return "Reviewed"

    # Map possible status string forms to standard _ACTIVE_REVIEWER_FOR_STATUS keys
    if "vc" in s or "vice chancellor" in s or "vice_chancellor" in s or "dean reviewed" in s or s == "pending vc":
        return "Pending VC Review"
        
    if "dean" in s or "director reviewed" in s or s == "pending dean":
        return "Pending Dean Review"
        
    if "director" in s or "hod reviewed" in s or s == "pending director":
        return "Pending Director Review"
        
    if "hod" in s or s == "pending hod":
        return "Pending HOD Review"
        
    if "center head" in s or "center_head" in s or s == "pending center head":
        return "Pending Center Head Review"
        
    if "registrar" in s or s == "pending registrar":
        return "Pending Registrar Review"
        
    if "ro" in s or "reporting officer" in s or "reporting_officer" in s:
        return "Pending RO Review"
        
    if s in {"submitted", "pending review", "pending_review", "draft"}:
        return "Submitted"
        
    return status


def department_has_hod(school: Optional[str], department: Optional[str]) -> bool:
    if not school or not department:
        return False
    norm_school = normalize_school(school)
    if norm_school != "SoEMR":
        return False
    dept_lower = department.strip().lower()
    return any(name in dept_lower for name in ("mechanical", "civil", "chemical", "semiconductor"))


def get_review_chain(profile: FacultyProfile) -> list:
    role = (profile.appraisal_role or "faculty").strip().lower()
    
    if role == "vc":
        return []
    if role == "registrar":
        return ["vc"]
    if role == "reporting_officer":
        return ["registrar", "vc"]
    if role == "non_teaching_staff":
        reports_to_registrar = getattr(profile, "reports_to_registrar", False)
        return ["registrar", "vc"] if reports_to_registrar else ["reporting_officer", "registrar", "vc"]
    if role == "center_head":
        return ["vc"]
    if role == "dean":
        return ["vc"]
    if role == "director":
        return ["dean", "vc"]
    if role == "hod":
        return ["director", "dean", "vc"]

    school = normalize_school(profile.school)
    
    if school == "CISR":
        return ["center_head", "vc"]

    if school == "SoEMR":
        if department_has_hod(profile.school, profile.department):
            return ["hod", "director", "dean", "vc"]
        else:
            return ["director", "dean", "vc"]

    return ["director", "dean", "vc"]


def _is_immediate_superior(
    reviewer_role: str,
    target_profile: FacultyProfile,
    current_status: str,
) -> bool:
    norm_status = normalize_status(current_status)
    allowed = _ACTIVE_REVIEWER_FOR_STATUS.get(norm_status)
    if allowed is not None:
        return reviewer_role in allowed
    if norm_status == "Submitted":
        chain = get_review_chain(target_profile)
        if chain:
            return reviewer_role == chain[0]
    return False


# ── Score extraction helper ──────────────────────────────────────────────────

def _extract_numeric_score(raw: Any, role: str) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw)
        except (ValueError, TypeError):
            return 0.0
    if isinstance(raw, dict):
        val = raw.get(role) or raw.get('score') or 0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0
    if isinstance(raw, list):
        total = 0.0
        for item in raw:
            if isinstance(item, dict):
                val = item.get(role) or item.get('score') or 0
                try:
                    total += float(val)
                except (ValueError, TypeError):
                    pass
        return total
    return 0.0


async def update_item_scores(
    db: AsyncSession,
    email: str,
    year: str,
    role: str,
    section_scores: Dict[str, Any],
):
    column_map = {
        "hod":         "hod_score",
        "center_head": "director_score",
        "director":    "director_score",
        "dean":        "dean_score",
        "vc":          "vc_score",
    }
    col = column_map.get(role)
    if not col:
        return

    section_map = {
        "lectures":        models_a.TeachingProcess,
        "courseFile":      models_a.CourseFile,
        "innovDetails":    models_a.InnovativeTeaching,
        "projects":        models_a.ProjectGuided,
        "quals":           models_a.QualificationEnhancement,
        "feedback":        models_a.StudentFeedback,
        "deptActs":        models_a.DepartmentActivity,
        "uniActs":         models_a.UniversityActivity,
        "society":         models_a.SocialContribution,
        "industry":        models_a.IndustryConnect,
        "acr":             models_a.ACRScore,
        "journals":        models_b.JournalPublication,
        "books":           models_b.BookPublication,
        "ict":             models_b.ICTPedagogy,
        "research":        models_b.ResearchGuidance,
        "projects2":       models_b.ResearchProject,
        "externalProjects":models_b.ExternalResearchProject,
        "patents":         models_b.Patent,
        "awards":          models_b.Award,
        "confs":           models_b.Conference,
        "proposals":       models_b.ResearchProposal,
        "products":        models_b.ProductDeveloped,
        "fdps":            models_b.SelfDevelopment,
        "training":        models_b.IndustrialTraining,
    }

    for section_key, raw_score in section_scores.items():
        model = section_map.get(section_key)
        if model and hasattr(model, col):
            numeric_score = _extract_numeric_score(raw_score, role)
            await db.execute(
                update(model)
                .where(model.faculty_email == email, model.academic_year == year)
                .values({col: numeric_score})
            )


# ── Core review handler ──────────────────────────────────────────────────────

async def handle_review(
    role: str,
    email: str,
    data: Dict[str, Any],
    current_user: CurrentUser,
    db: AsyncSession,
):
    target_res = await db.execute(
        select(FacultyProfile).where(FacultyProfile.email == email)
    )
    target = target_res.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Faculty not found")

    if not current_user.has_authority_over(
        email, target.appraisal_role, target.department, target.school
    ):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to update remarks for this faculty",
        )

    academic_year = data.get('academic_year')
    if not academic_year:
        raise HTTPException(status_code=422, detail="academic_year is required")

    decl_res = await db.execute(
        select(Declaration).where(
            Declaration.faculty_email == email,
            Declaration.academic_year == academic_year,
        )
    )
    decl = decl_res.scalar_one_or_none()

    # Lock: once VC finalises, only VC may re-edit
    if role != "vc" and decl and normalize_status(decl.status) == "Reviewed":
        raise HTTPException(
            status_code=403,
            detail="This appraisal has been finalised by the VC and can no longer be modified.",
        )

    # Lock: once rejected, workflow is frozen until faculty resubmits
    if decl and normalize_status(decl.status) == "Rejected" and not _is_rejection_request(data):
        raise HTTPException(
            status_code=409,
            detail="This appraisal has been rejected and is awaiting resubmission by the faculty.",
        )

    is_rejection = _is_rejection_request(data)

    school_norm = normalize_school(target.school)
    is_creative = school_norm in NON_ENGINEERING_SCHOOLS

    if is_rejection:
        rejection_remarks = _get_rejection_remarks(data)
        if not rejection_remarks:
            raise HTTPException(
                status_code=422,
                detail="Remarks are mandatory when rejecting an appraisal.",
            )
        if not decl:
            raise HTTPException(
                status_code=400,
                detail="No submitted appraisal found for this faculty and year.",
            )
        if normalize_status(decl.status) == "Rejected":
            raise HTTPException(
                status_code=409,
                detail="This appraisal has already been rejected and is awaiting resubmission.",
            )
        if not _is_immediate_superior(role, target, decl.status):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Only the immediate superior may reject. "
                    f"Current workflow status is '{decl.status}'."
                ),
            )
    else:
        rejection_remarks = None

        # ── Previous Reviews Lookup and Validation ──────────────────────────
        # VC/Dean/Director review validation checks that previous steps are done
        reviews_res = await db.execute(
            select(AppraisalReview).where(
                AppraisalReview.faculty_email == email,
                AppraisalReview.academic_year == academic_year,
            )
        )
        existing_reviews = {r.reviewer_role: r for r in reviews_res.scalars().all() if r.status != 'Rejected'}

        review_chain = get_review_chain(target)
        try:
            current_index = review_chain.index(role)
        except ValueError:
            current_index = -1

        required_roles = []
        if current_index > 0:
            required_roles = [review_chain[current_index - 1]]

        for req_role in required_roles:
            req_review = existing_reviews.get(req_role)
            if not req_review:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot submit review. Previous review from {req_role.upper()} is missing.",
                )

        # ── Max Score Validation ────────────────────────────────────────────
        part_a_in = float(data.get('part_a_score') or data.get('partAScore') or 0)
        part_b_in = float(data.get('part_b_score') or data.get('partBScore') or 0)
        part_c_in = float(data.get('part_c_score') or data.get('partCScore') or 0)
        part_d_in = float(data.get('part_d_score') or data.get('partDScore') or 0)
        total_in = float(data.get('total_score') or data.get('totalScore') or 0)

        if is_creative:
            max_a, max_b, max_c, max_d, max_total = 150.0, 350.0, 150.0, 50.0, 700.0
        else:
            snap_res = await db.execute(
                select(AppraisalSnapshot).where(
                    AppraisalSnapshot.faculty_email == email,
                    AppraisalSnapshot.academic_year == academic_year,
                )
            )
            snapshot = snap_res.scalar_one_or_none()
            self_form = _extract_snapshot_form(snapshot)
            self_app = _extract_snapshot_applicability(snapshot)
            effective_max = compute_effective_max(self_form, self_app, mode="reviewer")
            
            max_a = effective_max.get("part_a_max", 200.0)
            max_b = effective_max.get("part_b_max", 375.0)
            max_c = 150.0
            max_d = 50.0
            max_total = max_a + max_b + max_c + max_d

        if part_a_in > max_a:
            raise HTTPException(status_code=400, detail=f"Part A score {part_a_in} exceeds maximum allowed {max_a}")
        if part_b_in > max_b:
            raise HTTPException(status_code=400, detail=f"Part B score {part_b_in} exceeds maximum allowed {max_b}")
        if part_c_in > max_c:
            raise HTTPException(status_code=400, detail=f"Part C score {part_c_in} exceeds maximum allowed {max_c}")
        if part_d_in > max_d:
            raise HTTPException(status_code=400, detail=f"Part D score {part_d_in} exceeds maximum allowed {max_d}")
        if total_in > max_total:
            raise HTTPException(status_code=400, detail=f"Total score {total_in} exceeds maximum allowed {max_total}")

    review_in = AppraisalReviewBase(
        faculty_email=email,
        academic_year=academic_year,
        reviewer_email=current_user.email,
        reviewer_role=role,
        part_a_score=data.get('part_a_score') or data.get('partAScore') or 0,
        part_b_score=data.get('part_b_score') or data.get('partBScore') or 0,
        part_c_score=data.get('part_c_score') or data.get('partCScore') or 0,
        part_d_score=data.get('part_d_score') or data.get('partDScore') or 0,
        total_score=data.get('total_score') or data.get('totalScore') or 0,
        remarks=rejection_remarks if is_rejection else data.get('remarks'),
        status='Rejected' if is_rejection else 'Reviewed',
    )
    db_review = await create_or_update_review(db, review_in)

    if data.get('section_scores'):
        db_review.section_scores = data['section_scores']
        flag_modified(db_review, 'section_scores')

    if 'section_scores' in data:
        await update_item_scores(db, email, academic_year, role, data['section_scores'])

    if decl:
        if is_rejection:
            decl.status = f"{_ROLE_DISPLAY.get(role, role.replace('_', ' ').title())} Rejected"
        else:
            decl.status = _STATUS_MAP.get(role, decl.status)

    # Draft is now superseded by the final review — clean it up
    await db.execute(
        delete(ReviewerSnapshot).where(
            ReviewerSnapshot.faculty_email == email,
            ReviewerSnapshot.academic_year == academic_year,
            ReviewerSnapshot.reviewer_role == role,
        )
    )

    await db.commit()

    response = {
        "message": "Appraisal rejected" if is_rejection else "Review submitted",
        "status": decl.status if decl else "unknown",
        "decision": "rejected" if is_rejection else "approved",
    }
    if is_rejection:
        response["next_reviewer"] = None
        response["next_reviewer_role"] = None
        response["next_reviewer_email"] = None
    return response


# ── Draft save / load endpoints ──────────────────────────────────────────────

@router.get("/draft/{email}")
async def get_review_draft(
    email: str,
    academic_year: str,
    reviewer_role: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Load a previously saved review draft for the given faculty member.
    Returns {"payload": null, "updated_at": null} if no draft exists yet.
    """
    import traceback
    import json

    email = unquote(email)

    logger.info("[DRAFT LOAD] route matched: /draft/{email}")
    logger.info("[DRAFT LOAD] HTTP method: GET")
    logger.info(f"[DRAFT LOAD] decoded subjectEmail: '{email}'")
    logger.info(f"[DRAFT LOAD] academic_year: '{academic_year}'")
    logger.info(f"[DRAFT LOAD] reviewer_role: '{reviewer_role}'")
    logger.info(f"[DRAFT LOAD] authenticated user email: '{current_user.email}'")
    logger.info(f"[DRAFT LOAD] authenticated user role: {current_user.roles}")

    try:
        reviewer_role = reviewer_role.strip().lower()

        if reviewer_role not in current_user.roles and "admin" not in current_user.roles:
            logger.error(f"[DRAFT LOAD] Authorization failed: user roles {current_user.roles} do not contain '{reviewer_role}'")
            raise HTTPException(
                status_code=403,
                detail=f"You do not have the '{reviewer_role}' role.",
            )

        # Must have authority over this faculty — prevents cross-department draft reads
        target_res = await db.execute(
            select(FacultyProfile).where(FacultyProfile.email == email)
        )
        target = target_res.scalar_one_or_none()
        if not target:
            logger.error(f"[DRAFT LOAD] Target faculty '{email}' not found")
            raise HTTPException(status_code=404, detail="Faculty not found")

        logger.info(f"[DRAFT LOAD] Target Faculty profile found. Appraisal Role: '{target.appraisal_role}', Department: '{target.department}', School: '{target.school}'")

        if not current_user.has_authority_over(
            email, target.appraisal_role, target.department, target.school
        ):
            logger.error(f"[DRAFT LOAD] Authority check failed: '{current_user.email}' does not have authority over target '{email}'")
            raise HTTPException(
                status_code=403,
                detail="Not authorized to read a review draft for this faculty",
            )

        res = await db.execute(
            select(ReviewerSnapshot).where(
                ReviewerSnapshot.faculty_email == email,
                ReviewerSnapshot.academic_year == academic_year,
                ReviewerSnapshot.reviewer_role == reviewer_role,
            )
        )
        snapshot = res.scalar_one_or_none()
        
        if not snapshot:
            logger.info(f"[DRAFT LOAD] No draft snapshot found in DB for '{email}'")
            logger.info("[DRAFT LOAD] DB query success: no draft found")
            return {"payload": None, "updated_at": None}
            
        payload = snapshot.payload
        logger.info(f"[DRAFT LOAD] Successfully loaded draft snapshot for '{email}'")
        logger.info(f"[DRAFT LOAD] payload keys: {list(payload.keys()) if isinstance(payload, dict) else []}")
        logger.info(f"[DRAFT LOAD] section_scores type: {type(payload.get('section_scores'))}")
        logger.info(f"[DRAFT LOAD] section_scores keys count: {len(payload.get('section_scores', {})) if isinstance(payload.get('section_scores'), dict) else 0}")
        logger.info(f"[DRAFT LOAD] payload JSON byte size: {len(json.dumps(payload))}")
        logger.info("[DRAFT LOAD] DB query success: draft found")

        return {
            "payload":    snapshot.payload,
            "updated_at": snapshot.updated_at.isoformat() if snapshot.updated_at else None,
        }
    except Exception as e:
        logger.error(f"[DRAFT LOAD] full traceback on exception:\n{traceback.format_exc()}")
        if isinstance(e, HTTPException):
            raise
        return JSONResponse(
            status_code=500,
            content={
                "user_message": "Unable to load reviewer draft.",
                "detail": str(e)
            }
        )


@router.put("/draft/{email}")
async def save_review_draft(
    email: str,
    data: Dict[str, Any],
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Save (upsert) an in-progress review without advancing the declaration status.
    The payload is stored verbatim — send whatever fields the review form contains.
    """
    import traceback
    import json
    
    email = unquote(email)

    reviewer_role = (data.get('reviewer_role') or '').strip().lower()
    academic_year = data.get('academic_year')
    payload = data.get('payload', {})

    logger.info("[DRAFT SAVE] route matched: /draft/{email}")
    logger.info("[DRAFT SAVE] HTTP method: PUT")
    logger.info(f"[DRAFT SAVE] decoded subjectEmail: '{email}'")
    logger.info(f"[DRAFT SAVE] academic_year: '{academic_year}'")
    logger.info(f"[DRAFT SAVE] reviewer_role: '{reviewer_role}'")
    logger.info(f"[DRAFT SAVE] authenticated user email: '{current_user.email}'")
    logger.info(f"[DRAFT SAVE] authenticated user role: {current_user.roles}")
    logger.info(f"[DRAFT SAVE] payload keys: {list(payload.keys()) if isinstance(payload, dict) else []}")
    logger.info(f"[DRAFT SAVE] section_scores type: {type(payload.get('section_scores'))}")
    logger.info(f"[DRAFT SAVE] section_scores keys count: {len(payload.get('section_scores', {})) if isinstance(payload.get('section_scores'), dict) else 0}")
    logger.info(f"[DRAFT SAVE] payload JSON byte size: {len(json.dumps(payload))}")

    try:
        if not reviewer_role:
            logger.error("[DRAFT SAVE] Validation failed: reviewer_role is missing")
            raise HTTPException(status_code=422, detail="reviewer_role is required")
        if reviewer_role not in _VALID_REVIEWER_ROLES:
            logger.error(f"[DRAFT SAVE] Validation failed: invalid reviewer_role '{reviewer_role}'")
            raise HTTPException(status_code=422, detail=f"Invalid reviewer_role '{reviewer_role}'")
        if not academic_year:
            logger.error("[DRAFT SAVE] Validation failed: academic_year is missing")
            raise HTTPException(status_code=422, detail="academic_year is required")

        # Reviewer must actually hold the claimed role
        if reviewer_role not in current_user.roles and "admin" not in current_user.roles:
            logger.error(f"[DRAFT SAVE] Authorization failed: user roles {current_user.roles} do not contain '{reviewer_role}'")
            raise HTTPException(
                status_code=403,
                detail=f"You do not have the '{reviewer_role}' role.",
            )

        # Must have hierarchical authority over the target faculty
        target_res = await db.execute(
            select(FacultyProfile).where(FacultyProfile.email == email)
        )
        target = target_res.scalar_one_or_none()
        if not target:
            logger.error(f"[DRAFT SAVE] Target faculty '{email}' not found")
            raise HTTPException(status_code=404, detail="Faculty not found")

        logger.info(f"[DRAFT SAVE] Target Faculty profile found. Appraisal Role: '{target.appraisal_role}', Department: '{target.department}', School: '{target.school}'")

        if not current_user.has_authority_over(
            email, target.appraisal_role, target.department, target.school
        ):
            logger.error(f"[DRAFT SAVE] Authority check failed: '{current_user.email}' does not have authority over target '{email}'")
            raise HTTPException(
                status_code=403,
                detail="Not authorized to save a review draft for this faculty",
            )

        # Upsert draft
        res = await db.execute(
            select(ReviewerSnapshot).where(
                ReviewerSnapshot.faculty_email == email,
                ReviewerSnapshot.academic_year == academic_year,
                ReviewerSnapshot.reviewer_role == reviewer_role,
            )
        )
        snapshot = res.scalar_one_or_none()
        
        db_op = "UPDATE" if snapshot else "INSERT"
        logger.info(f"[DRAFT SAVE] DB Operation: {db_op}")

        if snapshot:
            snapshot.payload = payload
            snapshot.reviewer_email = current_user.email
            flag_modified(snapshot, 'payload')
        else:
            snapshot = ReviewerSnapshot(
                faculty_email=email,
                academic_year=academic_year,
                reviewer_email=current_user.email,
                reviewer_role=reviewer_role,
                payload=payload,
            )
            db.add(snapshot)

        await db.commit()
        await db.refresh(snapshot)
        logger.info(f"[DRAFT SAVE] DB upsert success: Transaction committed successfully for '{email}'")
        
        return {
            "message": "Draft saved",
            "payload": snapshot.payload,
            "updated_at": snapshot.updated_at.isoformat() if snapshot.updated_at else None
        }
    except Exception as e:
        logger.error(f"[DRAFT SAVE] DB upsert failure for '{email}': {str(e)}")
        logger.error(f"[DRAFT SAVE] full traceback on exception:\n{traceback.format_exc()}")
        if isinstance(e, HTTPException):
            raise
        return JSONResponse(
            status_code=500,
            content={
                "user_message": "Unable to save reviewer draft.",
                "detail": str(e)
            }
        )


# ── Final review route handlers ───────────────────────────────────────────────

@router.put("/hod/{email}")
async def review_hod(
    email: str,
    data: Dict[str, Any],
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if "hod" not in current_user.roles and "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="HOD role required")
    return await handle_review("hod", email, data, current_user, db)


@router.put("/center-head/{email}")
async def review_center_head(
    email: str,
    data: Dict[str, Any],
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if "center_head" not in current_user.roles and "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Center Head role required")
    return await handle_review("center_head", email, data, current_user, db)


@router.put("/director/{email}")
async def review_director(
    email: str,
    data: Dict[str, Any],
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if "director" not in current_user.roles and "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Director role required")
    return await handle_review("director", email, data, current_user, db)


@router.put("/dean/{email}")
async def review_dean(
    email: str,
    data: Dict[str, Any],
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if "dean" not in current_user.roles and "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Dean role required")
    return await handle_review("dean", email, data, current_user, db)


@router.put("/final/{email}")
async def review_final(
    email: str,
    data: Dict[str, Any],
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if "vc" not in current_user.roles and "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="VC role required")
    return await handle_review("vc", email, data, current_user, db)
