from sqlalchemy import Column, String, Numeric, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from src.setup.database import Base

class BasePartAModel(Base):
    __abstract__ = True
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    faculty_email = Column(String, nullable=False)
    academic_year = Column(String, nullable=False)
    form_family = Column(String)
    section_title = Column(String)
    max_marks = Column(Numeric)
    score = Column(Numeric, nullable=False, default=0)
    hod_score = Column(Numeric)
    director_score = Column(Numeric)
    dean_score = Column(Numeric)
    vc_score = Column(Numeric)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class TeachingProcess(BasePartAModel):
    __tablename__ = "teaching_process"
    row_no = Column(Integer)
    semester = Column(String)
    course_code = Column(String)
    planned_classes = Column(Numeric, nullable=False, default=0)
    conducted_classes = Column(Numeric, nullable=False, default=0)

class CourseFile(BasePartAModel):
    __tablename__ = "course_files"
    row_no = Column(Integer)
    course = Column(String)
    title = Column(String)
    details = Column(String)

class InnovativeTeaching(BasePartAModel):
    __tablename__ = "innovative_teaching"
    row_no = Column(Integer, default=1)
    details = Column(String)

class ProjectGuided(BasePartAModel):
    __tablename__ = "projects_guided"
    row_no = Column(Integer)
    label = Column(String)

class QualificationEnhancement(BasePartAModel):
    __tablename__ = "qualification_enhancement"
    row_no = Column(Integer)
    label = Column(String)

class StudentFeedback(BasePartAModel):
    __tablename__ = "student_feedback"
    row_no = Column(Integer)
    course_code = Column(String)
    feedback_1 = Column(Numeric, nullable=False, default=0)
    feedback_2 = Column(Numeric, nullable=False, default=0)

class DepartmentActivity(BasePartAModel):
    __tablename__ = "department_activities"
    row_no = Column(Integer)
    activity = Column(String)
    nature = Column(String)

class UniversityActivity(BasePartAModel):
    __tablename__ = "university_activities"
    row_no = Column(Integer)
    activity = Column(String)
    nature = Column(String)

class SocialContribution(BasePartAModel):
    __tablename__ = "social_contributions"
    row_no = Column(Integer)
    activity = Column(String)
    status = Column(String)
    details = Column(String)

class IndustryConnect(BasePartAModel):
    __tablename__ = "industry_connect"
    row_no = Column(Integer)
    name = Column(String)
    details = Column(String)

class ACRScore(BasePartAModel):
    __tablename__ = "acr_scores"
    row_no = Column(Integer)
    label = Column(String)

class EventOrganization(BasePartAModel):
    __tablename__ = "event_organisation"
    row_no = Column(Integer)
    event = Column(String)
    role = Column(String)
    date = Column(String)
    level = Column(String)

class AlumniEngagement(BasePartAModel):
    __tablename__ = "alumni_engagement"
    row_no = Column(Integer)
    activity = Column(String)
    details = Column(String)
    date = Column(String)

class PlacementMentoring(BasePartAModel):
    __tablename__ = "placement_mentoring"
    row_no = Column(Integer)
    type = Column(String)
    name = Column(String)
    date = Column(String)
