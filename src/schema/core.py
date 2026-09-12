from pydantic import BaseModel, EmailStr, ConfigDict, model_validator
from uuid import UUID
from typing import Optional, List, Any
from datetime import datetime

class FacultyProfileBase(BaseModel):
    email: EmailStr
    full_name: str
    employee_id: Optional[str] = None
    qualification: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    school: Optional[str] = None
    teaching_experience: Optional[str] = None
    phone: Optional[str] = None
    academic_year: Optional[str] = None
    appraisal_role: str = 'faculty'
    avatar: Optional[str] = None
    profile_picture_url: Optional[str] = None

class FacultyProfileCreate(FacultyProfileBase):
    password: str

class FacultyProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    employee_id: Optional[str] = None
    qualification: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    school: Optional[str] = None
    teaching_experience: Optional[str] = None
    phone: Optional[str] = None
    academic_year: Optional[str] = None
    avatar: Optional[str] = None
    profile_picture_url: Optional[str] = None

class FacultyProfileResponse(FacultyProfileBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class FormSectionDefinitionBase(BaseModel):
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

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "maxMarks" in data and "max_marks" not in data:
                data["max_marks"] = data["maxMarks"]
            if "tableOrder" in data and "table_order" not in data:
                data["table_order"] = data["tableOrder"]
        return data

class FormSectionDefinitionResponse(FormSectionDefinitionBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="after")
    def populate_aliases(self) -> "FormSectionDefinitionResponse":
        self.maxMarks = self.max_marks
        self.tableOrder = self.table_order
        return self

class DeclarationBase(BaseModel):
    faculty_email: EmailStr
    academic_year: str
    part_a_total: float = 0
    part_b_total: float = 0
    part_c_total: float = 0
    part_d_total: float = 0
    grand_total: float = 0
    status: str = 'Pending Review'
    submission_attempt: int = 1

class DeclarationResponse(DeclarationBase):
    id: UUID
    submitted_at: datetime
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AppraisalDocumentBase(BaseModel):
    faculty_email: EmailStr
    academic_year: str
    section: str
    section_title: Optional[str] = None
    max_marks: Optional[float] = None
    row_no: Optional[int] = None
    doc_key: Optional[str] = None
    file_name: str
    file_type: Optional[str] = None
    file_url: Optional[str] = None
    storage_path: Optional[str] = None

class AppraisalDocumentResponse(AppraisalDocumentBase):
    id: UUID
    uploaded_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AppraisalReviewBase(BaseModel):
    faculty_email: EmailStr
    academic_year: str
    reviewer_email: Optional[EmailStr] = None
    reviewer_role: str
    part_a_score: float = 0
    part_b_score: float = 0
    part_c_score: float = 0
    part_d_score: float = 0
    total_score: float = 0
    remarks: Optional[str] = None
    status: str

class AppraisalReviewResponse(AppraisalReviewBase):
    id: UUID
    reviewed_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SchoolBase(BaseModel):
    code: str
    full_name: str
    track: str  # "engineering" | "non_engineering" | "cisr"
    has_hod: bool = False
    has_director: bool = True
    approval_chain: List[str]
    departments: List[str] = []
    default_form: Optional[str] = None  # "standard" | "creative"
    form_variant: Optional[str] = None
    form_type: Optional[str] = None
    form_label: Optional[str] = None

    active: bool = True
    order: Optional[int] = 0


class SchoolCreate(SchoolBase):
    defaultForm: Optional[str] = None
    formVariant: Optional[str] = None
    formType: Optional[str] = None
    formLabel: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_form_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "defaultForm" in data and "default_form" not in data:
                data["default_form"] = data["defaultForm"]
            if "formVariant" in data and "form_variant" not in data:
                data["form_variant"] = data["formVariant"]
            if "formType" in data and "form_type" not in data:
                data["form_type"] = data["formType"]
            if "formLabel" in data and "form_label" not in data:
                data["form_label"] = data["formLabel"]
        return data


class SchoolUpdate(BaseModel):
    full_name: Optional[str] = None
    track: Optional[str] = None
    has_hod: Optional[bool] = None
    has_director: Optional[bool] = None
    approval_chain: Optional[List[str]] = None
    departments: Optional[List[str]] = None
    default_form: Optional[str] = None
    form_variant: Optional[str] = None
    form_type: Optional[str] = None
    form_label: Optional[str] = None
    defaultForm: Optional[str] = None
    formVariant: Optional[str] = None
    formType: Optional[str] = None
    formLabel: Optional[str] = None
    active: Optional[bool] = None
    order: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_form_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "defaultForm" in data and "default_form" not in data:
                data["default_form"] = data["defaultForm"]
            if "formVariant" in data and "form_variant" not in data:
                data["form_variant"] = data["formVariant"]
            if "formType" in data and "form_type" not in data:
                data["form_type"] = data["formType"]
            if "formLabel" in data and "form_label" not in data:
                data["form_label"] = data["formLabel"]
        return data


class SchoolResponse(SchoolBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

