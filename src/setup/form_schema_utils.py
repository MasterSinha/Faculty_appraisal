"""
Form Schema Utilities for Dynamic Appraisal Form Builder.
Handles normalization, column maximums validation, field key locking,
part sequencing, and active filtering according to specifications.
"""

import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import HTTPException


NUMERIC_COLUMN_TYPES = frozenset({
    "number", "integer", "int", "numeric", "decimal", "float"
})


def slugify_key(text: Optional[str]) -> str:
    """
    Converts a label into a clean, stable snake_case wire key.
    E.g. 'Publication Title' -> 'publication_title'
    """
    if not text:
        return "field"
    # Replace non-alphanumeric chars (except underscore and dash) with space
    s = re.sub(r'[^\w\s-]', '', str(text)).strip().lower()
    s = re.sub(r'[-\s]+', '_', s)
    s = s.strip('_')
    return s or "field"


def normalize_column_schema(col: Any, strict: bool = False) -> Dict[str, Any]:
    """
    Normalizes a single column schema object for table fields.
    Rules:
    - Max marks is visible/valid only for numeric ('number' and 'integer') columns.
    - A blank/missing maximum is stored as None/null, not zero.
    - Explicit zero (0 or 0.0) is preserved.
    - A supplied numeric maximum must be finite and non-negative (>= 0).
    - Changing a numeric column to non-numeric clears its maximum to None.
    - Tolerates stale non-numeric maximums in legacy schemas without rejecting the form.
    - Maps both maxMarks and max_marks so neither is lost across the API boundary.
    """
    if not isinstance(col, dict):
        return {"name": str(col), "type": "text", "maxMarks": None, "max_marks": None}

    col_dict = dict(col)
    col_name = str(col_dict.get("name", "")).strip()
    col_type = str(col_dict.get("type", "text")).strip().lower()
    col_dict["name"] = col_name
    col_dict["type"] = col_type

    is_numeric = col_type in NUMERIC_COLUMN_TYPES

    # Extract maxMarks / max_marks
    raw_max = col_dict.get("maxMarks") if "maxMarks" in col_dict else col_dict.get("max_marks")

    if not is_numeric:
        # Non-numeric columns MUST have null maximum
        col_dict["maxMarks"] = None
        col_dict["max_marks"] = None
    else:
        if raw_max is None or (isinstance(raw_max, str) and raw_max.strip() == ""):
            col_dict["maxMarks"] = None
            col_dict["max_marks"] = None
        else:
            try:
                num_val = float(raw_max)
                if math.isnan(num_val) or math.isinf(num_val):
                    if strict:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Column '{col_name}' max marks must be a finite number."
                        )
                    col_dict["maxMarks"] = None
                    col_dict["max_marks"] = None
                elif num_val < 0:
                    if strict:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Column '{col_name}' max marks must be a non-negative number."
                        )
                    col_dict["maxMarks"] = None
                    col_dict["max_marks"] = None
                else:
                    # Integer columns with whole number values format cleanly
                    if col_type in ("integer", "int") and num_val.is_integer():
                        final_val = int(num_val)
                    else:
                        final_val = int(num_val) if num_val.is_integer() else num_val
                    col_dict["maxMarks"] = final_val
                    col_dict["max_marks"] = final_val
            except (ValueError, TypeError):
                if strict:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Column '{col_name}' max marks must be numeric, got '{raw_max}'."
                    )
                # Tolerate legacy non-numeric values by normalizing to None
                col_dict["maxMarks"] = None
                col_dict["max_marks"] = None

    return col_dict


def normalize_field_schema(
    field: Any,
    existing_field: Optional[Dict[str, Any]] = None,
    strict: bool = False
) -> Dict[str, Any]:
    """
    Normalizes a single field schema object.
    Ensures stable key derivation, column normalization, and dual-casing support.
    """
    if isinstance(field, str):
        key = slugify_key(field)
        return {
            "id": key,
            "key": key,
            "label": field,
            "type": "text",
            "required": False,
            "isCustom": False,
            "is_custom": False,
            "active": True,
        }

    if not isinstance(field, dict):
        return {}

    f = dict(field)

    # Resolve ID
    field_id = f.get("id") or (existing_field.get("id") if existing_field else None)
    if not field_id:
        field_id = f.get("key") or slugify_key(f.get("label", "field"))

    # Resolve stable wire key
    wire_key = f.get("key") or (existing_field.get("key") if existing_field else None) or f.get("id")
    if not wire_key:
        wire_key = slugify_key(f.get("label", "field"))

    f["id"] = field_id
    f["key"] = wire_key
    f["label"] = str(f.get("label", wire_key))
    f["type"] = str(f.get("type", "text")).strip()
    f["required"] = bool(f.get("required", False))

    # isCustom / is_custom
    is_custom = f.get("isCustom") if "isCustom" in f else f.get("is_custom")
    if is_custom is None:
        is_custom = existing_field.get("isCustom", existing_field.get("is_custom", True)) if existing_field else True
    f["isCustom"] = bool(is_custom)
    f["is_custom"] = bool(is_custom)

    # active
    active = f.get("active")
    if active is None:
        active = existing_field.get("active", True) if existing_field else True
    f["active"] = bool(active)

    # Options for dropdown / select / yesNo / conditionalText
    if "options" in f and f["options"] is not None:
        if isinstance(f["options"], list):
            f["options"] = [str(o).strip() for o in f["options"] if str(o).strip()]
        elif isinstance(f["options"], str):
            f["options"] = [o.strip() for o in f["options"].split(",") if o.strip()]

    # Conditional text properties
    if "triggerValue" in f or "trigger_value" in f:
        tv = f.get("triggerValue") if "triggerValue" in f else f.get("trigger_value")
        f["triggerValue"] = tv
        f["trigger_value"] = tv

    if "extraLabel" in f or "extra_label" in f:
        el = f.get("extraLabel") if "extraLabel" in f else f.get("extra_label")
        f["extraLabel"] = el
        f["extra_label"] = el

    # rowMax / row_max
    row_max = f.get("rowMax") if "rowMax" in f else f.get("row_max")
    if row_max is not None and row_max != "":
        try:
            r_val = float(row_max)
            f["rowMax"] = int(r_val) if r_val.is_integer() else r_val
            f["row_max"] = f["rowMax"]
        except (ValueError, TypeError):
            f["rowMax"] = None
            f["row_max"] = None
    else:
        f["rowMax"] = None
        f["row_max"] = None

    # Table-level properties
    if f["type"] == "table":
        # autoSerial / auto_serial
        auto_serial = f.get("autoSerial") if "autoSerial" in f else f.get("auto_serial")
        f["autoSerial"] = bool(auto_serial) if auto_serial is not None else True
        f["auto_serial"] = f["autoSerial"]

        # Table-level maxMarks / max_marks
        tbl_max = f.get("maxMarks") if "maxMarks" in f else f.get("max_marks")
        if tbl_max is not None and tbl_max != "":
            try:
                t_val = float(tbl_max)
                f["maxMarks"] = int(t_val) if t_val.is_integer() else t_val
                f["max_marks"] = f["maxMarks"]
            except (ValueError, TypeError):
                f["maxMarks"] = None
                f["max_marks"] = None
        else:
            f["maxMarks"] = None
            f["max_marks"] = None

        # Columns
        raw_columns = f.get("columns", [])
        if isinstance(raw_columns, list):
            f["columns"] = [normalize_column_schema(col, strict=strict) for col in raw_columns]
        else:
            f["columns"] = []

    return f


def validate_and_normalize_fields(
    existing_fields_raw: List[Any],
    updated_fields_raw: List[Any],
    strict: bool = True
) -> List[Dict[str, Any]]:
    """
    Validates field updates and ensures:
    1. Field 'key' is locked after first save (§4). Any attempt to rename an existing field's key is rejected with 400.
    2. Core fields (isCustom: False) cannot be deleted; missing core fields are preserved with active=False (§3).
    3. All column properties are normalized and validated.
    4. Render order in the returned array reflects the updated array order.
    """
    # Build lookup of existing fields
    existing_by_id: Dict[str, Dict[str, Any]] = {}
    existing_by_key: Dict[str, Dict[str, Any]] = {}
    existing_core_keys: Set[str] = set()

    for item in existing_fields_raw or []:
        norm_item = normalize_field_schema(item, strict=False)
        fid = str(norm_item.get("id") or norm_item.get("key"))
        fkey = str(norm_item.get("key") or norm_item.get("id"))
        existing_by_id[fid] = norm_item
        existing_by_key[fkey] = norm_item
        if not norm_item.get("isCustom", True):
            existing_core_keys.add(fkey)

    normalized_updated: List[Dict[str, Any]] = []
    seen_keys: Set[str] = set()

    for incoming in updated_fields_raw:
        incoming_dict = dict(incoming) if isinstance(incoming, dict) else {"label": str(incoming)}
        incoming_id = str(incoming_dict.get("id") or "")
        incoming_key = str(incoming_dict.get("key") or "")

        # Find existing field match
        matched_existing: Optional[Dict[str, Any]] = None
        if incoming_id and incoming_id in existing_by_id:
            matched_existing = existing_by_id[incoming_id]
        elif incoming_key and incoming_key in existing_by_key:
            matched_existing = existing_by_key[incoming_key]

        # Key-locking check (§4):
        # If an existing field had a saved key, the incoming payload cannot change it.
        if matched_existing and strict:
            saved_key = matched_existing.get("key")
            if incoming_key and saved_key and incoming_key != saved_key:
                raise HTTPException(
                    status_code=400,
                    detail=f"Field key '{saved_key}' is locked and cannot be renamed to '{incoming_key}'."
                )

        norm_field = normalize_field_schema(incoming_dict, existing_field=matched_existing, strict=strict)
        key = norm_field["key"]

        # Duplicate key check within the same section
        if key in seen_keys:
            if strict:
                raise HTTPException(
                    status_code=400,
                    detail=f"Duplicate field key '{key}' in section."
                )
            # Make unique if non-strict
            idx = 1
            while f"{key}_{idx}" in seen_keys:
                idx += 1
            norm_field["key"] = f"{key}_{idx}"
            norm_field["id"] = norm_field["key"]

        seen_keys.add(norm_field["key"])
        normalized_updated.append(norm_field)

    # Core field preservation (§3):
    # Core fields cannot be deleted; if not in the updated array, keep them as active = False.
    for core_key in existing_core_keys:
        if core_key not in seen_keys:
            retired_core = dict(existing_by_key[core_key])
            retired_core["active"] = False
            normalized_updated.append(retired_core)
            seen_keys.add(core_key)

    return normalized_updated


def sort_sections_with_table_order(
    sections: List[Any],
    table_order: Optional[List[str]] = None
) -> List[Any]:
    """
    Sorts a list of sections or fields using an optional tableOrder array.
    Missing IDs follow explicitly ordered IDs in stable existing order (§1).
    """
    if not table_order:
        return list(sections)

    order_map = {item_id: idx for idx, item_id in enumerate(table_order)}
    n_ordered = len(table_order)

    def get_sort_key(sec_idx_tuple: Tuple[int, Any]) -> Tuple[int, int]:
        orig_idx, sec = sec_idx_tuple
        code = getattr(sec, "code", None) or (sec.get("code") if isinstance(sec, dict) else None)
        sec_id = getattr(sec, "id", None) or (sec.get("id") if isinstance(sec, dict) else None) or code
        
        if code in order_map:
            return (0, order_map[code])
        if sec_id in order_map:
            return (0, order_map[sec_id])
        return (1, orig_idx)

    indexed = list(enumerate(sections))
    indexed.sort(key=get_sort_key)
    return [item for _, item in indexed]


def filter_active_form_schema(
    sections: List[Any],
    table_order: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Applies server-side active filtering for faculty and reviewer read paths (§5):
    - Returns only sections where active == True.
    - Within each section, returns only fields where active != False.
    - Preserves column orders and configured numeric maximums.
    - Orders sections preserving parts sequence and tableOrder.
    """
    sorted_sections = sort_sections_with_table_order(sections, table_order)
    active_result: List[Dict[str, Any]] = []

    for sec in sorted_sections:
        is_active = getattr(sec, "active", True) if hasattr(sec, "active") else sec.get("active", True)
        if not is_active:
            continue

        sec_dict: Dict[str, Any] = {}
        for col in ("code", "form_family", "part", "section_key", "title", "max_marks", "storage_table", "order"):
            sec_dict[col] = getattr(sec, col, None) if hasattr(sec, col) else sec.get(col)

        sec_dict["maxMarks"] = sec_dict["max_marks"]
        sec_dict["active"] = True

        raw_fields = getattr(sec, "fields", []) if hasattr(sec, "fields") else sec.get("fields", [])
        filtered_fields: List[Dict[str, Any]] = []

        for f in raw_fields:
            norm_f = normalize_field_schema(f, strict=False)
            if norm_f.get("active", True):
                filtered_fields.append(norm_f)

        sec_dict["fields"] = filtered_fields
        active_result.append(sec_dict)

    return active_result
