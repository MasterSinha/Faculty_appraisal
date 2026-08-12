from fastapi import APIRouter, Depends, HTTPException, Query, Request
from src.setup.errors import AppError
from sqlalchemy.ext.asyncio import AsyncSession
from src.setup.database import get_db
from src.setup.dependencies import CurrentUser
from src.models.core import AppraisalSnapshot, Declaration, AppraisalDocument, AppraisalReview, FormSectionDefinition, AppraisalConfig, ReviewerSnapshot
from src.crud.core import create_or_update_declaration
from src.models import part_a as models_a
from src.models import part_b as models_b
from sqlalchemy import select, delete, inspect as sa_inspect, Numeric as SANumeric, Integer as SAInteger, String as SAString, Date as SADate
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime, date as date_type
from typing import Optional, List, Dict, Any
import logging
import traceback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/appraisal", tags=["Appraisal Form"])

def normalize_details_value(val: Any) -> str:
    if val is None:
        return None
    if isinstance(val, str) and val.strip() == "":
        return None
    
    val_str = str(val).strip()
    val_lower = val_str.lower()
    
    if val_lower in ("yes", "available", "1.available"):
        return "1.Available"
    elif val_lower in ("partial", "partially available", "2.partially available"):
        return "2.Partially Available"
    elif val_lower in ("no", "not available", "3.not available"):
        return "3.Not Available"
    else:
        raise AppError(
            user_message=f"Invalid value for course file details: '{val_str}'",
            detail=f"Validation failed: details value '{val_str}' is unsupported.",
            status_code=400
        )

def normalize_course_files_in_form(form: Any):
    if not isinstance(form, dict):
        return
    course_file_rows = form.get("courseFile")
    if isinstance(course_file_rows, list):
        for row in course_file_rows:
            if isinstance(row, dict) and "details" in row:
                row["details"] = normalize_details_value(row["details"])

def normalize_appraisal_payload(data: Any):
    if not isinstance(data, dict):
        return
    if "form" in data:
        normalize_course_files_in_form(data["form"])
    if "payload" in data and isinstance(data["payload"], dict):
        payload = data["payload"]
        if "form" in payload:
            normalize_course_files_in_form(payload["form"])

def _coerce_for_column(model_instance, field_name, value):
    """Coerce value to match the actual DB column type."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == '':
        return None

    try:
        col = sa_inspect(type(model_instance)).columns.get(field_name)
        if col is not None:
            col_type = col.type
            if isinstance(col_type, SAInteger):
                try:
                    # Handle case where value might be a float string like "5.0"
                    return int(float(value))
                except (ValueError, TypeError):
                    return None
            elif isinstance(col_type, SANumeric):
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None
            elif isinstance(col_type, SADate):
                if isinstance(value, date_type):
                    return value
                if isinstance(value, str):
                    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                        try:
                            return datetime.strptime(value, fmt).date()
                        except ValueError:
                            continue
                return None  # unparseable date — skip rather than crash asyncpg
            else:
                # VARCHAR / Text / String — always convert to str
                if isinstance(value, (int, float)):
                    return str(value)
    except Exception:
        pass

    return value

def _safe_num(value, default=0):
    """Coerce a value to float for totals, falling back to default."""
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def _rewrite_payload_urls(payload: Any, app_url: str):
    """Recursively search for and rewrite relative URLs starting with / in a payload."""
    if isinstance(payload, dict):
        for k, v in list(payload.items()):
            if k == "url" and isinstance(v, str) and v.startswith("/"):
                payload[k] = f"{app_url}{v}"
            else:
                _rewrite_payload_urls(v, app_url)
    elif isinstance(payload, list):
        for item in payload:
            _rewrite_payload_urls(item, app_url)

@router.get("/snapshot")
async def get_snapshot(request: Request, academic_year: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppraisalSnapshot).where(
        AppraisalSnapshot.faculty_email == current_user.email,
        AppraisalSnapshot.academic_year == academic_year
    ))
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        return None
    
    # Fetch reviews
    rev_res = await db.execute(select(AppraisalReview).where(
        AppraisalReview.faculty_email == current_user.email,
        AppraisalReview.academic_year == academic_year
    ))
    reviews = rev_res.scalars().all()
    
    # Fetch declaration
    decl_res = await db.execute(select(Declaration).where(
        Declaration.faculty_email == current_user.email,
        Declaration.academic_year == academic_year
    ))
    decl = decl_res.scalar_one_or_none()
    
    # Fetch profile
    from src.models.core import FacultyProfile
    profile_res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == current_user.email))
    faculty = profile_res.scalar_one_or_none()
    
    from src.setup.score_utils import generate_scoring_metadata
    metadata = generate_scoring_metadata(faculty, snapshot, reviews, decl)
    
    import copy
    import os
    payload = copy.deepcopy(snapshot.payload)
    if request:
        app_url = str(request.base_url).rstrip("/")
    else:
        app_url = os.getenv("APP_URL", "").rstrip("/")
    _rewrite_payload_urls(payload, app_url)
    
    return {
        "id": snapshot.id,
        "faculty_email": snapshot.faculty_email,
        "academic_year": snapshot.academic_year,
        "payload": payload,
        "created_at": snapshot.created_at,
        "updated_at": snapshot.updated_at,
        **metadata
    }

@router.get("/previous-year-report")
async def get_previous_year_report(
    request: Request,
    academic_year: str,
    current_user: CurrentUser,
    email: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    target_email = email.strip() if email else current_user.email
    
    # 1. Fetch faculty profile
    from src.models.core import FacultyProfile
    profile_res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == target_email))
    faculty = profile_res.scalar_one_or_none()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty profile not found")
        
    # 2. Authorization check
    if target_email != current_user.email:
        if not current_user.has_authority_over(target_email, faculty.appraisal_role, faculty.department, faculty.school):
            raise HTTPException(status_code=403, detail="Not authorized to view this faculty's previous year report")
            
    # 3. Fetch snapshot
    snap_res = await db.execute(select(AppraisalSnapshot).where(
        AppraisalSnapshot.faculty_email == target_email,
        AppraisalSnapshot.academic_year == academic_year
    ))
    snapshot = snap_res.scalar_one_or_none()
    
    # 4. Fetch reviews
    rev_res = await db.execute(select(AppraisalReview).where(
        AppraisalReview.faculty_email == target_email,
        AppraisalReview.academic_year == academic_year
    ))
    reviews = rev_res.scalars().all()
    
    # 5. Fetch declaration
    decl_res = await db.execute(select(Declaration).where(
        Declaration.faculty_email == target_email,
        Declaration.academic_year == academic_year
    ))
    decl = decl_res.scalar_one_or_none()
    
    reviews_data = [
        {
            "reviewer_role": r.reviewer_role,
            "reviewer_email": r.reviewer_email,
            "part_a_score": float(r.part_a_score) if r.part_a_score is not None else 0.0,
            "part_b_score": float(r.part_b_score) if r.part_b_score is not None else 0.0,
            "total_score": float(r.total_score) if r.total_score is not None else 0.0,
            "section_scores": r.section_scores or {},
            "remarks": r.remarks,
            "status": r.status,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        }
        for r in reviews
    ]
    
    from src.setup.score_utils import generate_scoring_metadata
    metadata = generate_scoring_metadata(faculty, snapshot, reviews, decl)
    
    if snapshot is None:
        return {
            "reviews": reviews_data,
            **metadata
        }
        
    import copy
    import os
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
        "profile_picture_url": faculty.profile_picture_url,
        **metadata
    }

@router.put("/snapshot")
async def upsert_snapshot(data: Dict[str, Any], current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    normalize_appraisal_payload(data)
    academic_year = data.get('academic_year')
    payload = data.get('payload')
    docs = data.get('docs', {})

    if not academic_year:
        raise HTTPException(status_code=422, detail="academic_year is required")

    decl_res = await db.execute(select(Declaration).where(
        Declaration.faculty_email == current_user.email,
        Declaration.academic_year == academic_year
    ))
    existing_decl = decl_res.scalar_one_or_none()
    from src.api.v1.remarks import REJECTED_STATUSES
    if existing_decl is not None and existing_decl.status not in REJECTED_STATUSES:
        raise HTTPException(
            status_code=403,
            detail="Your appraisal has already been submitted and cannot be modified.",
        )

    try:
        result = await db.execute(select(AppraisalSnapshot).where(
            AppraisalSnapshot.faculty_email == current_user.email,
            AppraisalSnapshot.academic_year == academic_year
        ))
        db_snapshot = result.scalar_one_or_none()

        if db_snapshot:
            db_snapshot.payload = payload
            flag_modified(db_snapshot, "payload")
        else:
            db_snapshot = AppraisalSnapshot(
                faculty_email=current_user.email,
                academic_year=academic_year,
                payload=payload
            )
            db.add(db_snapshot)

        if docs and isinstance(docs, dict):
            await db.execute(
                delete(AppraisalDocument).where(
                    AppraisalDocument.faculty_email == current_user.email,
                    AppraisalDocument.academic_year == academic_year
                ),
                execution_options={"synchronize_session": False}
            )
            for doc_key, file_list in docs.items():
                if not isinstance(file_list, list):
                    continue
                section = doc_key.rstrip('0123456789') or doc_key
                for row_no, file_obj in enumerate(file_list, 1):
                    if not isinstance(file_obj, dict) or not file_obj.get('name'):
                        continue
                    db.add(AppraisalDocument(
                        faculty_email=current_user.email,
                        academic_year=academic_year,
                        section=section,
                        doc_key=doc_key,
                        row_no=row_no,
                        file_name=file_obj.get('name', ''),
                        file_type=file_obj.get('type'),
                        file_url=file_obj.get('url'),
                        storage_path=file_obj.get('publicId')
                    ))

        await db.commit()
        return {"message": "Saved"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error saving snapshot for {current_user.email}: {str(e)}")
        logger.error(traceback.format_exc())
        raise AppError(
            "Your draft could not be saved. Please try again.",
            detail=f"Snapshot upsert failed: {type(e).__name__}: {e}",
            status_code=500,
        )

async def shred_form(db: AsyncSession, email: str, year: str, form_data: Dict[str, Any], form_family: str):
    """
    Takes the JSON form data and populates normalized tables.
    """
    # Mapping of frontend form keys to (Model, Section Title)
    mappings = {
        "lectures": (models_a.TeachingProcess, "A1. Lectures / Tutorials / Practicals"),
        "courseFile": (models_a.CourseFile, "A2. Course File"),
        "projects": (models_a.ProjectGuided, "A4. Projects"),
        "quals": (models_a.QualificationEnhancement, "A5. Qualification Enhancement"),
        "feedback": (models_a.StudentFeedback, "Student Feedback"),
        "deptActs": (models_a.DepartmentActivity, "Departmental / School Activities"),
        "uniActs": (models_a.UniversityActivity, "University Level Activities"),
        "society": (models_a.SocialContribution, "Contribution to Society"),
        "industry": (models_a.IndustryConnect, "Industry Connect"),
        "acr": (models_a.ACRScore, "Annual Confidential Report - School Level"),
        "events": (models_a.EventOrganization, "C3. Event Organisation & Institutional Visibility"),
        "eventRows": (models_a.EventOrganization, "C3. Event Organisation & Institutional Visibility"),
        "alumni": (models_a.AlumniEngagement, "C6. Alumni Engagement & Networking"),
        "alumniRows": (models_a.AlumniEngagement, "C6. Alumni Engagement & Networking"),
        "placements": (models_a.PlacementMentoring, "C7. Student Placement Mentoring & Career Development"),
        "placementRows": (models_a.PlacementMentoring, "C7. Student Placement Mentoring & Career Development"),
        "journals": (models_b.JournalPublication, "B1. Research Papers / Journal Publications"),
        "books": (models_b.BookPublication, "B2. Books / Book Chapters"),
        "ict": (models_b.ICTPedagogy, "B3. ICT / E-Content / Pedagogy"),
        "research": (models_b.ResearchGuidance, "B4(a). Research Guidance - PhD / PG"),
        "projects2": (models_b.ResearchProject, "B4(b). Research / Consultancy Internal Projects"),
        "externalProjects": (models_b.ExternalResearchProject, "B4(c). Research / Consultancy External Projects"),
        "patents": (models_b.Patent, "B5(a). Patents (IPR)"),
        "awards": (models_b.Award, "B5(b). Awards"),
        "confs": (models_b.Conference, "B6. Invited Lectures / Resource Person / Paper Presentations"),
        "proposals": (models_b.ResearchProposal, "B7(a). Submitted Research Proposals"),
        "products": (models_b.ProductDeveloped, "B7(b). Product Developed and Used by Students"),
        "fdps": (models_b.SelfDevelopment, "B8(a). FDP / Workshops"),
        "training": (models_b.IndustrialTraining, "B8(b). Industrial Training"),
    }

    # Field Aliases Mapping (Frontend -> Backend)
    field_aliases = {
        "title_with_page_nos": "title",
        "journal_details": "journal",
        "issn_isbn_no": "issn",
        "issn_isbn": "issn",
        "course_code_name": "course_code",
        "course_paper": "course",
        "nature_of_activity": "nature",
        "activity_type": "activity",
        "activityType": "type",
        "details_of_activity": "details",
        "project_type": "label",
        "qualification_type": "label",
        "short_description": "details",
        "title_and_pages": "title",
        "book_title_editor": "book",
        "event_title": "title",
        "hosting_organization": "organization",
        "event_level": "level",
        "pedagogy_type": "type",
        "company_industry": "company",
        "duration_days": "duration",
        "nature_of_training": "nature",
        "hod": "hod_score",
        "director": "director_score",
        "dean": "dean_score",
        "vc": "vc_score",
        "maxMarks": "max_marks"
    }

    # 1. Handle InnovativeTeaching separately (Scalar text field)
    await db.execute(delete(models_a.InnovativeTeaching).where(
        models_a.InnovativeTeaching.faculty_email == email,
        models_a.InnovativeTeaching.academic_year == year
    ), execution_options={"synchronize_session": False})
    innov_details = form_data.get("innovDetails")
    innov_score_raw = form_data.get('innovScore')
    
    if innov_details or innov_score_raw:
        innov = models_a.InnovativeTeaching(
            faculty_email=email,
            academic_year=year,
            form_family=form_family,
            section_title="A3. Innovative Teaching-Learning",
            details=str(innov_details) if not isinstance(innov_details, dict) else innov_details.get("details")
        )
        if innov_score_raw is not None:
            innov.score = _coerce_for_column(innov, 'score', innov_score_raw)
        db.add(innov)

    # 2. Handle all other sections (List of objects)
    total_added = 0
    for key, (model, title) in mappings.items():
        # Clean existing records for this user/year/section to avoid duplicates on re-submit
        await db.execute(delete(model).where(
            model.faculty_email == email,
            model.academic_year == year
        ), execution_options={"synchronize_session": False})

        section_data = form_data.get(key)
        if not section_data and section_data != 0:
            logger.warning(f"shred_form: skipping section '{key}' — no data in submitted form")
            continue

        # Handle both list and object inputs (some sections are single objects)
        items = section_data if isinstance(section_data, list) else [section_data]

        section_count = 0
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue

            # Build constructor kwargs safely
            kwargs = {
                "faculty_email": email,
                "academic_year": year,
                "form_family": form_family,
                "section_title": title
            }
            if hasattr(model, "row_no"):
                kwargs["row_no"] = idx + 1

            db_item = model(**kwargs)

            # Map specific fields from JSON to Model columns
            for field_name, value in item.items():
                target_field = field_aliases.get(field_name, field_name)
                if not hasattr(db_item, target_field):
                    logger.warning(
                        f"shred_form: field '{field_name}'→'{target_field}' not found in "
                        f"{type(db_item).__name__}, skipping"
                    )
                    continue
                if isinstance(db_item, models_a.CourseFile) and target_field == "details":
                    value = normalize_details_value(value)
                coerced = _coerce_for_column(db_item, target_field, value)
                if coerced is not None:
                    setattr(db_item, target_field, coerced)

            db.add(db_item)
            section_count += 1

        total_added += section_count
        logger.info(f"shred_form: section '{key}' → {section_count} row(s) queued")

    if total_added == 0:
        non_empty_keys = [k for k in mappings.keys() if form_data.get(k)]
        logger.warning(
            f"shred_form: 0 rows queued for {email}/{year}. "
            f"Non-empty keys in payload: {non_empty_keys}"
        )
    else:
        logger.info(f"shred_form: {total_added} total rows queued for {email}/{year}")

@router.post("/submit")
async def submit_appraisal(data: Dict[str, Any], current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    normalize_appraisal_payload(data)
    academic_year = data.get('academic_year')
    
    # Robustness: Check both 'form' and 'payload.form'
    form = data.get('form')
    totals = data.get('totals')
    
    if not form and "payload" in data and isinstance(data["payload"], dict):
        form = data["payload"].get("form")
    if not totals and "payload" in data and isinstance(data["payload"], dict):
        totals = data["payload"].get("totals")

    if form is None:
        raise HTTPException(status_code=400, detail="Form data is missing. Ensure 'form' or 'payload.form' key is present.")

    if not academic_year:
        raise HTTPException(status_code=422, detail="academic_year is required")

    # Cycle gate: if a config exists for this year and is_open=False, block submission.
    # No config row = unrestricted (backwards compatible with years before this feature existed).
    config_res = await db.execute(
        select(AppraisalConfig).where(AppraisalConfig.academic_year == academic_year)
    )
    cycle_config = config_res.scalar_one_or_none()
    if cycle_config is not None and not cycle_config.is_open:
        raise HTTPException(
            status_code=403,
            detail=f"Appraisal submissions for {academic_year} are currently closed.",
        )

    totals = totals or {}

    try:
        from src.setup.dependencies import get_form_family
        from src.api.v1.remarks import REJECTED_STATUSES
        from src.schema.core import DeclarationBase

        form_family = get_form_family(current_user.school) if current_user.school else "standard"

        # Check submission eligibility (also catches resubmission after rejection)
        sub_check = await db.execute(select(Declaration).where(
            Declaration.faculty_email == current_user.email,
            Declaration.academic_year == academic_year,
        ))
        existing_decl = sub_check.scalar_one_or_none()
        is_resubmission = existing_decl is not None and existing_decl.status in REJECTED_STATUSES

        if existing_decl is not None and not is_resubmission:
            raise HTTPException(
                status_code=403,
                detail="Your appraisal is currently under review and cannot be resubmitted.",
            )

        # 1. Shred JSON into normalized tables
        await shred_form(db, current_user.email, academic_year, form, form_family)
        await db.flush()  # surface any DB constraint violations before proceeding

        # 2. Update/Create Declaration
        # Use status from payload if provided (frontend computes review chain); default to 'Submitted'
        initial_status = data.get('status') or data.get('workflow_status') or 'Submitted'

        if is_resubmission:
            # Increment attempt counter, reset workflow state, update totals
            existing_decl.part_a_total = _safe_num(totals.get('partATotal'))
            existing_decl.part_b_total = _safe_num(totals.get('partBTotal'))
            existing_decl.part_c_total = _safe_num(totals.get('partCTotal'))
            existing_decl.part_d_total = _safe_num(totals.get('partDTotal'))
            existing_decl.grand_total  = _safe_num(totals.get('grandTotal'))
            existing_decl.status            = initial_status
            existing_decl.submission_attempt = existing_decl.submission_attempt + 1
            existing_decl.submitted_at      = datetime.utcnow()
            # Reviewer drafts are now stale — clear them so reviewers start fresh
            await db.execute(
                delete(ReviewerSnapshot).where(
                    ReviewerSnapshot.faculty_email == current_user.email,
                    ReviewerSnapshot.academic_year == academic_year,
                )
            )
        else:
            decl_data = DeclarationBase(
                faculty_email=current_user.email,
                academic_year=academic_year,
                part_a_total=_safe_num(totals.get('partATotal')),
                part_b_total=_safe_num(totals.get('partBTotal')),
                part_c_total=_safe_num(totals.get('partCTotal')),
                part_d_total=_safe_num(totals.get('partDTotal')),
                grand_total=_safe_num(totals.get('grandTotal')),
                status=initial_status,
            )
            await create_or_update_declaration(db, decl_data)

        # 3. Save uploaded documents from docs map
        docs = data.get('docs', {})
        if docs and isinstance(docs, dict):
            await db.execute(
                delete(AppraisalDocument).where(
                    AppraisalDocument.faculty_email == current_user.email,
                    AppraisalDocument.academic_year == academic_year
                ),
                execution_options={"synchronize_session": False}
            )
            for doc_key, file_list in docs.items():
                if not isinstance(file_list, list):
                    continue
                section = doc_key.rstrip('0123456789') or doc_key
                for row_no, file_obj in enumerate(file_list, 1):
                    if not isinstance(file_obj, dict) or not file_obj.get('name'):
                        continue
                    db.add(AppraisalDocument(
                        faculty_email=current_user.email,
                        academic_year=academic_year,
                        section=section,
                        doc_key=doc_key,
                        row_no=row_no,
                        file_name=file_obj.get('name', ''),
                        file_type=file_obj.get('type'),
                        file_url=file_obj.get('url'),
                        storage_path=file_obj.get('publicId')
                    ))

        # 4. Update Snapshot (Draft -> Latest)
        result = await db.execute(select(AppraisalSnapshot).where(
            AppraisalSnapshot.faculty_email == current_user.email,
            AppraisalSnapshot.academic_year == academic_year
        ))
        db_snapshot = result.scalar_one_or_none()
        if db_snapshot:
            db_snapshot.payload = data
            flag_modified(db_snapshot, "payload")
        else:
            db.add(AppraisalSnapshot(
                faculty_email=current_user.email,
                academic_year=academic_year,
                payload=data
            ))

        await db.commit()
        return {"message": "Submitted successfully", "submitted_at": datetime.utcnow().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error during appraisal submission for {current_user.email}: {str(e)}")
        logger.error(traceback.format_exc())
        raise AppError(
            "Your appraisal could not be submitted. Please try again.",
            detail=f"Submission failed: {type(e).__name__}: {e}",
            status_code=500,
        )

@router.get("/status")
async def get_appraisal_status(academic_year: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    decl_res = await db.execute(select(Declaration).where(
        Declaration.faculty_email == current_user.email,
        Declaration.academic_year == academic_year
    ))
    declaration = decl_res.scalar_one_or_none()

    rev_res = await db.execute(select(AppraisalReview).where(
        AppraisalReview.faculty_email == current_user.email,
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

    from src.models.core import FacultyProfile
    user_res = await db.execute(select(FacultyProfile).where(FacultyProfile.email == current_user.email))
    user_profile = user_res.scalar_one_or_none()
    profile_pic = user_profile.profile_picture_url if user_profile else None

    return {
        "declaration": declaration,
        "reviews": reviews_data,
        "profile_picture_url": profile_pic
    }


@router.get("/cycles")
async def get_available_cycles(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import distinct
    
    # Retrieve all configurations
    result = await db.execute(
        select(AppraisalConfig).order_by(AppraisalConfig.academic_year.desc())
    )
    configs = result.scalars().all()
    
    # Also collect years that the user has snapshots or declarations in, just in case
    decl_res = await db.execute(
        select(distinct(Declaration.academic_year)).where(Declaration.faculty_email == current_user.email)
    )
    snap_res = await db.execute(
        select(distinct(AppraisalSnapshot.academic_year)).where(AppraisalSnapshot.faculty_email == current_user.email)
    )
    
    user_years = set([r[0] for r in decl_res.all()] + [r[0] for r in snap_res.all()])
    
    cycles = []
    for c in configs:
        cycles.append({
            "academic_year": c.academic_year,
            "is_open": c.is_open,
            "submission_start": c.submission_start.isoformat() if c.submission_start else None,
            "submission_end": c.submission_end.isoformat() if c.submission_end else None,
        })
        user_years.discard(c.academic_year)
        
    # Add any other years the user had data for but are not in the main configs
    for y in sorted(user_years, reverse=True):
        if y:
            cycles.append({
                "academic_year": y,
                "is_open": False,
                "submission_start": None,
                "submission_end": None,
            })
        
    return cycles
