"""
Standard Appraisal Compatibility Module

Provides backward-compatible field/section aliasing, safe single-model shredding,
nested custom_fields sanitization/flattening, and read-side compatibility for
Standard Appraisal form submissions.

Strict Scope: Standard Appraisal only. Dynamic, Creative, Media, Design, and Non-teaching
forms are explicitly excluded and handled by their respective systems.
"""

from typing import Dict, Any, List, Optional, Tuple, Type
from datetime import datetime, date as date_type
import logging
from sqlalchemy import delete, inspect as sa_inspect, Numeric as SANumeric, Integer as SAInteger, Date as SADate
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import part_a as models_a
from src.models import part_b as models_b
from src.setup.errors import AppError

logger = logging.getLogger(__name__)

# Standard Form Family Identifiers
STANDARD_FORM_FAMILY = "standard"
STANDARD_SCHOOLS = frozenset({"SoCSEA", "SoBB", "SoCE", "SoEMR", "SoCM", "CISR"})
NON_STANDARD_FORM_FAMILIES = frozenset({"media", "design", "creative", "non_teaching", "non-teaching", "custom"})
NON_STANDARD_SCHOOLS = frozenset({"SoMCS", "SoHSS", "SoD", "SoAA"})


def is_standard_form_submission(
    form_family: Optional[str] = None,
    school: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Deterministically checks whether a submission or snapshot is a Standard Appraisal form.
    Does NOT guess Standard merely from missing keys or the reviewer's school.
    """
    from src.setup.dependencies import get_form_family, normalize_school

    if form_family is not None and str(form_family).strip():
        fam = str(form_family).strip().lower()
        if fam == STANDARD_FORM_FAMILY:
            return True
        if fam in NON_STANDARD_FORM_FAMILIES:
            return False
        norm_fam_school = normalize_school(form_family)
        if norm_fam_school in NON_STANDARD_SCHOOLS:
            return False
        if norm_fam_school in STANDARD_SCHOOLS:
            return True
        if get_form_family(form_family).lower() == STANDARD_FORM_FAMILY:
            return True

    if school is not None and str(school).strip():
        norm_school = normalize_school(school)
        if norm_school in NON_STANDARD_SCHOOLS:
            return False
        if norm_school in STANDARD_SCHOOLS:
            return True
        fam = get_form_family(school).lower()
        if fam in NON_STANDARD_FORM_FAMILIES:
            return False
        if fam == STANDARD_FORM_FAMILY:
            return True

    if payload and isinstance(payload, dict):
        if "form_family" in payload and payload["form_family"]:
            fam = str(payload["form_family"]).strip().lower()
            if fam == STANDARD_FORM_FAMILY:
                return True
            if fam in NON_STANDARD_FORM_FAMILIES:
                return False
            norm_fam = normalize_school(payload["form_family"])
            if norm_fam in NON_STANDARD_SCHOOLS:
                return False
            if norm_fam in STANDARD_SCHOOLS:
                return True
            if get_form_family(payload["form_family"]).lower() == STANDARD_FORM_FAMILY:
                return True
        form = payload.get("form")
        if isinstance(form, dict) and form.get("form_family"):
            fam = str(form["form_family"]).strip().lower()
            if fam == STANDARD_FORM_FAMILY:
                return True
            if fam in NON_STANDARD_FORM_FAMILIES:
                return False
            norm_fam = normalize_school(form["form_family"])
            if norm_fam in NON_STANDARD_SCHOOLS:
                return False
            if norm_fam in STANDARD_SCHOOLS:
                return True
            if get_form_family(form["form_family"]).lower() == STANDARD_FORM_FAMILY:
                return True
        if payload.get("school"):
            norm_s = normalize_school(payload["school"])
            if norm_s in NON_STANDARD_SCHOOLS:
                return False
            if norm_s in STANDARD_SCHOOLS:
                return True
            fam = get_form_family(payload["school"]).lower()
            if fam in NON_STANDARD_FORM_FAMILIES:
                return False
            if fam == STANDARD_FORM_FAMILY:
                return True

    return False


def normalize_details_value(val: Any) -> Optional[str]:
    """
    Normalizes Course File 'details' values into standard enum strings.
    """
    if val is None:
        return None
    if isinstance(val, str) and val.strip() == "":
        return None

    val_str = str(val).strip()
    val_lower = val_str.lower()

    if val_lower in ("yes", "available", "1.available", "1. available"):
        return "1.Available"
    elif val_lower in ("partial", "partially available", "2.partially available", "2. partially available"):
        return "2.Partially Available"
    elif val_lower in ("no", "not available", "3.not available", "3. not available"):
        return "3.Not Available"
    else:
        raise AppError(
            user_message=f"Invalid value for course file details: '{val_str}'",
            detail=f"Validation failed: details value '{val_str}' is unsupported.",
            status_code=400,
        )


def _coerce_for_column(model_instance, field_name: str, value: Any) -> Any:
    """
    Coerce a value to match the actual DB column type while preserving 0, False, and valid empty values.
    """
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None

    try:
        col = sa_inspect(type(model_instance)).columns.get(field_name)
        if col is not None:
            col_type = col.type
            if isinstance(col_type, SAInteger):
                try:
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
                    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
                        try:
                            return datetime.strptime(value.strip(), fmt).date()
                        except ValueError:
                            continue
                return None
            else:
                if isinstance(value, (int, float)):
                    return str(value)
    except Exception:
        pass

    return value


def _flatten_custom_fields(cf: Any) -> Dict[str, Any]:
    """
    Recursively unwraps and flattens any nested 'custom_fields' dictionaries.
    """
    result: Dict[str, Any] = {}
    if not isinstance(cf, dict):
        return result

    for k, v in cf.items():
        if k == "custom_fields" and isinstance(v, dict):
            inner = _flatten_custom_fields(v)
            result.update(inner)
        else:
            result[k] = v
    return result


# Security-sensitive reviewer/system keys that MUST NEVER be trusted or set from client custom_fields
DISALLOWED_CUSTOM_KEYS = frozenset({
    "id", "faculty_email", "academic_year", "form_family", "section_title", "row_no",
    "score", "self_score", "selfScore", "self_marks", "selfMarks",
    "hod_score", "hodScore", "hod_marks", "hodMarks", "center_head_score", "centerHeadScore",
    "director_score", "directorScore", "dir_score", "dirScore",
    "dean_score", "deanScore", "dean_marks", "deanMarks",
    "vc_score", "vcScore", "vc_marks", "vcMarks",
    "status", "workflow_status", "review_chain", "next_reviewer", "next_reviewer_role",
    "part_a_score", "part_b_score", "part_c_score", "part_d_score", "total_score",
    "part_a_total", "part_b_total", "part_c_total", "part_d_total", "grand_total",
    "created_at", "updated_at", "submission_attempt", "submitted_at"
})


class StandardSectionContract:
    """
    Specification for a single Standard appraisal section.
    """
    def __init__(
        self,
        canonical_key: str,
        aliases: Tuple[str, ...],
        model: Type[Any],
        section_title: str,
        column_aliases: Dict[str, Tuple[str, ...]],
        allowed_display_fields: Tuple[str, ...] = (),
        is_scalar: bool = False,
    ):
        self.canonical_key = canonical_key
        self.aliases = aliases
        self.all_keys = (canonical_key,) + tuple(a for a in aliases if a != canonical_key)
        self.model = model
        self.section_title = section_title
        self.column_aliases = column_aliases
        self.allowed_display_fields = allowed_display_fields
        self.is_scalar = is_scalar


# Standard Section Specifications Registry
STANDARD_SECTIONS: List[StandardSectionContract] = [
    # --- PART A ---
    StandardSectionContract(
        canonical_key="lectures",
        aliases=("lectures", "lectures_v2"),
        model=models_a.TeachingProcess,
        section_title="A1. Lectures / Tutorials / Practicals",
        column_aliases={
            "semester": ("semester",),
            "course_code": ("course_code", "courseCode", "course_code_name", "courseCodeName"),
            "planned_classes": ("planned_classes", "plannedClasses", "planned"),
            "conducted_classes": ("conducted_classes", "conductedClasses", "conducted"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="courseFile",
        aliases=("courseFile", "course_files"),
        model=models_a.CourseFile,
        section_title="A2. Course File",
        column_aliases={
            "course": ("course", "course_code", "courseCode", "course_paper"),
            "title": ("title", "course_title", "courseTitle"),
            "details": ("details",),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="innovDetails",
        aliases=("innovDetails", "innovativeTeaching"),
        model=models_a.InnovativeTeaching,
        section_title="A3. Innovative Teaching-Learning",
        column_aliases={
            "details": ("details", "innovDetails", "innovativeTeaching"),
            "score": ("score", "innovScore", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
        is_scalar=True,
    ),
    StandardSectionContract(
        canonical_key="projects",
        aliases=("projects", "projectsGuided"),
        model=models_a.ProjectGuided,
        section_title="A4. Projects",
        column_aliases={
            "label": ("label", "project_type", "projectType", "projectCategory", "category", "attribute"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="quals",
        aliases=("quals", "qualificationEnhancement"),
        model=models_a.QualificationEnhancement,
        section_title="A5. Qualification Enhancement",
        column_aliases={
            "label": ("label", "qualification_type", "qualificationType", "qualification", "category", "attribute"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="feedback",
        aliases=("feedback", "studentFeedback"),
        model=models_a.StudentFeedback,
        section_title="Student Feedback",
        column_aliases={
            "course_code": ("course_code", "courseCode", "course_code_name", "courseCodeName"),
            "feedback_1": ("feedback_1", "feedback1", "feedback_odd"),
            "feedback_2": ("feedback_2", "feedback2", "feedback_even"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="deptActs",
        aliases=("deptActs", "deptActivities", "departmentActivities"),
        model=models_a.DepartmentActivity,
        section_title="Departmental / School Activities",
        column_aliases={
            "activity": ("activity", "activity_type", "activityType"),
            "nature": ("nature", "nature_of_activity", "natureOfActivity"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="uniActs",
        aliases=("uniActs", "uniActivities", "universityActivities"),
        model=models_a.UniversityActivity,
        section_title="University Level Activities",
        column_aliases={
            "activity": ("activity", "activity_type", "activityType"),
            "nature": ("nature", "nature_of_activity", "natureOfActivity"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="society",
        aliases=("society", "socialContributions"),
        model=models_a.SocialContribution,
        section_title="Contribution to Society",
        column_aliases={
            "activity": ("activity", "societyActivity", "society_activity", "activity_type", "activityType"),
            "status": ("status",),
            "details": ("details", "short_description", "shortDescription", "description"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="industry",
        aliases=("industry", "industryConnect"),
        model=models_a.IndustryConnect,
        section_title="Industry Connect",
        column_aliases={
            "name": ("name", "industryName", "industry_name", "company_industry", "companyIndustry", "company"),
            "details": ("details", "short_description", "shortDescription", "description"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="acr",
        aliases=("acr", "acrScores"),
        model=models_a.ACRScore,
        section_title="Annual Confidential Report - School Level",
        column_aliases={
            "label": ("label", "category", "attribute"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="events",
        aliases=("events", "eventRows"),
        model=models_a.EventOrganization,
        section_title="C3. Event Organisation & Institutional Visibility",
        column_aliases={
            "event": ("event", "event_title", "eventTitle", "title"),
            "role": ("role", "event_role"),
            "date": ("date", "event_date"),
            "level": ("level", "event_level", "eventLevel"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
        allowed_display_fields=("organization", "hosting_organization", "hostingOrganization", "venue", "description"),
    ),
    StandardSectionContract(
        canonical_key="alumni",
        aliases=("alumni", "alumniRows"),
        model=models_a.AlumniEngagement,
        section_title="C6. Alumni Engagement & Networking",
        column_aliases={
            "activity": ("activity", "activity_type", "activityType", "title"),
            "details": ("details", "short_description", "shortDescription", "description"),
            "date": ("date", "activity_date"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="placements",
        aliases=("placements", "placementRows"),
        model=models_a.PlacementMentoring,
        section_title="C7. Student Placement Mentoring & Career Development",
        column_aliases={
            "type": ("type", "activityType", "activity_type"),
            "name": ("name", "student_name", "studentName", "company", "company_name"),
            "date": ("date", "placement_date"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),

    # --- PART B ---
    StandardSectionContract(
        canonical_key="journals",
        aliases=("journals", "journalPublications"),
        model=models_b.JournalPublication,
        section_title="B1. Research Papers / Journal Publications",
        column_aliases={
            "title": ("title", "title_with_page_nos", "titleWithPageNos", "title_and_pages", "titleAndPages", "paper_title"),
            "journal": ("journal", "journal_details", "journalDetails", "journal_name", "journalName"),
            "issn": ("issn", "issn_isbn_no", "issn_isbn", "issnIsbnNo", "issnNo"),
            "indexing": ("indexing", "journal_indexing", "indexingType"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
        allowed_display_fields=("impactFactor", "impact_factor", "authorPosition", "author_position", "authorPos", "date", "publication_date", "volume", "page_no", "pageNo", "pages", "peer_reviewed", "doi"),
    ),
    StandardSectionContract(
        canonical_key="books",
        aliases=("books", "bookPublications"),
        model=models_b.BookPublication,
        section_title="B2. Books / Book Chapters",
        column_aliases={
            "title": ("title", "book_title", "title_and_pages", "title_with_page_nos"),
            "book": ("book", "book_title_editor", "bookTitleEditor", "book_name", "bookName", "editor"),
            "issn": ("issn", "issn_no"),
            "isbn": ("isbn", "isbn_no", "issn_isbn_no", "issn_isbn"),
            "publisher": ("publisher", "publisher_name"),
            "coauthor": ("coauthor", "co_author", "coAuthors"),
            "first_author": ("first_author", "firstAuthor"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
        allowed_display_fields=("level", "book_level", "edition", "author_position", "authorPosition", "year", "date"),
    ),
    StandardSectionContract(
        canonical_key="ict",
        aliases=("ict", "ictPedagogy"),
        model=models_b.ICTPedagogy,
        section_title="B3. ICT / E-Content / Pedagogy",
        column_aliases={
            "title": ("title", "course_title"),
            "description": ("description", "details", "short_description"),
            "type": ("type", "pedagogy_type", "pedagogyType", "activityType"),
            "quadrant": ("quadrant", "e_content_quadrant"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="research",
        aliases=("research", "researchGuidance"),
        model=models_b.ResearchGuidance,
        section_title="B4(a). Research Guidance - PhD / PG",
        column_aliases={
            "degree": ("degree", "level", "degree_level", "degreeLevel"),
            "student_name": ("student_name", "studentName", "name", "candidate_name"),
            "thesis": ("thesis", "thesis_title", "thesisTitle", "title"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="projects2",
        aliases=("projects2", "internalProjects", "researchProjects"),
        model=models_b.ResearchProject,
        section_title="B4(b). Research / Consultancy Internal Projects",
        column_aliases={
            "title": ("title", "project_title", "projectTitle"),
            "agency": ("agency", "funding_agency", "fundingAgency"),
            "sanction_date": ("sanction_date", "sanctionDate", "date"),
            "amount": ("amount", "grant_amount", "grantAmount", "sanctioned_amount", "sanctionedAmount"),
            "role": ("role", "pi_co_pi", "piCoPi", "project_role", "projectRole"),
            "project_status": ("project_status", "projectStatus", "status"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="externalProjects",
        aliases=("externalProjects", "externalResearchProjects"),
        model=models_b.ExternalResearchProject,
        section_title="B4(c). Research / Consultancy External Projects",
        column_aliases={
            "title": ("title", "project_title", "projectTitle"),
            "agency": ("agency", "funding_agency", "fundingAgency"),
            "sanction_date": ("sanction_date", "sanctionDate", "date"),
            "amount": ("amount", "grant_amount", "grantAmount", "sanctioned_amount", "sanctionedAmount"),
            "role": ("role", "pi_co_pi", "piCoPi", "project_role", "projectRole"),
            "project_status": ("project_status", "projectStatus", "status"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="patents",
        aliases=("patents", "patentRecords"),
        model=models_b.Patent,
        section_title="B5(a). Patents (IPR)",
        column_aliases={
            "title": ("title", "patent_title", "patentTitle"),
            "type": ("type", "patent_type", "patentType"),
            "scope": ("scope", "patent_scope", "patentScope", "level"),
            "patent_date": ("patent_date", "patentDate", "date", "filing_date", "filingDate", "award_date", "awardDate"),
            "patent_status": ("patent_status", "patentStatus", "status"),
            "file_no": ("file_no", "fileNo", "filing_no", "filingNo", "application_no", "applicationNo", "reference_no", "referenceNo"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="awards",
        aliases=("awards", "awardRecords"),
        model=models_b.Award,
        section_title="B5(b). Awards",
        column_aliases={
            "title": ("title", "award_title", "awardTitle", "name"),
            "award_date": ("award_date", "awardDate", "date"),
            "agency": ("agency", "organization", "awarding_body", "awardingBody"),
            "level": ("level", "award_level", "awardLevel"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="confs",
        aliases=("confs", "conferences"),
        model=models_b.Conference,
        section_title="B6. Invited Lectures / Resource Person / Paper Presentations",
        column_aliases={
            "title": ("title", "paper_title", "paperTitle", "presentation_title", "presentationTitle"),
            "type": ("type", "presentation_type", "presentationType", "activityType", "activity_type"),
            "organization": ("organization", "hosting_organization", "hostingOrganization", "organizer"),
            "level": ("level", "conference_level", "conferenceLevel", "event_level", "eventLevel"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="proposals",
        aliases=("proposals", "researchProposals"),
        model=models_b.ResearchProposal,
        section_title="B7(a). Submitted Research Proposals",
        column_aliases={
            "title": ("title", "proposal_title", "proposalTitle"),
            "duration": ("duration", "project_duration", "projectDuration"),
            "agency": ("agency", "funding_agency", "fundingAgency"),
            "amount": ("amount", "requested_amount", "requestedAmount", "proposed_amount", "proposedAmount"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="products",
        aliases=("products", "productsDeveloped"),
        model=models_b.ProductDeveloped,
        section_title="B7(b). Product Developed and Used by Students",
        column_aliases={
            "details": ("details", "product_name", "productName", "product_details", "productDetails", "title"),
            "usage": ("usage", "student_usage", "studentUsage", "usage_details", "usageDetails"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="fdps",
        aliases=("fdps", "selfDevelopment"),
        model=models_b.SelfDevelopment,
        section_title="B8(a). FDP / Workshops",
        column_aliases={
            "program": ("program", "program_title", "programTitle", "title", "course_program", "courseProgram"),
            "duration": ("duration", "duration_days", "durationDays"),
            "organization": ("organization", "hosting_organization", "hostingOrganization", "organizer"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
    StandardSectionContract(
        canonical_key="training",
        aliases=("training", "industrialTraining"),
        model=models_b.IndustrialTraining,
        section_title="B8(b). Industrial Training",
        column_aliases={
            "company": ("company", "company_industry", "companyIndustry", "organization", "name"),
            "duration": ("duration", "duration_days", "durationDays"),
            "nature": ("nature", "nature_of_training", "natureOfTraining"),
            "score": ("score", "selfScore", "self_score", "selfMarks", "self_marks"),
            "max_marks": ("max_marks", "maxMarks", "max"),
        },
    ),
]


def resolve_section_data(
    form_data: Dict[str, Any],
    contract: StandardSectionContract
) -> Tuple[Optional[Any], List[str]]:
    """
    Extracts data for a section from form_data by checking canonical key and aliases.
    Resolves conflicts deterministically and produces section/field diagnostics.
    """
    diagnostics: List[str] = []
    found_entries: List[Tuple[str, Any]] = []

    for k in contract.all_keys:
        if k in form_data:
            val = form_data[k]
            if val is not None:
                found_entries.append((k, val))

    if not found_entries:
        return None, diagnostics

    if len(found_entries) == 1:
        return found_entries[0][1], diagnostics

    # Multiple alias keys present in payload:
    # Filter out empty lists / empty dicts if other non-empty entries exist
    non_empty = [e for e in found_entries if e[1] not in ([], {}, "", None)]
    if len(non_empty) == 1:
        return non_empty[0][1], diagnostics
    elif len(non_empty) == 0:
        # All are empty
        return found_entries[0][1], diagnostics

    # Both have content: prefer canonical key if present, else first alias
    canonical_entry = next((e for e in non_empty if e[0] == contract.canonical_key), None)
    chosen = canonical_entry or non_empty[0]

    # Diagnostic warning (identifies section without logging personal data/tokens)
    keys_found = [e[0] for e in non_empty]
    diagnostics.append(f"Section '{contract.canonical_key}': duplicate alias keys {keys_found} resolved to '{chosen[0]}'")
    logger.warning(f"Standard Compatibility: Section '{contract.canonical_key}' has multiple aliases {keys_found}. Using '{chosen[0]}'.")

    return chosen[1], diagnostics


def normalize_row_item(
    item: Dict[str, Any],
    contract: StandardSectionContract,
    row_no: int,
    email: str,
    year: str,
    form_family: str,
) -> Tuple[Any, List[str]]:
    """
    Normalizes a single row dictionary into an instantiated SQLAlchemy model with proper
    coerced column values, flattened custom_fields, and stripped reviewer marks.
    """
    diagnostics: List[str] = []
    model_cls = contract.model

    kwargs = {
        "faculty_email": email,
        "academic_year": year,
        "form_family": form_family,
        "section_title": contract.section_title,
    }
    if hasattr(model_cls, "row_no"):
        kwargs["row_no"] = row_no

    db_item = model_cls(**kwargs)

    # 1. Unpack and flatten any incoming custom_fields
    raw_custom = item.get("custom_fields")
    flattened_custom = _flatten_custom_fields(raw_custom) if raw_custom else {}

    # 2. Extract column values using deterministic alias precedence
    consumed_keys = set()
    all_known_aliases = set()
    for col_name, aliases in contract.column_aliases.items():
        all_known_aliases.update(aliases)
        val_to_set = None
        chosen_alias = None

        # Check canonical column name first, then aliases
        ordered_candidates = (col_name,) + tuple(a for a in aliases if a != col_name)
        for cand in ordered_candidates:
            if cand in item and item[cand] is not None:
                val = item[cand]
                # Preserve 0, False, and non-empty values
                if val != "":
                    val_to_set = val
                    chosen_alias = cand
                    break
                elif val == "" and val_to_set is None:
                    val_to_set = val
                    chosen_alias = cand

        # Fallback to flattened custom fields if column value is missing
        if val_to_set is None:
            for cand in ordered_candidates:
                if cand in flattened_custom and flattened_custom[cand] is not None:
                    val_to_set = flattened_custom.pop(cand)
                    break

        if val_to_set is not None:
            if isinstance(db_item, models_a.CourseFile) and col_name == "details":
                val_to_set = normalize_details_value(val_to_set)
            coerced = _coerce_for_column(db_item, col_name, val_to_set)
            if coerced is not None:
                setattr(db_item, col_name, coerced)

        for cand in aliases:
            if cand in item:
                consumed_keys.add(cand)

    # 3. Gather unknown / extra fields into custom_fields
    final_custom: Dict[str, Any] = dict(flattened_custom)
    for k, v in item.items():
        if k in consumed_keys or k == "custom_fields":
            continue
        if hasattr(db_item, k) and k != "custom_fields":
            # Direct model attribute match not in column_aliases
            if k not in DISALLOWED_CUSTOM_KEYS:
                coerced = _coerce_for_column(db_item, k, v)
                if coerced is not None:
                    setattr(db_item, k, coerced)
            consumed_keys.add(k)
        else:
            # Side-channel extra field
            if k not in DISALLOWED_CUSTOM_KEYS:
                final_custom[k] = v
            consumed_keys.add(k)

    # Clean any disallowed keys from custom_fields
    for bad_key in list(final_custom.keys()):
        if bad_key in DISALLOWED_CUSTOM_KEYS or bad_key == "custom_fields":
            final_custom.pop(bad_key, None)

    if hasattr(db_item, "custom_fields"):
        db_item.custom_fields = final_custom

    return db_item, diagnostics


async def shred_standard_form(
    db: AsyncSession,
    email: str,
    year: str,
    form_data: Dict[str, Any],
    form_family: str = STANDARD_FORM_FAMILY,
) -> int:
    """
    Shreds Standard Appraisal JSON form into normalized SQL tables.
    Processes each storage model EXACTLY ONCE per submission, avoiding multi-alias deletion bugs.
    """
    total_added = 0

    for contract in STANDARD_SECTIONS:
        # 1. Resolve section data across canonical key and aliases
        section_raw, _ = resolve_section_data(form_data, contract)

        # 2. Delete existing records for this model ONCE
        await db.execute(
            delete(contract.model).where(
                contract.model.faculty_email == email,
                contract.model.academic_year == year,
            ),
            execution_options={"synchronize_session": False},
        )

        # 3. Process scalar section (InnovativeTeaching)
        if contract.is_scalar:
            innov_details = section_raw
            innov_score_raw = form_data.get("innovScore")
            if isinstance(innov_details, dict):
                details_text = innov_details.get("details", "")
                if innov_score_raw is None:
                    innov_score_raw = innov_details.get("score") or innov_details.get("selfScore")
            else:
                details_text = str(innov_details) if innov_details is not None else ""

            if details_text or (innov_score_raw is not None and str(innov_score_raw).strip() != ""):
                innov = models_a.InnovativeTeaching(
                    faculty_email=email,
                    academic_year=year,
                    form_family=form_family,
                    section_title=contract.section_title,
                    details=details_text,
                    row_no=1,
                )
                if innov_score_raw is not None:
                    innov.score = _coerce_for_column(innov, "score", innov_score_raw) or 0
                db.add(innov)
                total_added += 1
            continue

        if section_raw is None:
            logger.info(f"shred_standard_form: section '{contract.canonical_key}' omitted in submission")
            continue

        # 4. Process list of rows
        items = section_raw if isinstance(section_raw, list) else [section_raw]
        section_count = 0
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            db_item, _ = normalize_row_item(
                item=item,
                contract=contract,
                row_no=idx + 1,
                email=email,
                year=year,
                form_family=form_family,
            )
            db.add(db_item)
            section_count += 1

        total_added += section_count
        logger.info(f"shred_standard_form: section '{contract.canonical_key}' → {section_count} row(s) queued")

    return total_added


def normalize_standard_snapshot_read(payload: Any, is_standard: bool) -> Any:
    """
    Read-side compatibility transform for Standard Appraisal snapshots.
    Restores known display fields from custom_fields only when canonical value is null/missing.
    Preserves explicit blank/0/false and does not promote reviewer scores or authorization metadata.
    """
    if not is_standard or not isinstance(payload, dict):
        return payload

    form = payload.get("form") if isinstance(payload.get("form"), dict) else (payload.get("payload", {}).get("form") if isinstance(payload.get("payload"), dict) else None)
    if not form or not isinstance(form, dict):
        return payload

    for contract in STANDARD_SECTIONS:
        # Check canonical key and aliases
        found_key = next((k for k in contract.all_keys if k in form and isinstance(form[k], (list, dict))), None)
        if not found_key:
            continue

        rows = form[found_key]
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                cf = row.get("custom_fields")
                if isinstance(cf, dict):
                    flat_cf = _flatten_custom_fields(cf)
                    for disp_field in contract.allowed_display_fields:
                        if disp_field in flat_cf and (disp_field not in row or row[disp_field] is None):
                            row[disp_field] = flat_cf[disp_field]

    # Additive contract version metadata for observability
    if "_contract_version" not in payload:
        payload["_contract_version"] = "standard_v1"

    return payload
