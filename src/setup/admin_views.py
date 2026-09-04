try:
    from sqladmin import Admin, ModelView
    from sqladmin.authentication import AuthenticationBackend
except ImportError:
    Admin = None
    ModelView = object
    AuthenticationBackend = object
from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqlalchemy import select
from src.setup.database import engine, AsyncSessionLocal
from src.models.core import FacultyProfile, Declaration, AppraisalReview, AppraisalDocument, Feedback, AppraisalConfig, Announcement, School
from src.models.non_teaching import NonTeachingAppraisal
from src.setup.local_auth import verify_password
import os


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = form.get("username")
        password = form.get("password")

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(FacultyProfile).where(FacultyProfile.email == email)
            )
            user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            return False
        if user.appraisal_role != "admin":
            return False

        request.session.update({"admin_email": email})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request):
        if not request.session.get("admin_email"):
            return RedirectResponse("/admin/login", status_code=302)


class SchoolAdmin(ModelView, model=School):
    name = "School"
    name_plural = "Schools"
    icon = "fa-solid fa-school"
    column_list = ["code", "full_name", "track", "default_form", "has_hod", "has_director", "active", "order"]
    column_searchable_list = ["code", "full_name"]
    column_sortable_list = ["code", "track", "active", "order"]
    column_filters = ["track", "default_form", "active"]


class FacultyProfileAdmin(ModelView, model=FacultyProfile):
    name = "Faculty Profile"
    name_plural = "Faculty Profiles"
    icon = "fa-solid fa-user"
    column_list = ["email", "full_name", "appraisal_role", "school", "department", "is_verified", "created_at"]
    column_searchable_list = ["email", "full_name"]
    column_sortable_list = ["school", "appraisal_role", "created_at"]
    column_filters = ["school", "appraisal_role", "is_verified"]
    form_excluded_columns = ["password_hash", "created_at", "updated_at"]


class DeclarationAdmin(ModelView, model=Declaration):
    name = "Declaration"
    name_plural = "Declarations"
    icon = "fa-solid fa-file-alt"
    column_list = ["faculty_email", "academic_year", "status", "part_a_total", "part_b_total", "grand_total", "submitted_at"]
    column_searchable_list = ["faculty_email"]
    column_sortable_list = ["academic_year", "status", "grand_total"]
    column_filters = ["academic_year", "status"]
    can_create = False


class AppraisalReviewAdmin(ModelView, model=AppraisalReview):
    name = "Appraisal Review"
    name_plural = "Appraisal Reviews"
    icon = "fa-solid fa-star"
    column_list = ["faculty_email", "academic_year", "reviewer_role", "reviewer_email", "part_a_score", "part_b_score", "total_score", "status", "reviewed_at"]
    column_searchable_list = ["faculty_email", "reviewer_email"]
    column_sortable_list = ["academic_year", "reviewer_role", "total_score"]
    column_filters = ["academic_year", "reviewer_role", "status"]
    can_create = False


class NonTeachingAppraisalAdmin(ModelView, model=NonTeachingAppraisal):
    name = "Non-Teaching Appraisal"
    name_plural = "Non-Teaching Appraisals"
    icon = "fa-solid fa-briefcase"
    column_list = ["staff_email", "academic_year", "status", "self_total", "ro_total", "registrar_total", "vc_total", "submitted_at"]
    column_searchable_list = ["staff_email"]
    column_sortable_list = ["academic_year", "status"]
    column_filters = ["academic_year", "status"]
    can_create = False


class FeedbackAdmin(ModelView, model=Feedback):
    name = "Feedback"
    name_plural = "Feedback"
    icon = "fa-solid fa-envelope"
    column_list = ["submitted_at", "category", "status", "name", "email", "subject"]
    column_searchable_list = ["email", "subject", "name"]
    column_sortable_list = ["submitted_at", "category", "status"]
    column_filters = ["category", "status"]
    can_create = False


class AppraisalDocumentAdmin(ModelView, model=AppraisalDocument):
    name = "Document"
    name_plural = "Documents"
    icon = "fa-solid fa-paperclip"
    column_list = ["faculty_email", "academic_year", "section", "file_name", "file_type", "uploaded_at"]
    column_searchable_list = ["faculty_email"]
    column_sortable_list = ["academic_year", "uploaded_at"]
    column_filters = ["academic_year", "section"]
    can_create = False
    can_edit = False


class AppraisalConfigAdmin(ModelView, model=AppraisalConfig):
    name = "Appraisal Config"
    name_plural = "Appraisal Configs"
    icon = "fa-solid fa-calendar-check"
    column_list = ["academic_year", "is_open", "submission_start", "submission_end", "updated_at"]
    column_sortable_list = ["academic_year", "is_open"]
    column_filters = ["is_open"]


class AnnouncementAdmin(ModelView, model=Announcement):
    name = "Announcement"
    name_plural = "Announcements"
    icon = "fa-solid fa-bullhorn"
    column_list = ["created_at", "is_active", "title", "created_by"]
    column_searchable_list = ["title", "created_by"]
    column_sortable_list = ["created_at", "is_active"]
    column_filters = ["is_active"]


def create_admin(app):
    if Admin is None:
        return None
    auth_backend = AdminAuth(secret_key=os.getenv("JWT_SECRET_KEY", "fallback-secret"))
    admin = Admin(
        app,
        engine,
        authentication_backend=auth_backend,
        title="Faculty Appraisal — Admin",
        base_url="/admin",
    )
    admin.add_view(SchoolAdmin)
    admin.add_view(FacultyProfileAdmin)
    admin.add_view(DeclarationAdmin)
    admin.add_view(AppraisalReviewAdmin)
    admin.add_view(NonTeachingAppraisalAdmin)
    admin.add_view(FeedbackAdmin)
    admin.add_view(AppraisalDocumentAdmin)
    admin.add_view(AppraisalConfigAdmin)
    admin.add_view(AnnouncementAdmin)
    return admin

