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
