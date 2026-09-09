"""
Dynamic Form Registry for Faculty Appraisal System.
Defines available appraisal form variants, mappings, and validation helpers.
"""

from typing import Optional, Dict, Any, List
from fastapi import HTTPException


FORM_REGISTRY: List[Dict[str, Any]] = [
    {
        "default_form": "standard",
        "form_variant": "standard",
        "form_type": "FORM_A",
        "form_label": "Standard Appraisal",
        "active": True,
    },
    {
        "default_form": "creative",
        "form_variant": "mediaCommunication",
        "form_type": "FORM_B",
        "form_label": "Creative Appraisal - Media Communication",
        "active": True,
    },
    {
        "default_form": "creative",
        "form_variant": "designArts",
        "form_type": "FORM_C",
        "form_label": "Creative Appraisal - Design Arts",
        "active": True,
    },
]


def get_form_registry(active_only: bool = True) -> List[Dict[str, Any]]:
    """Returns the list of registered form variants."""
    if active_only:
        return [entry for entry in FORM_REGISTRY if entry.get("active", True)]
    return list(FORM_REGISTRY)


def find_registry_entry(
    default_form: Optional[str] = None,
    form_variant: Optional[str] = None,
    form_type: Optional[str] = None,
    active_only: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Finds a matching form registry entry by form_type, form_variant, or default_form.
    """
    entries = get_form_registry(active_only=active_only)

    # 1. Match by form_type if given (case-insensitive)
    if form_type:
        norm_ft = form_type.strip().upper()
        for entry in entries:
            if entry["form_type"].upper() == norm_ft:
                if not default_form or entry["default_form"].lower() == default_form.strip().lower():
                    return entry

    # 2. Match by form_variant (case-insensitive)
    if form_variant:
        norm_fv = form_variant.strip().lower()
        for entry in entries:
            if entry["form_variant"].lower() == norm_fv:
                if not default_form or entry["default_form"].lower() == default_form.strip().lower():
                    return entry

    # 3. Match by default_form if only default_form is given
    if default_form and not form_variant and not form_type:
        norm_df = default_form.strip().lower()
        for entry in entries:
            if entry["default_form"].lower() == norm_df:
                return entry

    return None


def validate_and_resolve_form_config(
    default_form: Optional[str],
    form_variant: Optional[str],
    form_type: Optional[str] = None,
    form_label: Optional[str] = None,
    existing_school: Optional[Any] = None,
) -> Dict[str, str]:
    """
    Validates and resolves school form configuration according to specification:
    - If default_form is missing and existing_school is None, default to 'standard'.
    - If form_variant is missing and default_form is 'standard', set form_variant = 'standard'.
    - If form_variant is missing and default_form is 'creative', reject with 400.
    - Do NOT silently default creative to designArts.
    - Validate form_variant / form_type against active registry entries.
    - Derive / resolve form_type and form_label from registry.
    """
    # Determine default_form
    if default_form is None:
        if existing_school is not None:
            df = getattr(existing_school, "default_form", "standard") or "standard"
        else:
            df = "standard"
    else:
        df = default_form.strip().lower()

    if df not in ("standard", "creative"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid default_form '{default_form}'. Must be 'standard' or 'creative'.",
        )

    # Determine form_variant
    if form_variant is not None and form_variant.strip():
        fv = form_variant.strip()
    elif existing_school is not None and default_form is None:
        # Only inherit form_variant if default_form was NOT explicitly changed
        fv = getattr(existing_school, "form_variant", None)
    elif existing_school is not None and default_form is not None and getattr(existing_school, "default_form", None) == df:
        # Same default_form unchanged
        fv = getattr(existing_school, "form_variant", None)
    else:
        fv = "standard" if df == "standard" else None

    # Determine form_type and form_label
    ft = form_type.strip() if form_type and form_type.strip() else None
    fl = form_label.strip() if form_label and form_label.strip() else None

    if df == "standard":
        if not fv or fv.lower() == "standard":
            return {
                "default_form": "standard",
                "form_variant": "standard",
                "form_type": ft or "FORM_A",
                "form_label": fl or "Standard Appraisal",
            }
        matched = find_registry_entry(default_form="standard", form_variant=fv, form_type=ft)
        if not matched:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid form configuration for standard appraisal: variant '{fv}' or type '{ft}' not found in active registry.",
            )
        return {
            "default_form": "standard",
            "form_variant": matched["form_variant"],
            "form_type": matched["form_type"],
            "form_label": fl or matched["form_label"],
        }

    elif df == "creative":
        if not fv or fv.lower() == "standard":
            raise HTTPException(
                status_code=400,
                detail="Creative appraisal form requires a valid 'form_variant' (e.g. 'mediaCommunication', 'designArts').",
            )
        matched = find_registry_entry(default_form="creative", form_variant=fv, form_type=ft)
        if not matched:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid form_variant '{fv}' for creative form. Must match an active registry entry (e.g. 'mediaCommunication', 'designArts').",
            )
        
        resolved_label = fl if fl and fl != "Standard Appraisal" else matched["form_label"]
        resolved_type = ft if ft and ft != "FORM_A" else matched["form_type"]

        return {
            "default_form": "creative",
            "form_variant": matched["form_variant"],
            "form_type": resolved_type,
            "form_label": resolved_label,
        }

    raise HTTPException(status_code=400, detail="Invalid form configuration.")



    raise HTTPException(status_code=400, detail="Invalid form configuration.")


def resolve_school_form_fields(school: Any) -> Dict[str, str]:
    """
    Given a School DB model or dict, safely resolves all 4 form fields with fallbacks for legacy records.
    """
    df = getattr(school, "default_form", None) or (school.get("default_form") if isinstance(school, dict) else None) or "standard"
    fv = getattr(school, "form_variant", None) or (school.get("form_variant") if isinstance(school, dict) else None)
    ft = getattr(school, "form_type", None) or (school.get("form_type") if isinstance(school, dict) else None)
    fl = getattr(school, "form_label", None) or (school.get("form_label") if isinstance(school, dict) else None)
    code = (getattr(school, "code", None) or (school.get("code") if isinstance(school, dict) else None) or "").upper()

    if not fv:
        if df == "standard":
            fv, ft, fl = "standard", "FORM_A", "Standard Appraisal"
        else:
            if code in ("SOMCS", "SOHSS"):
                fv, ft, fl = "mediaCommunication", "FORM_B", "Creative Appraisal - Media Communication"
            elif code in ("SOD", "SOAA"):
                fv, ft, fl = "designArts", "FORM_C", "Creative Appraisal - Design Arts"
            else:
                fv, ft, fl = "mediaCommunication", "FORM_B", "Creative Appraisal - Media Communication"

    if not ft or not fl or (df == "creative" and fl == "Standard Appraisal"):
        matched = find_registry_entry(default_form=df, form_variant=fv)
        if matched:
            ft = matched["form_type"] if (not ft or ft == "FORM_A") else ft
            fl = matched["form_label"] if (not fl or fl == "Standard Appraisal") else fl

    return {
        "default_form": df,
        "form_variant": fv or "standard",
        "form_type": ft or "FORM_A",
        "form_label": fl or "Standard Appraisal",
    }

