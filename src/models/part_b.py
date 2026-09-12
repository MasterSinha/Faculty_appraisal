from sqlalchemy import Column, String, Numeric, Integer, DateTime, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime
from src.setup.database import Base

class BasePartBModel(Base):
    __abstract__ = True
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    faculty_email = Column(String, nullable=False)
    academic_year = Column(String, nullable=False)
    form_family = Column(String)
    section_title = Column(String)
    max_marks = Column(Numeric)
    row_no = Column(Integer)
    score = Column(Numeric, nullable=False, default=0)
    hod_score = Column(Numeric)
    director_score = Column(Numeric)
    dean_score = Column(Numeric)
    vc_score = Column(Numeric)
    custom_fields = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class JournalPublication(BasePartBModel):
    __tablename__ = "journal_publications"
    title = Column(String)
    journal = Column(String)
    issn = Column(String)
    indexing = Column(String)

class PopularWriting(BasePartBModel):
    __tablename__ = "popular_writings"
    media = Column(String)
    film = Column(String)

class BookPublication(BasePartBModel):
    __tablename__ = "book_publications"
    title = Column(String)
    book = Column(String)
    issn = Column(String)
    isbn = Column(String)
    publisher = Column(String)
    coauthor = Column(String)
    first_author = Column(String)

class ICTPedagogy(BasePartBModel):
    __tablename__ = "ict_pedagogy"
    title = Column(String)
    description = Column(String)
    type = Column(String)
    quadrant = Column(String)

class ResearchGuidance(BasePartBModel):
    __tablename__ = "research_guidance"
    degree = Column(String)
    student_name = Column(String)
    thesis = Column(String)

class ResearchProject(BasePartBModel):
    __tablename__ = "research_projects"
    title = Column(String)
    agency = Column(String)
    sanction_date = Column(Date)
    amount = Column(Numeric)
    role = Column(String)
    project_status = Column(String)

class ExternalResearchProject(BasePartBModel):
    __tablename__ = "external_research_projects"
    title = Column(String)
    agency = Column(String)
    sanction_date = Column(Date)
    amount = Column(Numeric)
    role = Column(String)
    project_status = Column(String)

class IPRRecord(BasePartBModel):
    __tablename__ = "ipr_records"
    title = Column(String)
    scope = Column(String)
    ipr_date = Column(Date)
    ipr_status = Column(String)
    file_no = Column(String)

class Patent(BasePartBModel):
    __tablename__ = "patents"
    title = Column(String)
    type = Column(String)
    scope = Column(String)
    patent_date = Column(Date)
    patent_status = Column(String)
    file_no = Column(String)

class Award(BasePartBModel):
    __tablename__ = "awards"
    title = Column(String)
    award_date = Column(Date)
    agency = Column(String)
    level = Column(String)

class Conference(BasePartBModel):
    __tablename__ = "conferences"
    title = Column(String)
    type = Column(String)
    organization = Column(String)
    level = Column(String)

class ResearchProposal(BasePartBModel):
    __tablename__ = "research_proposals"
    title = Column(String)
    duration = Column(String)
    agency = Column(String)
    amount = Column(Numeric)

class ProductDeveloped(BasePartBModel):
    __tablename__ = "products_developed"
    details = Column(String)
    usage = Column(String)

class SelfDevelopment(BasePartBModel):
    __tablename__ = "self_development"
    program = Column(String)
    duration = Column(String)
    organization = Column(String)

class IndustrialTraining(BasePartBModel):
    __tablename__ = "industrial_training"
    company = Column(String)
    duration = Column(String)
    nature = Column(String)
