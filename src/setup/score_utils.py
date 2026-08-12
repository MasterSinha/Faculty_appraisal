import logging
from typing import Dict, Any, Optional

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

def generate_scoring_metadata(
    faculty: Any,
    snapshot: Any,
    reviews: list,
    declaration: Any
) -> dict:
    """
    Generates score_summary and score_source metadata dictionaries for the frontend.
    Handles engineering vs creative schools and derives max scores based on applicability.
    """
    from src.setup.dependencies import normalize_school, NON_ENGINEERING_SCHOOLS
    school_norm = normalize_school(getattr(faculty, "school", ""))
    is_creative = school_norm in NON_ENGINEERING_SCHOOLS

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
            chain = get_review_chain(faculty)
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

        # Calculate max marks
        part_a_max = 0.0
        part_b_max = 0.0
        part_a_max_src = "derived_from_applicability"
        part_b_max_src = "derived_from_applicability"

        if is_creative:
            part_a_max = 150.0
            part_b_max = 350.0
            part_a_max_src = "school_defaults"
            part_b_max_src = "school_defaults"
        else:
            if role == "faculty":
                payload = snapshot.payload if snapshot and hasattr(snapshot, "payload") and isinstance(snapshot.payload, dict) else {}
                totals = payload.get("totals") or {}
                hist_a = totals.get("effective_part_a_max") or totals.get("effectivePartAMax")
                hist_b = totals.get("effective_part_b_max") or totals.get("effectivePartBMax")

                if hist_a is not None:
                    part_a_max = float(hist_a)
                    part_a_max_src = "historical_totals"
                else:
                    part_a_max = 200.0 - 25.0  # Exclude ACR
                    for sec, max_val in PART_A_SECTION_MAX.items():
                        if sec == "acr":
                            continue
                        if self_app_norm.get(sec) == "notApplicable":
                            part_a_max -= max_val

                if hist_b is not None:
                    part_b_max = float(hist_b)
                    part_b_max_src = "historical_totals"
                else:
                    part_b_max = 375.0
                    for sec, max_val in PART_B_SECTION_MAX.items():
                        if self_app_norm.get(sec) == "notApplicable":
                            part_b_max -= max_val
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

                part_a_max = 200.0
                for sec, max_val in PART_A_SECTION_MAX.items():
                    if app_norm.get(sec) == "notApplicable":
                        part_a_max -= max_val

                part_b_max = 375.0
                for sec, max_val in PART_B_SECTION_MAX.items():
                    if app_norm.get(sec) == "notApplicable":
                        part_b_max -= max_val

        grand = None
        if part_a_score is not None and part_b_score is not None:
            grand = part_a_score + part_b_score

        grand_max = part_a_max + part_b_max
        percentage = None
        if grand is not None and grand_max > 0:
            percentage = round((grand / grand_max) * 100, 2)

        summary[role] = {
            "partA": part_a_score,
            "partB": part_b_score,
            "grand": grand,
            "partAMax": part_a_max,
            "partBMax": part_b_max,
            "grandMax": grand_max,
            "percentage": percentage
        }

        source[role] = {
            "partAMaxSource": part_a_max_src,
            "partBMaxSource": part_b_max_src,
            "grandMaxSource": "partA_plus_partB"
        }

    return {
        "score_summary": summary,
        "score_source": source,
        "raw_applicability": self_app
    }
