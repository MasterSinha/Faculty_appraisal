from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Optional
from datetime import datetime

class BasePartASchema(BaseModel):
    faculty_email: str
    academic_year: str
    form_family: Optional[str] = None
    section_title: Optional[str] = None
    max_marks: Optional[float] = None
    score: float = 0
    hod_score: Optional[float] = None
    director_score: Optional[float] = None
    dean_score: Optional[float] = None
    vc_score: Optional[float] = None

class TeachingProcessBase(BasePartASchema):
    row_no: Optional[int] = None
    semester: Optional[str] = None
    course_code: Optional[str] = None
    planned_classes: float = 0
    conducted_classes: float = 0

class TeachingProcessResponse(TeachingProcessBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class CourseFileBase(BasePartASchema):
    row_no: Optional[int] = None
    course: Optional[str] = None
    title: Optional[str] = None
    details: Optional[str] = None

class CourseFileResponse(CourseFileBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class InnovativeTeachingBase(BasePartASchema):
    row_no: Optional[int] = None
    details: Optional[str] = None

class InnovativeTeachingResponse(InnovativeTeachingBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ProjectGuidedBase(BasePartASchema):
    row_no: Optional[int] = None
    label: Optional[str] = None

class ProjectGuidedResponse(ProjectGuidedBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class QualificationEnhancementBase(BasePartASchema):
    row_no: Optional[int] = None
    label: Optional[str] = None

class QualificationEnhancementResponse(QualificationEnhancementBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class StudentFeedbackBase(BasePartASchema):
    row_no: Optional[int] = None
    course_code: Optional[str] = None
    feedback_1: float = 0
    feedback_2: float = 0

class StudentFeedbackResponse(StudentFeedbackBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DepartmentActivityBase(BasePartASchema):
    row_no: Optional[int] = None
    activity: Optional[str] = None
    nature: Optional[str] = None

class DepartmentActivityResponse(DepartmentActivityBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class UniversityActivityBase(BasePartASchema):
    row_no: Optional[int] = None
    activity: Optional[str] = None
    nature: Optional[str] = None

class UniversityActivityResponse(UniversityActivityBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class SocialContributionBase(BasePartASchema):
    row_no: Optional[int] = None
    activity: Optional[str] = None
    status: Optional[str] = None
    details: Optional[str] = None

class SocialContributionResponse(SocialContributionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class IndustryConnectBase(BasePartASchema):
    row_no: Optional[int] = None
    name: Optional[str] = None
    details: Optional[str] = None

class IndustryConnectResponse(IndustryConnectBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ACRScoreBase(BasePartASchema):
    row_no: Optional[int] = None
    label: Optional[str] = None

class ACRScoreResponse(ACRScoreBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
