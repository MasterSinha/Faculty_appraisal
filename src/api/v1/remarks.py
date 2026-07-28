from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.setup.database import get_db
from src.setup.dependencies import CurrentUser
from src.models.core import AppraisalReview, Declaration, FacultyProfile, ReviewerSnapshot
from src.crud.core import create_or_update_review
from src.schema.core import AppraisalReviewBase
from typing import Dict, Any
from sqlalchemy import select, update, delete
from sqlalchemy.orm.attributes import flag_modified
from src.models import part_a as models_a
from src.models import part_b as models_b

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


def _is_immediate_superior(
    reviewer_role: str,
    subject_appraisal_role: str,
    current_status: str,
) -> bool:
    allowed = _ACTIVE_REVIEWER_FOR_STATUS.get(current_status)
    if allowed is not None:
        return reviewer_role in allowed
    if current_status == "Submitted":
        allowed = _FIRST_REVIEWER_FOR_ROLE.get(
            (subject_appraisal_role or "faculty").lower(), frozenset()
        )
        return reviewer_role in allowed
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
    if role != "vc" and decl and decl.status == "Reviewed":
        raise HTTPException(
            status_code=403,
            detail="This appraisal has been finalised by the VC and can no longer be modified.",
        )

    # Lock: once rejected, workflow is frozen until faculty resubmits
    if decl and decl.status in REJECTED_STATUSES and not _is_rejection_request(data):
        raise HTTPException(
            status_code=409,
            detail="This appraisal has been rejected and is awaiting resubmission by the faculty.",
        )

    is_rejection = _is_rejection_request(data)

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
        if decl.status in REJECTED_STATUSES:
            raise HTTPException(
                status_code=409,
                detail="This appraisal has already been rejected and is awaiting resubmission.",
            )
        if not _is_immediate_superior(role, target.appraisal_role or "faculty", decl.status):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Only the immediate superior may reject. "
                    f"Current workflow status is '{decl.status}'."
                ),
            )
    else:
        rejection_remarks = None

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
    reviewer_role = reviewer_role.strip().lower()

    if reviewer_role not in current_user.roles and "admin" not in current_user.roles:
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
        raise HTTPException(status_code=404, detail="Faculty not found")

    if not current_user.has_authority_over(
        email, target.appraisal_role, target.department, target.school
    ):
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
        return {"payload": None, "updated_at": None}
    return {
        "payload":    snapshot.payload,
        "updated_at": snapshot.updated_at,
    }


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
    reviewer_role = (data.get('reviewer_role') or '').strip().lower()
    academic_year = data.get('academic_year')
    payload = data.get('payload', {})

    if not reviewer_role:
        raise HTTPException(status_code=422, detail="reviewer_role is required")
    if reviewer_role not in _VALID_REVIEWER_ROLES:
        raise HTTPException(status_code=422, detail=f"Invalid reviewer_role '{reviewer_role}'")
    if not academic_year:
        raise HTTPException(status_code=422, detail="academic_year is required")

    # Reviewer must actually hold the claimed role
    if reviewer_role not in current_user.roles and "admin" not in current_user.roles:
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
        raise HTTPException(status_code=404, detail="Faculty not found")

    if not current_user.has_authority_over(
        email, target.appraisal_role, target.department, target.school
    ):
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
    return {"message": "Draft saved"}


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
