"""
Pydantic Schemas for Form Builder Endpoints.
"""

from pydantic import BaseModel, ConfigDict, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from src.setup.form_schema_utils import (
    normalize_column_schema,
    normalize_field_schema
)


class ColumnSchema(BaseModel):
    id: Optional[str] = None
    key: Optional[str] = None
    name: str
    label: Optional[str] = None
    type: str = "text"
    placeholder: Optional[str] = None
    required: Optional[bool] = False
    active: Optional[bool] = True
    max_marks: Optional[float] = None
    maxMarks: Optional[float] = None
    options: Optional[Any] = None
    trigger_value: Optional[str] = None
    triggerValue: Optional[str] = None
    extra_label: Optional[str] = None
    extraLabel: Optional[str] = None
    formula_expr: Optional[str] = None
    formulaExpr: Optional[str] = None
    min_val: Optional[float] = None
    minVal: Optional[float] = None
    aggregate: Optional[str] = None
    width: Optional[Any] = None
    prefilled: Optional[bool] = False
    prefilled_values: Optional[List[Any]] = None
    prefilledValues: Optional[List[Any]] = None
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_col(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return normalize_column_schema(data, strict=False)
        return data


class FieldSchema(BaseModel):
    id: Optional[str] = None
    key: Optional[str] = None
    label: str
    type: str = "text"
    layout: Optional[str] = "rows"
    row_header_title: Optional[str] = None
    rowHeaderTitle: Optional[str] = None
    row_headers: Optional[List[Any]] = None
    rowHeaders: Optional[List[Any]] = None
    required: bool = False
    options: Optional[List[str]] = None
    trigger_value: Optional[str] = None
    triggerValue: Optional[str] = None
    extra_label: Optional[str] = None
    extraLabel: Optional[str] = None
    row_max: Optional[float] = None
    rowMax: Optional[float] = None
    is_custom: bool = True
    isCustom: Optional[bool] = None
    active: bool = True
    auto_serial: Optional[bool] = None
    autoSerial: Optional[bool] = None
    require_complete_rows: Optional[bool] = None
    requireCompleteRows: Optional[bool] = None
    max_marks: Optional[float] = None
    maxMarks: Optional[float] = None
    columns: Optional[List[ColumnSchema]] = None
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_f(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return normalize_field_schema(data, strict=False)
        return data


class FormSectionCreate(BaseModel):
    code: str
    form_family: str
    part: str
    section_key: Optional[str] = None
    title: str
    max_marks: float = 0.0
    maxMarks: Optional[float] = None
    storage_table: Optional[str] = None
    fields: List[Any] = []
    active: bool = True
    order: int = 0
    table_order: Optional[List[str]] = None
    tableOrder: Optional[List[str]] = None
    part_guideline: Optional[str] = None
    partGuideline: Optional[str] = None
    registrar_part: Optional[bool] = False
    registrarPart: Optional[bool] = None
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_create(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "maxMarks" in data and "max_marks" not in data:
                data["max_marks"] = data["maxMarks"]
            if "tableOrder" in data and "table_order" not in data:
                data["table_order"] = data["tableOrder"]
            if "partGuideline" in data and "part_guideline" not in data:
                data["part_guideline"] = data["partGuideline"]
            if "registrarPart" in data and "registrar_part" not in data:
                data["registrar_part"] = data["registrarPart"]
            if not data.get("section_key") and data.get("code"):
                data["section_key"] = data["code"]
        return data


class FormSectionUpdate(BaseModel):
    title: Optional[str] = None
    max_marks: Optional[float] = None
    maxMarks: Optional[float] = None
    active: Optional[bool] = None
    part: Optional[str] = None
    order: Optional[int] = None
    section_key: Optional[str] = None
    table_order: Optional[List[str]] = None
    tableOrder: Optional[List[str]] = None
    part_guideline: Optional[str] = None
    partGuideline: Optional[str] = None
    registrar_part: Optional[bool] = None
    registrarPart: Optional[bool] = None
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_update(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "maxMarks" in data and "max_marks" not in data:
                data["max_marks"] = data["maxMarks"]
            if "tableOrder" in data and "table_order" not in data:
                data["table_order"] = data["tableOrder"]
            if "part_guideline" not in data and "partGuideline" in data:
                data["part_guideline"] = data["partGuideline"]
            if "registrar_part" not in data and "registrarPart" in data:
                data["registrar_part"] = data["registrarPart"]
        return data


class FormSectionFieldsUpdate(BaseModel):
    fields: List[Any]
    table_order: Optional[List[str]] = None
    tableOrder: Optional[List[str]] = None
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_fields_update(cls, data: Any) -> Any:
        if isinstance(data, list):
            return {"fields": data}
        if isinstance(data, dict):
            if "tableOrder" in data and "table_order" not in data:
                data["table_order"] = data["tableOrder"]
        return data


class FormSectionResponse(BaseModel):
    code: str
    form_family: str
    part: str
    section_key: str
    title: str
    max_marks: float
    maxMarks: Optional[float] = None
    storage_table: Optional[str] = None
    fields: List[Any] = []
    active: bool = True
    order: int = 0
    table_order: List[str] = []
    tableOrder: Optional[List[str]] = None
    part_guideline: Optional[str] = None
    partGuideline: Optional[str] = None
    registrar_part: bool = False
    registrarPart: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="after")
    def populate_aliases(self) -> "FormSectionResponse":
        self.maxMarks = self.max_marks
        self.tableOrder = self.table_order
        self.partGuideline = self.part_guideline
        self.registrarPart = self.registrar_part
        return self
