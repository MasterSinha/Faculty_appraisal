import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

PART_A_SECTION_MAX = {
    "lectures": 50,
    "courseFile": 20,
    "innovativeTeaching": 10,
    "projects": 10,
    "quals": 10,
    "feedback": 10,
    "deptActs": 20,
    "uniActs": 30,
    "society": 10,
    "industry": 5,
    "acr": 25,
}

PART_B_SECTION_MAX = {
    "journals": 120,
    "books": 50,
    "ict": 20,
    "research": 30,
    "projects2": 15,
    "externalProjects": 30,
    "patents": 40,
    "awards": 10,
    "confs": 30,
    "proposals": 10,
    "products": 10,
    "fdps": 10,
    "training": 10,
}

SECTION_ALIASES = {
    "projectsGuidance": "projects",
    "qualificationEnhancement": "quals",
    "studentFeedback": "feedback",
    "departmentalActivities": "deptActs",
    "universityActivities": "uniActs",
    "societyContribution": "society",
    "industryConnect": "industry",
    "researchGuidance": "research",
    "internalProjects": "projects2",
    "conferences": "confs",
    "fdpTraining": "fdps",
}

PREVIOUS_YEAR_SCORING_CONFIGS = {
    "standard": {
        "part_a_max": 200.0,
        "part_b_max": 375.0,
        "faculty_excluded_part_a": {"acr"},
        "part_a_sections": {
            "lectures": 50.0,
            "courseFile": 20.0,
            "innovativeTeaching": 10.0,
            "projects": 10.0,
            "quals": 10.0,
            "feedback": 10.0,
            "deptActs": 20.0,
            "uniActs": 30.0,
            "society": 10.0,
            "industry": 5.0,
            "acr": 25.0,
        },
        "part_b_sections": {
            "journals": 120.0,
            "books": 50.0,
            "ict": 20.0,
            "research": 30.0,
            "projects2": 15.0,
            "externalProjects": 30.0,
            "patents": 40.0,
            "awards": 10.0,
            "confs": 30.0,
            "proposals": 10.0,
            "products": 10.0,
            "fdps": 10.0,
            "training": 10.0,
        },
    },
    "media": {
        "part_a_max": 200.0,
        "part_b_max": 375.0,
        "faculty_excluded_part_a": set(),
        "part_a_sections": {
            "lectures": 50.0,
            "courseFile": 20.0,
            "innovativeTeaching": 10.0,
            "projects": 10.0,
            "quals": 10.0,
            "feedback": 10.0,
            "deptActs": 20.0,
            "uniActs": 30.0,
            "society": 10.0,
            "acr": 25.0,
        },
        "part_b_sections": {
            "journals": 80.0,
            "popularWritings": 40.0,
            "books": 60.0,
            "ict": 30.0,
            "research": 30.0,
            "internalProjects": 15.0,
            "externalProjects": 30.0,
            "awards": 10.0,
            "confs": 30.0,
            "proposals": 10.0,
            "products": 20.0,
            "fdps": 20.0,
            "training": 20.0,
        },
    },
    "design": {
        "part_a_max": 200.0,
        "part_b_max": 375.0,
        "faculty_excluded_part_a": set(),
        "part_a_sections": {
            "lectures": 40.0,
            "courseFile": 20.0,
            "innovativeTeaching": 10.0,
            "projects": 20.0,
            "quals": 10.0,
            "feedback": 10.0,
            "deptActs": 20.0,
            "uniActs": 30.0,
            "society": 10.0,
            "industry": 5.0,
            "acr": 25.0,
        },
        "part_b_sections": {
            "journals": 80.0,
            "books": 60.0,
            "ict": 50.0,
            "research": 30.0,
            "internalProjects": 15.0,
            "externalProjects": 30.0,
            "ipr": 40.0,
            "awards": 10.0,
            "confs": 30.0,
            "proposals": 10.0,
            "fdps": 20.0,
            "training": 20.0,
        },
    },
}


def compute_effective_max(
    section_scores: Optional[Dict[str, Any]],
    section_applicability: Optional[Dict[str, Any]],
    mode: str
) -> Dict[str, float]:
    """
    Computes effective max marks for Part A, Part B, and Total.
    mode can be "self" (excludes ACR) or "reviewer" (includes ACR).
    Reduces max marks for sections marked "notApplicable" in section_applicability.
    """
    # Normalize applicability dict
    app = {}
    if isinstance(section_applicability, dict):
        for k, v in section_applicability.items():
            normalized_key = SECTION_ALIASES.get(k, k)
            app[normalized_key] = v

    # Also check if sectionApplicability is nested inside section_scores
    if isinstance(section_scores, dict) and "sectionApplicability" in section_scores:
        nested_app = section_scores["sectionApplicability"]
        if isinstance(nested_app, dict):
            for k, v in nested_app.items():
                normalized_key = SECTION_ALIASES.get(k, k)
                app[normalized_key] = v

    part_a_max = 0.0
    for sec, max_val in PART_A_SECTION_MAX.items():
        if mode == "self" and sec == "acr":
            continue
        if app.get(sec) == "notApplicable":
            continue
        part_a_max += max_val

    part_b_max = 0.0
    for sec, max_val in PART_B_SECTION_MAX.items():
        if app.get(sec) == "notApplicable":
            continue
        part_b_max += max_val

    return {
        "part_a_max": part_a_max,
        "part_b_max": part_b_max,
        "total_max": part_a_max + part_b_max,
    }

def _normalize_applicability(app_dict: Any) -> dict:
    if not isinstance(app_dict, dict):
        return {}
    normalized = {}
    for k, v in app_dict.items():
        nk = SECTION_ALIASES.get(k, k)
        normalized[nk] = v
    return normalized

async def generate_scoring_metadata(
    faculty: Any,
    snapshot: Any,
    reviews: list,
    declaration: Any,
    db: AsyncSession
) -> dict:
    """
    Generates score_summary and score_source metadata dictionaries for the frontend.
    Handles engineering vs creative schools and derives max scores based on applicability.
    """
    ay = getattr(declaration, "academic_year", None) or (snapshot.academic_year if snapshot and hasattr(snapshot, "academic_year") else None) or "2025-2026"
    has_c_d = (ay >= "2025-2026")

    from src.setup.dependencies import normalize_school, get_form_family
    school_norm = normalize_school(getattr(faculty, "school", ""))
    family = get_form_family(school_norm)
    config = PREVIOUS_YEAR_SCORING_CONFIGS.get(family, PREVIOUS_YEAR_SCORING_CONFIGS["standard"])

    # Extract snapshot payload and applicability
    def _extract_app(snap):
        if not snap or not hasattr(snap, "payload") or not isinstance(snap.payload, dict):
            return {}
        payload = snap.payload
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

    self_app = _extract_app(snapshot)
    self_app_norm = _normalize_applicability(self_app)

    roles = ["faculty", "hod", "director", "dean", "vc"]
    summary = {}
    source = {}

    # Find review chain to determine active/past reviewers
    chain = []
    if faculty:
        from src.api.v1.remarks import get_review_chain
        try:
            ay = getattr(declaration, "academic_year", None) or getattr(snapshot, "academic_year", "2025-2026")
            chain = await get_review_chain(faculty, db, ay)
        except Exception:
            chain = []

    # Map 'center_head' -> 'hod' in chain keys
    chain_keys = []
    for r in chain:
        rk = "hod" if r in ("hod", "center_head") else r
        if rk not in chain_keys:
            chain_keys.append(rk)

    # Determine current active role from declaration status
    active_role = None
    if declaration:
        s = (getattr(declaration, "status", "") or "").strip().lower().replace("_", " ")
        if "vc" in s or "vice chancellor" in s or "vice_chancellor" in s or "dean reviewed" in s or s == "pending vc":
            active_role = "vc"
        elif "dean" in s or "director reviewed" in s or s == "pending dean":
            active_role = "dean"
        elif "director" in s or "hod reviewed" in s or s == "pending director":
            active_role = "director"
        elif "hod" in s or "center head" in s or "center_head" in s or s == "pending hod" or s == "pending center head":
            active_role = "hod"
        elif s in ("reviewed", "finalised", "completed", "done", "vc approved", "vc_approved"):
            active_role = "vc"

    for role in roles:
        part_a_score = None
        part_b_score = None

        if role == "faculty":
            if declaration:
                part_a_score = float(declaration.part_a_total) if declaration.part_a_total is not None else 0.0
                part_b_score = float(declaration.part_b_total) if declaration.part_b_total is not None else 0.0
            else:
                payload = snapshot.payload if snapshot and hasattr(snapshot, "payload") and isinstance(snapshot.payload, dict) else {}
                totals = payload.get("totals") or {}
                part_a_score = totals.get("partA") or totals.get("part_a_total") or totals.get("part_a_score") or totals.get("part_a_score_total") or totals.get("effectivePartATotal")
                part_b_score = totals.get("partB") or totals.get("part_b_total") or totals.get("part_b_score") or totals.get("part_b_score_total") or totals.get("effectivePartBTotal")
                part_a_score = float(part_a_score) if part_a_score is not None else None
                part_b_score = float(part_b_score) if part_b_score is not None else None
        else:
            matching_review = None
            for r in reviews:
                r_role = getattr(r, "reviewer_role", "").strip().lower()
                if role == "hod" and r_role in ("hod", "center_head"):
                    matching_review = r
                    break
                elif r_role == role:
                    matching_review = r
                    break

            if matching_review:
                part_a_score = float(matching_review.part_a_score) if matching_review.part_a_score is not None else 0.0
                part_b_score = float(matching_review.part_b_score) if matching_review.part_b_score is not None else 0.0

            # If no review and not active/past role, return empty dict
            has_review = (matching_review is not None)
            is_active_or_past = False
            if active_role in chain_keys and role in chain_keys:
                idx_active = chain_keys.index(active_role)
                idx_role = chain_keys.index(role)
                if idx_role <= idx_active:
                    is_active_or_past = True
            elif active_role is None and role == "hod":
                is_active_or_past = True

            if not has_review and not is_active_or_past:
                summary[role] = {}
                source[role] = {}
                continue

        # Check if explicit historical max values exist in snapshot
        payload = (
            snapshot.payload
            if snapshot and hasattr(snapshot, "payload") and isinstance(snapshot.payload, dict)
            else {}
        )
        totals = payload.get("totals") or {}
        score_sum = payload.get("score_summary") or {}
        role_sum = score_sum.get(role) or {} if isinstance(score_sum, dict) else {}

        hist_a = None
        if isinstance(role_sum, dict):
            hist_a = role_sum.get("partAMax") or role_sum.get("part_a_max")
        if hist_a is None and role == "faculty":
            hist_a = totals.get("effective_part_a_max") or totals.get("effectivePartAMax")

        hist_b = None
        if isinstance(role_sum, dict):
            hist_b = role_sum.get("partBMax") or role_sum.get("part_b_max")
        if hist_b is None and role == "faculty":
            hist_b = totals.get("effective_part_b_max") or totals.get("effectivePartBMax")

        # Part A Max Calculation
        if hist_a is not None:
            part_a_max = float(hist_a)
            part_a_max_src = "historical_totals"
        else:
            # Derive Part A max
            part_a_max = config["part_a_max"]
            excluded = config["faculty_excluded_part_a"] if role == "faculty" else set()

            # 1. Get applicability
            if role == "faculty":
                app_norm = self_app_norm
            else:
                # Reviewer
                matching_review = None
                for r in reviews:
                    r_role = getattr(r, "reviewer_role", "").strip().lower()
                    if role == "hod" and r_role in ("hod", "center_head"):
                        matching_review = r
                        break
                    elif r_role == role:
                        matching_review = r
                        break

                reviewer_app = {}
                if matching_review and getattr(matching_review, "section_scores", None):
                    s_scores = matching_review.section_scores
                    if isinstance(s_scores, dict) and "sectionApplicability" in s_scores:
                        reviewer_app = s_scores["sectionApplicability"]

                app = reviewer_app if reviewer_app else self_app
                app_norm = _normalize_applicability(app)

            # 2. Subtract excluded sections
            for sec in excluded:
                part_a_max -= config["part_a_sections"].get(sec, 0.0)

            # 3. Subtract notApplicable sections
            for sec, max_val in config["part_a_sections"].items():
                if sec in excluded:
                    continue
                if app_norm.get(sec) == "notApplicable":
                    part_a_max -= max_val

            part_a_max_src = "derived_from_applicability"

        # Part B Max Calculation
        if hist_b is not None:
            part_b_max = float(hist_b)
            part_b_max_src = "historical_totals"
        else:
            # Derive Part B max
            part_b_max = config["part_b_max"]

            # 1. Get applicability (re-use app_norm computed for Part A)
            if role == "faculty":
                app_norm = self_app_norm
            else:
                matching_review = None
                for r in reviews:
                    r_role = getattr(r, "reviewer_role", "").strip().lower()
                    if role == "hod" and r_role in ("hod", "center_head"):
                        matching_review = r
                        break
                    elif r_role == role:
                        matching_review = r
                        break

                reviewer_app = {}
                if matching_review and getattr(matching_review, "section_scores", None):
                    s_scores = matching_review.section_scores
                    if isinstance(s_scores, dict) and "sectionApplicability" in s_scores:
                        reviewer_app = s_scores["sectionApplicability"]

                app = reviewer_app if reviewer_app else self_app
                app_norm = _normalize_applicability(app)

            # 2. Apply combined B8 rules for media/design, or individual rules for standard
            if family in ("media", "design"):
                for sec, max_val in config["part_b_sections"].items():
                    if sec in ("fdps", "training"):
                        continue
                    if app_norm.get(sec) == "notApplicable":
                        part_b_max -= max_val
                if app_norm.get("fdps") == "notApplicable" and app_norm.get("training") == "notApplicable":
                    part_b_max -= 20.0
            else:
                for sec, max_val in config["part_b_sections"].items():
                    if app_norm.get(sec) == "notApplicable":
                        part_b_max -= max_val

            part_b_max_src = "derived_from_applicability"

        # Get Part C and D scores
        part_c_score = 0.0
        part_d_score = 0.0
        part_c_max = 150.0 if has_c_d else 0.0
        part_d_max = 50.0 if has_c_d else 0.0

        if role == "faculty":
            if declaration:
                part_c_score = float(declaration.part_c_total) if declaration.part_c_total is not None else 0.0
                part_d_score = float(declaration.part_d_total) if declaration.part_d_total is not None else 0.0
            else:
                part_c_score = float(totals.get("partC") or totals.get("part_c_total") or totals.get("partCTotal") or 0.0)
                part_d_score = float(totals.get("partD") or totals.get("part_d_total") or totals.get("partDTotal") or 0.0)
        else:
            if matching_review:
                part_c_score = float(matching_review.part_c_score) if matching_review.part_c_score is not None else 0.0
                part_d_score = float(matching_review.part_d_score) if matching_review.part_d_score is not None else 0.0

        grand = None
        if part_a_score is not None and part_b_score is not None:
            grand = part_a_score + part_b_score
            if has_c_d:
                grand += part_c_score + part_d_score

        grand_max = part_a_max + part_b_max + part_c_max + part_d_max
        percentage = None
        if grand is not None and grand_max > 0:
            percentage = round((grand / grand_max) * 100, 2)

        summary[role] = {
            "partA": part_a_score,
            "partB": part_b_score,
            "partC": part_c_score if has_c_d else None,
            "partD": part_d_score if has_c_d else None,
            "grand": grand,
            "partAMax": part_a_max,
            "partBMax": part_b_max,
            "partCMax": part_c_max if has_c_d else None,
            "partDMax": part_d_max if has_c_d else None,
            "grandMax": grand_max,
            "percentage": percentage
        }

        source[role] = {
            "partAMaxSource": part_a_max_src,
            "partBMaxSource": part_b_max_src,
            "grandMaxSource": "partA_plus_partB" if not has_c_d else "partA_plus_partB_plus_partC_plus_partD"
        }

    return {
        "score_summary": summary,
        "score_source": source,
        "raw_applicability": self_app,
        "applicability": self_app
    }

