from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from fastapi import Depends, HTTPException, status, Header
from .database import get_db
from typing import List, Optional, Annotated
import os
from dotenv import load_dotenv

env_file = os.getenv("ENV_FILE")
if env_file and os.path.exists(env_file):
    load_dotenv(env_file, override=True)
elif os.getenv("TESTING") == "True":
    load_dotenv()
elif os.path.exists(".env.test") and not os.path.exists(".env"):
    load_dotenv(".env.test", override=True)
else:
    load_dotenv(override=True)

# Dean division membership — used by has_authority_over and dashboard filtering.
# A dean's `school` field must be set to "engineering" or "non_engineering" on registration.
# CISR is outside both divisions; only VC/Admin can review CISR faculty.
ENGINEERING_SCHOOLS = frozenset({"SoCSEA", "SoBB", "SoCE", "SoEMR"})
NON_ENGINEERING_SCHOOLS = frozenset({"SoCM", "SoMCS", "SoD", "SoAA", "SoHSS"})

_DYNAMIC_SCHOOL_TRACKS: dict = {}
_DYNAMIC_SCHOOL_FORM_FAMILIES: dict = {}

def register_school_track(code: str, track: str):
    if code and track:
        _DYNAMIC_SCHOOL_TRACKS[code.strip().lower()] = track.strip().lower()
        _DYNAMIC_SCHOOL_TRACKS[code.strip()] = track.strip().lower()

def register_school_form_family(code: str, family: str):
    if code and family:
        _DYNAMIC_SCHOOL_FORM_FAMILIES[code.strip().lower()] = family.strip()
        _DYNAMIC_SCHOOL_FORM_FAMILIES[code.strip()] = family.strip()
        norm = normalize_school(code)
        if norm:
            _DYNAMIC_SCHOOL_FORM_FAMILIES[norm.strip().lower()] = family.strip()
            _DYNAMIC_SCHOOL_FORM_FAMILIES[norm.strip()] = family.strip()

def get_school_track(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    norm = normalize_school(code)
    if norm in ENGINEERING_SCHOOLS:
        return "engineering"
    if norm in NON_ENGINEERING_SCHOOLS:
        return "non_engineering"
    if norm == "CISR":
        return _DYNAMIC_SCHOOL_TRACKS.get(code.strip().lower()) or _DYNAMIC_SCHOOL_TRACKS.get("cisr") or "cisr"
    return (
        _DYNAMIC_SCHOOL_TRACKS.get(code.strip().lower())
        or _DYNAMIC_SCHOOL_TRACKS.get(norm.strip().lower() if norm else "")
    )

def normalize_school(school: Optional[str]) -> Optional[str]:
    if not school:
        return school
    s = school.strip().lower()
    
    if "computer" in s or "csea" in s or "socsea" in s:
        return "SoCSEA"
    if "biotech" in s or "sobb" in s or "bioengineering" in s or "biology" in s:
        return "SoBB"
    if "civil" in s or "soce" in s:
        return "SoCE"
    if "emr" in s or "soemr" in s:
        return "SoEMR"
    if "commerce" in s or "management" in s or "socm" in s:
        return "SoCM"
    if "media" in s or "communication" in s or "somcs" in s:
        return "SoMCS"
    if "design" in s or "sod" in s:
        return "SoD"
    if "architecture" in s or "soaa" in s:
        return "SoAA"
    if "humanities" in s or "social sciences" in s or "sohss" in s or "hss" in s:
        return "SoHSS"
    if "cisr" in s:
        return "CISR"
        
    return school.strip()

def normalize_role(role: str) -> str:
    if not role:
        return role
    r = role.strip().lower().replace("_", " ")
    if r in {"vc", "vice chancellor", "vice_chancellor"}:
        return "vc"
    if r in {"hod", "head of department", "head of dept"}:
        return "hod"
    if r in {"center head"}:
        return "center_head"
    if r in {"reporting officer", "ro"}:
        return "reporting_officer"
    if r in {"super admin", "super_admin"}:
        return "super_admin"
    if r == "admin":
        return "admin"
    return r.replace(" ", "_")

class User:
    def __init__(
        self,
        id: str,
        email: str,
        roles: List[str],
        department: Optional[str] = None,
        school: Optional[str] = None,
        departments: Optional[List[str]] = None,
        assigned_schools: Optional[List[str]] = None,
        schools: Optional[List[str]] = None,
        school_tracks: Optional[dict] = None,
    ):
        self.id = id
        self.email = email
        self.roles = [normalize_role(r) for r in roles]
        self.department = department
        self.school = normalize_school(school)
        self.appraisal_role = self.roles[0] if self.roles else "faculty"
        self.departments = departments or ([department] if department else [])

        raw_schools = assigned_schools or schools or []
        if not raw_schools and self.school:
            raw_schools = [self.school]
        self.assigned_schools = [normalize_school(s) for s in raw_schools if s]
        self.schools = self.assigned_schools
        self.school_tracks = school_tracks or {}
        for c, t in self.school_tracks.items():
            register_school_track(c, t)

    def has_authority_over(self, subordinate_id: str, subordinate_role: str, subordinate_dept: Optional[str] = None, subordinate_school: Optional[str] = None) -> bool:
        """
        Implements Hierarchical Access Control:
        1. VC: All schools.
        2. Dean: All departments within their domain (engineering/non-engineering track).
        3. Director: All departments within their assigned schools.
        4. HOD: Only their specific department.
        """
        role_weights = {
            "faculty": 0,
            "non_teaching_staff": 0,
            "staff": 0,
            "hod": 1,
            "reporting_officer": 1.5,
            "section_head": 2,
            "director": 2,
            "center_head": 2.5,
            "dean": 3,
            "registrar": 3.5,
            "vc": 4,
            "admin": 5,
            "hr": 5,
            "super_admin": 6,
        }

        if any(r in self.roles for r in ("admin", "super_admin", "hr")):
            return True

        user_weight = max([role_weights.get(r, 0) for r in self.roles])
        sub_weight = role_weights.get((subordinate_role or "faculty").lower(), 0)

        # Self-access
        if str(self.id) == str(subordinate_id) or self.email == subordinate_id:
            return True

        # Hierarchy check
        if user_weight > sub_weight:
            if "vc" in self.roles or "registrar" in self.roles:
                return True
            
            sub_school_norm = normalize_school(subordinate_school)
            if "dean" in self.roles:
                if sub_school_norm == "CISR" or (subordinate_school and subordinate_school.strip().upper() == "CISR"):
                    return False

                dean_track = None
                if self.school == "engineering" or self.school in ENGINEERING_SCHOOLS:
                    dean_track = "engineering"
                elif self.school == "non_engineering" or self.school in NON_ENGINEERING_SCHOOLS:
                    dean_track = "non_engineering"
                elif self.school_tracks and self.school in self.school_tracks:
                    dean_track = self.school_tracks[self.school]
                else:
                    dean_track = get_school_track(self.school)

                sub_track = None
                if sub_school_norm in ENGINEERING_SCHOOLS:
                    sub_track = "engineering"
                elif sub_school_norm in NON_ENGINEERING_SCHOOLS:
                    sub_track = "non_engineering"
                elif self.school_tracks and sub_school_norm in self.school_tracks:
                    sub_track = self.school_tracks[sub_school_norm]
                elif self.school_tracks and subordinate_school in self.school_tracks:
                    sub_track = self.school_tracks[subordinate_school]
                else:
                    sub_track = get_school_track(sub_school_norm or subordinate_school)

                if dean_track and sub_track and dean_track.lower() == sub_track.lower():
                    return True

            if "director" in self.roles:
                if sub_school_norm != "CISR" and (not subordinate_school or subordinate_school.strip().upper() != "CISR"):
                    director_schools = [
                        normalize_school(s)
                        for s in (self.assigned_schools or ([self.school] if self.school else []))
                        if s
                    ]
                    raw_dir_schools = [s for s in (self.assigned_schools or ([self.school] if self.school else [])) if s]
                    all_dir_schools = set(director_schools + raw_dir_schools)
                    if (
                        sub_school_norm in all_dir_schools
                        or (subordinate_school and subordinate_school in all_dir_schools)
                        or any(sub_school_norm and s and sub_school_norm.lower() == s.lower() for s in all_dir_schools)
                        or any(subordinate_school and s and subordinate_school.lower() == s.lower() for s in all_dir_schools)
                    ):
                        return True

            if "center_head" in self.roles:
                if sub_school_norm == "CISR":
                    return True

            if any(r in self.roles for r in ["section_head", "reporting_officer"]):
                if self.school == sub_school_norm:
                    return True
            
            if "hod" in self.roles:
                hod_departments = self.departments or ([self.department] if self.department else [])
                if self.school == sub_school_norm and subordinate_dept in hod_departments:
                    return True
                
        return False

def get_form_family(school: str) -> str:
    """
    Maps a school code to a form family (standard, media, design, or custom).
    """
    if not school:
        return "standard"
        
    s_clean = school.strip()
    s_norm = s_clean.lower()

    if s_norm in _DYNAMIC_SCHOOL_FORM_FAMILIES:
        return _DYNAMIC_SCHOOL_FORM_FAMILIES[s_norm]
    if s_clean in _DYNAMIC_SCHOOL_FORM_FAMILIES:
        return _DYNAMIC_SCHOOL_FORM_FAMILIES[s_clean]

    s = normalize_school(school)
    if s:
        if s.lower() in _DYNAMIC_SCHOOL_FORM_FAMILIES:
            return _DYNAMIC_SCHOOL_FORM_FAMILIES[s.lower()]
        if s in _DYNAMIC_SCHOOL_FORM_FAMILIES:
            return _DYNAMIC_SCHOOL_FORM_FAMILIES[s]

    school_map = {
        "SoCSEA": "standard", "SoBB": "standard", "SoCE": "standard",
        "SoEMR": "standard", "SoCM": "standard", "CISR": "standard",
        "SoMCS": "media",
        "SoHSS": "media",
        "SoD": "design", "SoAA": "design"
    }
    return school_map.get(s, "standard")

async def get_current_user(
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Verifies the JWT from the Authorization header and returns the resolved User.
    Supports centralized SSO tokens mapping to local database roles, with local JWT fallback.
    """
    if not authorization:
        if os.getenv("ALLOW_MOCK_USER", "false").lower() == "true":
            return User(
                id="00000000-0000-0000-0000-000000000001",
                email="admin@example.com",
                roles=["admin", "faculty"],
                department="Computer Science",
                school="SoCSEA"
            )
        raise HTTPException(status_code=401, detail="Authorization header missing.")

    try:
        parts = authorization.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization header format.")
        token = parts[1]

        from .local_auth import decode_access_token, decode_central_token
        
        # 1. Try decoding with Central JWT configuration
        payload = None
        is_central = False
        
        try:
            payload = decode_central_token(token)
            if payload:
                is_central = True
        except Exception:
            pass

        # 2. Fallback to Local JWT configuration
        if not payload:
            payload = decode_access_token(token)

        if payload.get("purpose"):
            raise HTTPException(status_code=401, detail="This token is not valid for API access.")

        email = payload.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Token payload missing email.")

        def _is_uuid(val):
            if not val:
                return False
            from uuid import UUID
            try:
                UUID(str(val))
                return True
            except (ValueError, TypeError):
                return False

        from src.models.core import School, RoleAssignment, Department
        from src.crud.core import get_faculty_by_email

        school_tracks_map = {}
        schools_res = await db.execute(select(School.code, School.track, School.default_form, School.form_variant))
        for row in schools_res.all():
            c, t, d_form, f_variant = row[0], row[1], row[2], row[3]
            if c and t:
                school_tracks_map[c] = t
                register_school_track(c, t)
            if c:
                if f_variant and f_variant.lower() in ("mediacommunication", "media"):
                    fam = "media"
                elif f_variant and f_variant.lower() in ("designarts", "design"):
                    fam = "design"
                elif f_variant and f_variant.lower() != "standard":
                    fam = f_variant
                elif d_form and d_form.lower() not in ("standard", "creative"):
                    fam = d_form
                else:
                    fam = "standard"
                register_school_form_family(c, fam)

        if is_central:
            profile = await get_faculty_by_email(db, email)
            if not profile:
                raise HTTPException(
                    status_code=403,
                    detail="Authentication succeeded, but no profile was found for this user in Faculty Appraisal."
                )
            
            # Populate User object from local DB record
            roles = [profile.appraisal_role or "faculty"]
            
            dept_names = []
            if "hod" in roles:
                asg_res = await db.execute(
                    select(RoleAssignment.scope_id).where(
                        RoleAssignment.user_id == UUID(str(profile.id)),
                        RoleAssignment.role_type == "HOD",
                        RoleAssignment.status == "active",
                    )
                )
                dept_ids = [UUID(sid) for sid in asg_res.scalars().all() if _is_uuid(sid)]
                if dept_ids:
                    dept_res = await db.execute(
                        select(Department.name).where(
                            Department.id.in_(dept_ids),
                            Department.status == "active"
                        )
                    )
                    dept_names = dept_res.scalars().all()

            assigned_schools = []
            if "director" in roles:
                asg_res = await db.execute(
                    select(RoleAssignment.scope_id).where(
                        RoleAssignment.user_id == UUID(str(profile.id)),
                        RoleAssignment.role_type == "DIRECTOR",
                        RoleAssignment.status == "active",
                    )
                )
                assigned_schools = [normalize_school(sid) for sid in asg_res.scalars().all() if sid]
                if not assigned_schools and profile.school:
                    assigned_schools = [normalize_school(profile.school)]

            return User(
                id=str(profile.id),
                email=profile.email,
                roles=roles,
                department=profile.department,
                school=profile.school,
                departments=dept_names,
                assigned_schools=assigned_schools,
                school_tracks=school_tracks_map,
            )
        else:
            role = payload.get("appraisal_role") or payload.get("role", "faculty")
            roles = [role] if isinstance(role, str) else role
            
            dept_names = []
            assigned_schools = []
            if "hod" in roles or "director" in roles:
                profile = await get_faculty_by_email(db, email)
                if profile:
                    if "hod" in roles:
                        asg_res = await db.execute(
                            select(RoleAssignment.scope_id).where(
                                RoleAssignment.user_id == UUID(str(profile.id)),
                                RoleAssignment.role_type == "HOD",
                                RoleAssignment.status == "active",
                            )
                        )
                        dept_ids = [UUID(sid) for sid in asg_res.scalars().all() if _is_uuid(sid)]
                        if dept_ids:
                            dept_res = await db.execute(
                                select(Department.name).where(
                                    Department.id.in_(dept_ids),
                                    Department.status == "active"
                                )
                            )
                            dept_names = dept_res.scalars().all()

                    if "director" in roles:
                        asg_res = await db.execute(
                            select(RoleAssignment.scope_id).where(
                                RoleAssignment.user_id == UUID(str(profile.id)),
                                RoleAssignment.role_type == "DIRECTOR",
                                RoleAssignment.status == "active",
                            )
                        )
                        assigned_schools = [normalize_school(sid) for sid in asg_res.scalars().all() if sid]
                        if not assigned_schools and profile.school:
                            assigned_schools = [normalize_school(profile.school)]
                else:
                    if "director" in roles:
                        raw_list = payload.get("assigned_schools") or payload.get("schools") or []
                        if raw_list:
                            assigned_schools = [normalize_school(s) for s in raw_list if s]
                        elif payload.get("school"):
                            assigned_schools = [normalize_school(payload.get("school"))]

            return User(
                id=payload.get("sub"),
                email=payload.get("email").strip().lower() if payload.get("email") else None,
                roles=roles,
                department=payload.get("department"),
                school=payload.get("school"),
                departments=dept_names if dept_names else None,
                assigned_schools=assigned_schools if assigned_schools else None,
                school_tracks=school_tracks_map,
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


CurrentUser = Annotated[User, Depends(get_current_user)]
