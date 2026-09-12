"""
Dynamic Form Registry for Faculty Appraisal System.
Defines available appraisal form variants, mappings, and validation helpers.
Supports both system built-in form families and dynamic form builder families.
"""

from typing import Optional, Dict, Any, List, Set
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func


FORM_REGISTRY: List[Dict[str, Any]] = [
    {
        "default_form": "standard",
        "form_variant": "standard",
        "form_type": "FORM_A",
        "form_label": "Standard Appraisal",
        "active": True,
        "is_system": True,
    },
    {
        "default_form": "creative",
        "form_variant": "mediaCommunication",
        "form_type": "FORM_B",
        "form_label": "Creative Appraisal - Media Communication",
        "active": True,
        "is_system": True,
    },
    {
        "default_form": "creative",
        "form_variant": "designArts",
        "form_type": "FORM_C",
        "form_label": "Creative Appraisal - Design Arts",
        "active": True,
        "is_system": True,
    },
]

# System family canonical keys
SYSTEM_FORM_FAMILIES = frozenset({
    "standard", "creative", "media", "mediacommunication", "design", "designarts",
    "all_teaching", "standard_design", "media_design"
})


def get_form_registry(
    active_only: bool = True,
    custom_families: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Returns the list of registered form variants, augmenting with any custom form families.
    """
    entries = [dict(e) for e in FORM_REGISTRY if not active_only or e.get("active", True)]

    if custom_families:
        existing_variants = {e["form_variant"].lower() for e in entries}
        existing_defaults = {e["default_form"].lower() for e in entries}

        for fam in custom_families:
            if not fam or not str(fam).strip():
                continue
            fam_clean = str(fam).strip()
            fam_norm = fam_clean.lower()

            if fam_norm in existing_variants or fam_norm in existing_defaults or fam_norm in SYSTEM_FORM_FAMILIES:
                continue

            # Format human label and type
            label = f"{fam_clean.replace('_', ' ').replace('-', ' ').title()} Appraisal"
            ftype = f"FORM_{fam_clean.upper().replace('-', '_')}"

            dynamic_entry = {
                "default_form": fam_clean,
                "form_variant": fam_clean,
                "form_type": ftype,
                "form_label": label,
                "active": True,
                "is_system": False,
            }
            entries.append(dynamic_entry)
            existing_variants.add(fam_norm)

    return entries


async def get_dynamic_form_registry(
    db: AsyncSession,
    active_only: bool = True,
) -> List[Dict[str, Any]]:
    """
    Asynchronously queries FormSectionDefinition in DB to discover all active form families,
    returning the complete augmented form registry.
    """
    from src.models.core import FormSectionDefinition

    query = select(FormSectionDefinition.form_family).distinct()
    if active_only:
        query = query.where(FormSectionDefinition.active == True)
    
    res = await db.execute(query)
    db_families = [row[0] for row in res.all() if row[0]]

    return get_form_registry(active_only=active_only, custom_families=db_families)


def find_registry_entry(
    default_form: Optional[str] = None,
    form_variant: Optional[str] = None,
    form_type: Optional[str] = None,
    active_only: bool = True,
    custom_families: Optional[List[str]] = None,
    entries: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Finds a matching form registry entry by form_type, form_variant, or default_form.
    """
    all_entries = entries if entries is not None else get_form_registry(active_only=active_only, custom_families=custom_families)

    # 1. Match by form_type if given (case-insensitive)
    if form_type:
        norm_ft = form_type.strip().upper()
        for entry in all_entries:
            if entry["form_type"].upper() == norm_ft:
                if not default_form or entry["default_form"].lower() == default_form.strip().lower():
                    return entry

    # 2. Match by form_variant (case-insensitive)
    if form_variant:
        norm_fv = form_variant.strip().lower()
        for entry in all_entries:
            if entry["form_variant"].lower() == norm_fv:
                if not default_form or entry["default_form"].lower() == default_form.strip().lower():
                    return entry

    # 3. Match by default_form if only default_form is given
    if default_form and not form_variant and not form_type:
        norm_df = default_form.strip().lower()
        for entry in all_entries:
            if entry["default_form"].lower() == norm_df:
                return entry

    return None


def validate_and_resolve_form_config(
    default_form: Optional[str],
    form_variant: Optional[str],
    form_type: Optional[str] = None,
    form_label: Optional[str] = None,
    existing_school: Optional[Any] = None,
    custom_families: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Validates and resolves school form configuration according to specification:
    - If default_form is missing and existing_school is None, default to 'standard'.
    - If form_variant is missing and default_form is 'standard', set form_variant = 'standard'.
    - If form_variant is missing and default_form is 'creative', reject with 400.
    - Supports custom form families registered in form_section_definitions.
    - Validate form_variant / form_type against registry entries.
    - Derive / resolve form_type and form_label from registry.
    """
    entries = get_form_registry(active_only=True, custom_families=custom_families)
    known_custom = {f.lower() for f in (custom_families or [])}

    # Determine default_form
    if default_form is None:
        if existing_school is not None:
            df = getattr(existing_school, "default_form", "standard") or "standard"
        else:
            df = "standard"
    else:
        df = default_form.strip()

    df_norm = df.lower()

    # Built-in or custom family check
    is_builtin_df = df_norm in ("standard", "creative")
    is_custom_df = df_norm in known_custom or any(e["default_form"].lower() == df_norm for e in entries)

    if not is_builtin_df and not is_custom_df:
        if custom_families is not None:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid default_form '{default_form}'. Must be 'standard', 'creative', or a valid active form family.",
            )
        # If custom_families wasn't queried from DB, allow single-word alphanumeric identifiers as custom family
        if not df.replace("_", "").replace("-", "").isalnum():
            raise HTTPException(
                status_code=400,
                detail=f"Invalid default_form '{default_form}'.",
            )

    # Determine form_variant
    if form_variant is not None and form_variant.strip():
        fv = form_variant.strip()
    elif existing_school is not None and default_form is None:
        fv = getattr(existing_school, "form_variant", None)
    elif existing_school is not None and default_form is not None and getattr(existing_school, "default_form", None) == df:
        fv = getattr(existing_school, "form_variant", None)
    else:
        fv = "standard" if df_norm == "standard" else (df if not is_builtin_df else None)

    # Determine form_type and form_label
    ft = form_type.strip() if form_type and form_type.strip() else None
    fl = form_label.strip() if form_label and form_label.strip() else None

    if df_norm == "standard":
        if not fv or fv.lower() == "standard":
            return {
                "default_form": "standard",
                "form_variant": "standard",
                "form_type": ft or "FORM_A",
                "form_label": fl or "Standard Appraisal",
            }
        matched = find_registry_entry(default_form="standard", form_variant=fv, form_type=ft, entries=entries)
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

    elif df_norm == "creative":
        if not fv or fv.lower() == "standard":
            raise HTTPException(
                status_code=400,
                detail="Creative appraisal form requires a valid 'form_variant' (e.g. 'mediaCommunication', 'designArts').",
            )
        matched = find_registry_entry(default_form="creative", form_variant=fv, form_type=ft, entries=entries)
        if not matched:
            # Check if variant is a known custom family
            if fv.lower() in known_custom:
                return {
                    "default_form": "creative",
                    "form_variant": fv,
                    "form_type": ft or f"FORM_{fv.upper().replace('-', '_')}",
                    "form_label": fl or f"{fv.replace('_', ' ').title()} Appraisal",
                }
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

    else:
        # Dynamic / custom form family
        matched = find_registry_entry(default_form=df, form_variant=fv, form_type=ft, entries=entries)
        if matched:
            return {
                "default_form": matched["default_form"],
                "form_variant": matched["form_variant"],
                "form_type": ft or matched["form_type"],
                "form_label": fl or matched["form_label"],
            }
        
        resolved_variant = fv or df
        resolved_type = ft or f"FORM_{df.upper().replace('-', '_')}"
        resolved_label = fl or f"{df.replace('_', ' ').replace('-', ' ').title()} Appraisal"

        return {
            "default_form": df,
            "form_variant": resolved_variant,
            "form_type": resolved_type,
            "form_label": resolved_label,
        }


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
        elif df == "creative":
            if code in ("SOMCS", "SOHSS"):
                fv, ft, fl = "mediaCommunication", "FORM_B", "Creative Appraisal - Media Communication"
            elif code in ("SOD", "SOAA"):
                fv, ft, fl = "designArts", "FORM_C", "Creative Appraisal - Design Arts"
            else:
                fv, ft, fl = "mediaCommunication", "FORM_B", "Creative Appraisal - Media Communication"
        else:
            fv = df
            ft = f"FORM_{df.upper().replace('-', '_')}"
            fl = f"{df.replace('_', ' ').replace('-', ' ').title()} Appraisal"

    if not ft or not fl or (df == "creative" and fl == "Standard Appraisal"):
        matched = find_registry_entry(default_form=df, form_variant=fv)
        if matched:
            ft = matched["form_type"] if (not ft or ft == "FORM_A") else ft
            fl = matched["form_label"] if (not fl or fl == "Standard Appraisal") else fl
        else:
            ft = ft or f"FORM_{df.upper().replace('-', '_')}"
            fl = fl or f"{df.replace('_', ' ').replace('-', ' ').title()} Appraisal"

    return {
        "default_form": df,
        "form_variant": fv or "standard",
        "form_type": ft or "FORM_A",
        "form_label": fl or "Standard Appraisal",
    }


