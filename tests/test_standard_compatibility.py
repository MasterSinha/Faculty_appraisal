import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.core import FacultyProfile, Declaration, AppraisalSnapshot, AppraisalReview
from src.models import part_a as models_a
from src.models import part_b as models_b
from src.setup.local_auth import create_access_token
from src.setup.standard_compatibility import (
    is_standard_form_submission,
    shred_standard_form,
    normalize_standard_snapshot_read,
    _flatten_custom_fields,
)

pytestmark = pytest.mark.asyncio

YEAR = "2025-2026"
STANDARD_EMAIL = "std_faculty@test.com"
MEDIA_EMAIL = "media_faculty@test.com"
HOD_EMAIL = "hod_user@test.com"


async def create_faculty(db: AsyncSession, email: str, role: str = "faculty", school: str = "SoCSEA", dept: str = "Computer Science"):
    user = FacultyProfile(
        email=email,
        full_name=email.split("@")[0].capitalize(),
        appraisal_role=role,
        school=school,
        department=dept,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def auth_header(email: str, role: str = "faculty", school: str = "SoCSEA", dept: str = "Computer Science"):
    token = create_access_token(
        data={
            "email": email,
            "sub": email,
            "id": "1",
            "role": role,
            "appraisal_role": role,
            "roles": [role],
            "school": school,
            "department": dept,
        }
    )
    return {"Authorization": f"Bearer {token}"}


async def test_is_standard_form_submission_detection(db: AsyncSession):
    """Verifies that Standard submission detection is accurate and not based on guesses."""
    assert is_standard_form_submission(form_family="standard") is True
    assert is_standard_form_submission(school="SoCSEA") is True
    assert is_standard_form_submission(school="SoBB") is True
    assert is_standard_form_submission(school="CISR") is True
    assert is_standard_form_submission(form_family="media") is False
    assert is_standard_form_submission(school="SoMCS") is False
    assert is_standard_form_submission(form_family="design") is False
    assert is_standard_form_submission(school="SoD") is False
    assert is_standard_form_submission(payload={"form_family": "standard"}) is True
    assert is_standard_form_submission(payload={"form": {"form_family": "standard"}}) is True
    assert is_standard_form_submission(payload={"form_family": "media"}) is False


async def test_flatten_custom_fields():
    """Verifies recursive unnesting of custom_fields."""
    nested = {
        "impactFactor": 4.5,
        "custom_fields": {
            "authorPosition": "First",
            "custom_fields": {
                "volume": "12",
                "page_no": "100-110",
            },
        },
    }
    flattened = _flatten_custom_fields(nested)
    assert flattened == {
        "impactFactor": 4.5,
        "authorPosition": "First",
        "volume": "12",
        "page_no": "100-110",
    }


async def test_reproduction_event_alumni_placement_alias_deletion_bug(db: AsyncSession):
    """
    Reproduces and verifies fix for the bug where absent alias (e.g. eventRows) deleted
    rows inserted by the first alias (e.g. events).
    """
    form_data = {
        "events": [
            {
                "event": "AI Conference 2025",
                "role": "Organizing Chair",
                "date": "2025-04-10",
                "level": "International",
                "score": 10,
                "organization": "IEEE",
            }
        ],
        "alumni": [
            {
                "activity": "Alumni Mentorship Series",
                "details": "Conducted 3 sessions for final year students",
                "date": "2025-05-01",
                "score": 5,
            }
        ],
        "placements": [
            {
                "type": "Mock Interviews",
                "name": "Google Mentorship Cohort",
                "date": "2025-03-15",
                "score": 5,
            }
        ],
    }

    # Shred standard form
    added = await shred_standard_form(db, STANDARD_EMAIL, YEAR, form_data, form_family="standard")
    await db.commit()

    assert added == 3

    # Check EventOrganization
    events_res = await db.execute(
        select(models_a.EventOrganization).where(
            models_a.EventOrganization.faculty_email == STANDARD_EMAIL,
            models_a.EventOrganization.academic_year == YEAR,
        )
    )
    events = events_res.scalars().all()
    assert len(events) == 1
    assert events[0].event == "AI Conference 2025"
    assert events[0].role == "Organizing Chair"
    assert events[0].level == "International"
    assert events[0].score == 10
    assert events[0].custom_fields.get("organization") == "IEEE"

    # Check AlumniEngagement
    alumni_res = await db.execute(
        select(models_a.AlumniEngagement).where(
            models_a.AlumniEngagement.faculty_email == STANDARD_EMAIL,
            models_a.AlumniEngagement.academic_year == YEAR,
        )
    )
    alumni = alumni_res.scalars().all()
    assert len(alumni) == 1
    assert alumni[0].activity == "Alumni Mentorship Series"

    # Check PlacementMentoring
    placements_res = await db.execute(
        select(models_a.PlacementMentoring).where(
            models_a.PlacementMentoring.faculty_email == STANDARD_EMAIL,
            models_a.PlacementMentoring.academic_year == YEAR,
        )
    )
    placements = placements_res.scalars().all()
    assert len(placements) == 1
    assert placements[0].name == "Google Mentorship Cohort"


async def test_alias_precedence_and_zero_preservation(db: AsyncSession):
    """
    Verifies that 0, False, and explicit values are preserved deterministically
    when aliases are resolved.
    """
    form_data = {
        "lectures": [
            {
                "semester": "Fall 2025",
                "courseCodeName": "CS101",
                "plannedClasses": 45,
                "conductedClasses": 0,  # 0 must not be treated as empty or replaced by default
                "selfScore": 0,         # 0 score must be preserved
                "score": "",            # empty string should not override 0
            }
        ],
        "feedback": [
            {
                "course_code": "CS101",
                "feedback_odd": 85.5,
                "feedback_even": 0.0,
                "selfMarks": 15,
            }
        ],
    }

    added = await shred_standard_form(db, STANDARD_EMAIL, YEAR, form_data, form_family="standard")
    await db.commit()

    assert added == 2

    # Verify TeachingProcess
    teach_res = await db.execute(
        select(models_a.TeachingProcess).where(
            models_a.TeachingProcess.faculty_email == STANDARD_EMAIL,
            models_a.TeachingProcess.academic_year == YEAR,
        )
    )
    row = teach_res.scalar_one()
    assert row.course_code == "CS101"
    assert row.planned_classes == 45
    assert row.conducted_classes == 0
    assert row.score == 0

    # Verify StudentFeedback
    fb_res = await db.execute(
        select(models_a.StudentFeedback).where(
            models_a.StudentFeedback.faculty_email == STANDARD_EMAIL,
            models_a.StudentFeedback.academic_year == YEAR,
        )
    )
    fb_row = fb_res.scalar_one()
    assert fb_row.course_code == "CS101"
    assert float(fb_row.feedback_1) == 85.5
    assert float(fb_row.feedback_2) == 0.0
    assert float(fb_row.score) == 15.0


async def test_nested_custom_fields_resubmission_safety(db: AsyncSession):
    """
    Verifies that resubmitting forms with nested custom_fields flattens them cleanly
    and preserves non-SQL fields like impactFactor and authorPosition without recursion.
    """
    form_data = {
        "journals": [
            {
                "title": "Quantum Computing Advances",
                "journal": "Nature Physics",
                "issn": "1745-2473",
                "indexing": "SCI",
                "score": 25,
                "custom_fields": {
                    "impactFactor": 19.6,
                    "authorPosition": "First",
                    "custom_fields": {
                        "volume": "21",
                        "page_no": "45-52",
                    },
                },
            }
        ]
    }

    # Initial shred
    await shred_standard_form(db, STANDARD_EMAIL, YEAR, form_data, form_family="standard")
    await db.commit()

    j_res = await db.execute(
        select(models_b.JournalPublication).where(
            models_b.JournalPublication.faculty_email == STANDARD_EMAIL,
            models_b.JournalPublication.academic_year == YEAR,
        )
    )
    j_row = j_res.scalar_one()
    assert j_row.title == "Quantum Computing Advances"
    assert j_row.journal == "Nature Physics"
    assert j_row.issn == "1745-2473"
    assert j_row.indexing == "SCI"
    assert "custom_fields" not in j_row.custom_fields  # Ensure no recursive key
    assert j_row.custom_fields.get("impactFactor") == 19.6
    assert j_row.custom_fields.get("authorPosition") == "First"
    assert j_row.custom_fields.get("volume") == "21"
    assert j_row.custom_fields.get("page_no") == "45-52"

    # Resubmission simulating client passing back the existing record
    resubmitted_form_data = {
        "journals": [
            {
                "title": "Quantum Computing Advances - Revised",
                "journal": "Nature Physics",
                "issn": "1745-2473",
                "indexing": "SCI",
                "score": 25,
                "custom_fields": j_row.custom_fields,
            }
        ]
    }

    await shred_standard_form(db, STANDARD_EMAIL, YEAR, resubmitted_form_data, form_family="standard")
    await db.commit()

    j_res2 = await db.execute(
        select(models_b.JournalPublication).where(
            models_b.JournalPublication.faculty_email == STANDARD_EMAIL,
            models_b.JournalPublication.academic_year == YEAR,
        )
    )
    j_row2 = j_res2.scalar_one()
    assert j_row2.title == "Quantum Computing Advances - Revised"
    assert "custom_fields" not in j_row2.custom_fields
    assert j_row2.custom_fields.get("impactFactor") == 19.6
    assert j_row2.custom_fields.get("authorPosition") == "First"


async def test_client_reviewer_marks_stripping(db: AsyncSession):
    """
    Verifies that client-supplied reviewer marks (e.g. hod_score, vc_score, status)
    in custom_fields or payload are rejected and cannot overwrite server fields.
    """
    form_data = {
        "lectures": [
            {
                "semester": "Spring 2026",
                "course_code": "CS202",
                "planned_classes": 40,
                "conducted_classes": 40,
                "score": 20,
                "hod_score": 99,  # Malicious spoof attempt
                "director_score": 99,
                "custom_fields": {
                    "vc_score": 99,
                    "status": "Approved",
                    "notes": "Legitimate note",
                },
            }
        ]
    }

    await shred_standard_form(db, STANDARD_EMAIL, YEAR, form_data, form_family="standard")
    await db.commit()

    teach_res = await db.execute(
        select(models_a.TeachingProcess).where(
            models_a.TeachingProcess.faculty_email == STANDARD_EMAIL,
            models_a.TeachingProcess.academic_year == YEAR,
        )
    )
    row = teach_res.scalar_one()
    assert row.score == 20
    # Server reviewer columns should be None (not spoofed)
    assert row.hod_score is None
    assert row.director_score is None
    assert row.vc_score is None
    # custom_fields should only contain legitimate non-disallowed keys
    assert "vc_score" not in row.custom_fields
    assert "status" not in row.custom_fields
    assert row.custom_fields.get("notes") == "Legitimate note"


async def test_read_compatibility_restores_display_fields():
    """
    Verifies that normalize_standard_snapshot_read restores known display fields
    from custom_fields without mutating explicit values.
    """
    payload = {
        "form_family": "standard",
        "form": {
            "journals": [
                {
                    "title": "Deep Learning Systems",
                    "journal": "IEEE Transactions",
                    "custom_fields": {
                        "impactFactor": 8.2,
                        "authorPosition": "Corresponding",
                    },
                },
                {
                    "title": "Quantum Mechanics",
                    "journal": "Phys Rev",
                    "impactFactor": 12.0,  # Explicit top level
                    "custom_fields": {
                        "impactFactor": 8.0,  # Stale custom_fields value
                    },
                },
            ]
        },
    }

    normalized = normalize_standard_snapshot_read(payload, is_standard=True)

    # First row: missing at top level -> promoted from custom_fields
    row1 = normalized["form"]["journals"][0]
    assert row1["impactFactor"] == 8.2
    assert row1["authorPosition"] == "Corresponding"
    assert row1["custom_fields"]["impactFactor"] == 8.2

    # Second row: explicit top level 12.0 must NOT be overridden by stale 8.0
    row2 = normalized["form"]["journals"][1]
    assert row2["impactFactor"] == 12.0
    assert row2["custom_fields"]["impactFactor"] == 8.0

    # Contract version marker is additive
    assert normalized.get("_contract_version") == "standard_v1"


async def test_full_appraisal_submit_and_snapshot_read_api(client: AsyncClient, db: AsyncSession):
    """
    Full end-to-end integration test through HTTP API for Standard Appraisal submit and snapshot retrieval.
    """
    await create_faculty(db, STANDARD_EMAIL, role="faculty", school="SoCSEA", dept="Computer Science")
    headers = auth_header(STANDARD_EMAIL, role="faculty", school="SoCSEA", dept="Computer Science")

    payload = {
        "academic_year": YEAR,
        "form_family": "standard",
        "form": {
            "lectures": [
                {
                    "semester": "Sem 1",
                    "courseCode": "CS101",
                    "planned": 40,
                    "conducted": 40,
                    "selfScore": 25,
                }
            ],
            "courseFile": [
                {
                    "course": "CS101",
                    "title": "Intro to CS",
                    "details": "1.Available",
                    "selfScore": 10,
                }
            ],
            "events": [
                {
                    "event": "Hackathon 2025",
                    "role": "Coordinator",
                    "date": "2025-02-20",
                    "level": "National",
                    "selfScore": 10,
                    "organization": "DYPIU ACM",
                }
            ],
            "journals": [
                {
                    "title_with_page_nos": "AI in Healthcare pp. 1-10",
                    "journal_details": "Lancet Digital Health",
                    "issn_isbn_no": "2589-7500",
                    "indexing": "Scopus",
                    "selfScore": 25,
                    "custom_fields": {
                        "impactFactor": 24.5,
                        "authorPosition": "First",
                    },
                }
            ],
        },
        "totals": {
            "partATotal": 45,
            "partBTotal": 25,
            "grandTotal": 70,
        },
    }

    # Submit appraisal via /api/v1/appraisal/submit
    submit_res = await client.post("/api/v1/appraisal/submit", json=payload, headers=headers)
    assert submit_res.status_code == 200, submit_res.text
    resp_data = submit_res.json()
    assert resp_data["message"] == "Submitted successfully"

    # Read snapshot via /api/v1/appraisal/snapshot
    snap_res = await client.get(f"/api/v1/appraisal/snapshot?academic_year={YEAR}", headers=headers)
    assert snap_res.status_code == 200, snap_res.text
    snap_data = snap_res.json()

    snap_payload = snap_data.get("payload", {})
    snap_form = snap_payload.get("form", {})

    # Check journal has restored impactFactor on read
    journals = snap_form.get("journals", [])
    assert len(journals) == 1
    assert journals[0]["impactFactor"] == 24.5

    # Check EventOrganization table has 1 record (not deleted by eventRows alias)
    events_res = await db.execute(
        select(models_a.EventOrganization).where(
            models_a.EventOrganization.faculty_email == STANDARD_EMAIL,
            models_a.EventOrganization.academic_year == YEAR,
        )
    )
    assert len(events_res.scalars().all()) == 1


async def test_api_v2_route_consistency(client: AsyncClient, db: AsyncSession):
    """
    Verifies that /api/v2/appraisal behaves identically to /api/v1/appraisal.
    """
    v2_email = "v2_std_faculty@test.com"
    await create_faculty(db, v2_email, role="faculty", school="SoCSEA", dept="Computer Science")
    headers = auth_header(v2_email, role="faculty", school="SoCSEA", dept="Computer Science")

    payload = {
        "academic_year": YEAR,
        "form_family": "standard",
        "form": {
            "lectures": [
                {
                    "semester": "Sem 2",
                    "course_code": "CS102",
                    "planned_classes": 30,
                    "conducted_classes": 30,
                    "score": 20,
                }
            ]
        },
        "totals": {
            "partATotal": 20,
            "grandTotal": 20,
        },
    }

    # Submit via /api/v2
    submit_res = await client.post("/api/v2/appraisal/submit", json=payload, headers=headers)
    assert submit_res.status_code == 200
    assert submit_res.json()["message"] == "Submitted successfully"

    # Read via /api/v2
    snap_res = await client.get(f"/api/v2/appraisal/snapshot?academic_year={YEAR}", headers=headers)
    assert snap_res.status_code == 200
    assert snap_res.json()["payload"]["form"]["lectures"][0]["course_code"] == "CS102"


async def test_all_standard_sections_shredding(db: AsyncSession):
    """
    Verifies that all 27 standard appraisal sections are properly shredded,
    coerced, and stored with their respective models and custom_fields.
    """
    all_sections_form = {
        "lectures": [{"semester": "Sem 1", "courseCode": "CS101", "planned": 40, "conducted": 40, "selfScore": 25}],
        "courseFile": [{"course": "CS101", "title": "Intro to CS", "details": "1.Available", "selfScore": 10}],
        "innovDetails": "Implemented flipped classroom model",
        "innovScore": 15,
        "projects": [{"projectCategory": "UG Major Project", "selfScore": 10}],
        "quals": [{"qualificationType": "PhD", "selfScore": 10}],
        "feedback": [{"course_code": "CS101", "feedback_odd": 88, "feedback_even": 90, "selfScore": 15}],
        "deptActs": [{"activityType": "NBA Coordinator", "natureOfActivity": "Departmental", "selfScore": 10}],
        "uniActs": [{"activityType": "Convocation Committee", "natureOfActivity": "University", "selfScore": 10}],
        "society": [{"societyActivity": "Blood Donation Camp", "status": "Completed", "description": "Organized annual drive", "selfScore": 5}],
        "industry": [{"companyIndustry": "TCS", "description": "MoU signed for internship", "selfScore": 10}],
        "acr": [{"category": "Overall Assessment", "selfScore": 10}],
        "eventRows": [{"eventTitle": "National Symposium", "role": "Organizer", "eventDate": "2025-06-15", "eventLevel": "National", "selfScore": 10, "organization": "ACM"}],
        "alumniRows": [{"activityType": "Talk on Cloud Computing", "description": "Guest session by alumni", "activityDate": "2025-07-20", "selfScore": 5}],
        "placementRows": [{"activityType": "Placement Training", "name": "Resume Building Workshop", "placementDate": "2025-08-10", "selfScore": 5}],
        "journals": [{"titleWithPageNos": "Distributed Consensus", "journalDetails": "ACM Computing Surveys", "issnIsbnNo": "0360-0300", "indexingType": "SCI", "selfScore": 30, "impactFactor": 16.5, "authorPosition": "First"}],
        "books": [{"titleAndPages": "Operating Systems", "bookTitleEditor": "Pearson", "isbnNo": "978-0133591620", "publisher": "Pearson", "selfScore": 20, "level": "International"}],
        "ict": [{"title": "Cloud Computing Course", "description": "Developed 4 quadrants e-content", "pedagogyType": "SWAYAM", "quadrant": "Quadrant 1 & 2", "selfScore": 15}],
        "research": [{"degreeLevel": "PhD", "studentName": "John Doe", "thesisTitle": "AI in Edge Computing", "selfScore": 20}],
        "projects2": [{"projectTitle": "Smart Campus IoT", "fundingAgency": "Internal University Grant", "sanctionDate": "2025-01-10", "grantAmount": 50000, "role": "PI", "projectStatus": "Ongoing", "selfScore": 15}],
        "externalProjects": [{"projectTitle": "National Health AI", "fundingAgency": "DST-SERB", "sanctionDate": "2025-02-15", "grantAmount": 2500000, "role": "Co-PI", "projectStatus": "Sanctioned", "selfScore": 25}],
        "patents": [{"patentTitle": "Adaptive Routing in Mesh Networks", "patentType": "Granted", "patentScope": "National", "patentDate": "2025-03-20", "patentStatus": "Published", "fileNo": "IN2025010023", "selfScore": 20}],
        "awards": [{"awardTitle": "Young Scientist Award", "awardDate": "2025-04-05", "awardingBody": "IEEE", "awardLevel": "National", "selfScore": 15}],
        "confs": [{"paperTitle": "Deep Learning on Resource-Constrained Devices", "presentationType": "Keynote", "hostingOrganization": "IEEE India", "conferenceLevel": "International", "selfScore": 15}],
        "proposals": [{"proposalTitle": "Quantum Cryptography for IoT", "projectDuration": "3 Years", "fundingAgency": "DRDO", "requestedAmount": 4500000, "selfScore": 10}],
        "products": [{"productDetails": "Automated Proctoring System", "studentUsage": "Used in Mid-term exams by 500+ students", "selfScore": 15}],
        "fdps": [{"programTitle": "Advanced AI/ML FDP", "durationDays": "5 Days", "hostingOrganization": "IIT Bombay", "selfScore": 10}],
        "training": [{"company": "Infosys Mysore", "durationDays": "14 Days", "natureOfTraining": "Cloud Architecture", "selfScore": 10}],
    }

    added = await shred_standard_form(db, STANDARD_EMAIL, YEAR, all_sections_form, form_family="standard")
    await db.commit()

    # All 27 sections queued
    assert added == 27

    # Verify innovative teaching
    innov_res = await db.execute(select(models_a.InnovativeTeaching).where(models_a.InnovativeTeaching.faculty_email == STANDARD_EMAIL))
    innov = innov_res.scalar_one()
    assert innov.details == "Implemented flipped classroom model"
    assert float(innov.score) == 15.0

    # Verify external research project
    ext_res = await db.execute(select(models_b.ExternalResearchProject).where(models_b.ExternalResearchProject.faculty_email == STANDARD_EMAIL))
    ext = ext_res.scalar_one()
    assert ext.title == "National Health AI"
    assert ext.agency == "DST-SERB"
    assert float(ext.amount) == 2500000.0

    # Verify patent
    pat_res = await db.execute(select(models_b.Patent).where(models_b.Patent.faculty_email == STANDARD_EMAIL))
    pat = pat_res.scalar_one()
    assert pat.title == "Adaptive Routing in Mesh Networks"
    assert pat.file_no == "IN2025010023"


async def test_reviewer_and_historical_read_endpoints(client: AsyncClient, db: AsyncSession):
    """
    Verifies that /dashboard/faculty/{email} and /appraisal/previous-year-report
    properly apply Standard read compatibility for reviewers.
    """
    faculty_email = "rev_applicant@test.com"
    reviewer_email = "director_rev@test.com"

    await create_faculty(db, faculty_email, role="faculty", school="SoCSEA", dept="Computer Science")
    await create_faculty(db, reviewer_email, role="director", school="SoCSEA", dept="Computer Science")

    rev_headers = auth_header(reviewer_email, role="director", school="SoCSEA", dept="Computer Science")

    # Seed snapshot
    snap_payload = {
        "form_family": "standard",
        "form": {
            "journals": [
                {
                    "title": "Edge AI",
                    "journal": "IEEE Transactions",
                    "custom_fields": {
                        "impactFactor": 11.2,
                        "authorPosition": "First",
                    },
                }
            ]
        },
        "totals": {"grandTotal": 30},
    }
    snap = AppraisalSnapshot(
        faculty_email=faculty_email,
        academic_year=YEAR,
        payload=snap_payload,
    )
    decl = Declaration(
        faculty_email=faculty_email,
        academic_year=YEAR,
        status="Pending Director Review",
        grand_total=30,
    )
    db.add(snap)
    db.add(decl)
    await db.commit()

    # 1. Reviewer views faculty snapshot via /api/v1/dashboard/faculty/{email}
    dash_res = await client.get(f"/api/v1/dashboard/faculty/{faculty_email}?academic_year={YEAR}", headers=rev_headers)
    assert dash_res.status_code == 200, dash_res.text
    dash_data = dash_res.json()
    assert dash_data["payload"]["form"]["journals"][0]["impactFactor"] == 11.2

    # 2. Reviewer views previous year report via /api/v1/appraisal/previous-year-report
    prev_res = await client.get(f"/api/v1/appraisal/previous-year-report?academic_year={YEAR}&email={faculty_email}", headers=rev_headers)
    assert prev_res.status_code == 200, prev_res.text
    prev_data = prev_res.json()
    assert prev_data["payload"]["form"]["journals"][0]["impactFactor"] == 11.2


async def test_non_standard_forms_fallback_preserved(db: AsyncSession):
    """
    Verifies that Media, Design, and non-standard forms continue using the generic
    workflow without being altered by the standard compatibility adapter.
    """
    assert is_standard_form_submission(form_family="media") is False
    assert is_standard_form_submission(school="SoMCS") is False

    media_form = {
        "lectures": [{"course_code": "MED101", "score": 20}],
    }
    # Call shred_form with form_family="media"
    from src.api.v1.appraisal import shred_form
    await shred_form(db, MEDIA_EMAIL, YEAR, media_form, form_family="media")
    await db.commit()

    teach_res = await db.execute(
        select(models_a.TeachingProcess).where(
            models_a.TeachingProcess.faculty_email == MEDIA_EMAIL,
            models_a.TeachingProcess.academic_year == YEAR,
        )
    )
    row = teach_res.scalar_one()
    assert row.course_code == "MED101"
    assert row.form_family == "media"

