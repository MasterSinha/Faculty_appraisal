from sqlalchemy import Column, String, Numeric, Integer, ForeignKey, JSON, DateTime, Date, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, validates
import uuid
from datetime import datetime
from src.setup.database import Base

class FacultyProfile(Base):
    __tablename__ = "faculty_profiles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String)
    employee_id = Column(String)
    full_name = Column(String, nullable=False)
    qualification = Column(String)
    designation = Column(String)
    department = Column(String)
    school = Column(String)
    teaching_experience = Column(String)
    phone = Column(String)
    academic_year = Column(String)
    appraisal_role = Column(String, nullable=False, default='faculty')
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    reports_to_registrar = Column(Boolean, nullable=False, default=False)
    reporting_officer_email = Column(String, nullable=True)
    registrar_email = Column(String, nullable=True)
    avatar = Column(String)
    profile_picture_url = Column(String, nullable=True)

    @validates("school")
    def validate_school(self, key, value):
        from src.setup.dependencies import normalize_school
        return normalize_school(value)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class FormSectionDefinition(Base):
    __tablename__ = "form_section_definitions"
    code = Column(String, primary_key=True)
    form_family = Column(String, nullable=False)
    part = Column(String, nullable=False)
    section_key = Column(String, nullable=False)
    title = Column(String, nullable=False)
    max_marks = Column(Numeric, nullable=False)
    storage_table = Column(String)
    fields = Column(JSONB, nullable=False, default=[])
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class Declaration(Base):
    __tablename__ = "declarations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    faculty_email = Column(String, nullable=False)
    academic_year = Column(String, nullable=False)
    part_a_total = Column(Numeric, nullable=False, default=0)
    part_b_total = Column(Numeric, nullable=False, default=0)
    part_c_total = Column(Numeric, nullable=False, default=0)
    part_d_total = Column(Numeric, nullable=False, default=0)
    grand_total = Column(Numeric, nullable=False, default=0)
    status = Column(String, nullable=False, default='Pending Review')
    submission_attempt = Column(Integer, nullable=False, default=1)
    submitted_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class AppraisalDocument(Base):
    __tablename__ = "appraisal_documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    faculty_email = Column(String, nullable=False)
    academic_year = Column(String, nullable=False)
    form_family = Column(String)
    section = Column(String, nullable=False)
    section_title = Column(String)
    max_marks = Column(Numeric)
    row_no = Column(Integer)
    doc_key = Column(String)
    file_name = Column(String, nullable=False)
    file_type = Column(String)
    file_url = Column(String)
    storage_path = Column(String)
    uploaded_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class AppraisalReview(Base):
    __tablename__ = "appraisal_reviews"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    faculty_email = Column(String, nullable=False)
    academic_year = Column(String, nullable=False)
    reviewer_email = Column(String)
    reviewer_role = Column(String, nullable=False)
    part_a_score = Column(Numeric, nullable=False, default=0)
    part_b_score = Column(Numeric, nullable=False, default=0)
    part_c_score = Column(Numeric, nullable=False, default=0)
    part_d_score = Column(Numeric, nullable=False, default=0)
    total_score = Column(Numeric, nullable=False, default=0)
    remarks = Column(String)
    section_scores = Column(JSONB, nullable=False, default={})
    status = Column(String, nullable=False)
    reviewed_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class AppraisalSnapshot(Base):
    __tablename__ = "appraisal_snapshots"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    faculty_email = Column(String, nullable=False)
    academic_year = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(80))
    email = Column(String(254), nullable=False)
    category = Column(String, nullable=False)
    subject = Column(String(120), nullable=False)
    message = Column(String(5000), nullable=False)
    status = Column(String, nullable=False, default='new')
    ip_address = Column(String)
    user_agent = Column(String(512))
    submitted_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class AppraisalConfig(Base):
    __tablename__ = "appraisal_config"
    id = Column(Integer, primary_key=True, autoincrement=True)
    academic_year = Column(String, nullable=False, unique=True)
    is_open = Column(Boolean, nullable=False, default=False)
    submission_start = Column(DateTime(timezone=True))
    submission_end = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


VALID_ANNOUNCEMENT_AUDIENCES = frozenset({
    "all", "faculty", "hod", "director", "dean", "registrar", "non_teaching_staff",
    "SoCSEA", "SoBB", "SoCE", "SoEMR", "SoCM", "SoMCS", "SoD", "SoAA", "CISR", "SoHSS",
})

class Announcement(Base):
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    body = Column(String(5000), nullable=False)
    audience = Column(String(500), nullable=False, default="all")
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class ModuleConfig(Base):
    __tablename__ = "module_config"
    id = Column(Integer, primary_key=True, default=1)
    appraisal_module_enabled = Column(Boolean, nullable=False, default=True)
    self_appraisal_enabled = Column(Boolean, nullable=False, default=True)
    peer_review_enabled = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class ReviewerSnapshot(Base):
    __tablename__ = "reviewer_snapshots"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    faculty_email = Column(String, nullable=False)
    academic_year = Column(String, nullable=False)
    reviewer_email = Column(String, nullable=False)
    reviewer_role = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False, default={})
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False)
    token_hash = Column(String, nullable=False, unique=True)
    used = Column(Boolean, nullable=False, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class MfaOtp(Base):
    __tablename__ = "mfa_otps"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False)
    mfa_token = Column(String, nullable=False, unique=True)
    otp_code = Column(String, nullable=False)
    used = Column(Boolean, nullable=False, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

