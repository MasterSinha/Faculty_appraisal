from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, status, Header
from .database import get_db
from typing import List, Optional, Annotated
import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Dean division membership — used by has_authority_over and dashboard filtering.
# A dean's `school` field must be set to "engineering" or "non_engineering" on registration.
# CISR is outside both divisions; only VC/Admin can review CISR faculty.
ENGINEERING_SCHOOLS = frozenset({"SoCSEA", "SoBB", "SoCE", "SoEMR"})
NON_ENGINEERING_SCHOOLS = frozenset({"SoCM", "SoMCS", "SoD", "SoAA", "SoHSS"})

def normalize_school(school: Optional[str]) -> Optional[str]:
    if not school:
        return school
    s = school.strip().lower()
    if s in {
        "sohss", "hss", "humanities", "social sciences",
        "humanities and social sciences", "school of humanities and social sciences"
    }:
        return "SoHSS"
    
    mapping = {
        "socsea": "SoCSEA",
        "sobb": "SoBB",
        "soce": "SoCE",
        "soemr": "SoEMR",
        "socm": "SoCM",
        "somcs": "SoMCS",
        "sod": "SoD",
        "soaa": "SoAA",
        "cisr": "CISR"
    }
    return mapping.get(s, school.strip())

class User:
    def __init__(self, id: str, email: str, roles: List[str], department: Optional[str] = None, school: Optional[str] = None):
        self.id = id
        self.email = email
        self.roles = [r.lower() for r in roles]
        self.department = department
        self.school = normalize_school(school)

    def has_authority_over(self, subordinate_id: str, subordinate_role: str, subordinate_dept: Optional[str] = None, subordinate_school: Optional[str] = None) -> bool:
        """
        Implements Hierarchical Access Control:
        1. VC: All schools.
        2. Dean: All departments within their domain.
        3. Director: All departments within their school.
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
                if sub_school_norm in ENGINEERING_SCHOOLS:
                    return self.school == "engineering"
                if sub_school_norm in NON_ENGINEERING_SCHOOLS:
                    return self.school == "non_engineering"
                return False  # CISR and unknown — only VC/Admin

            if any(r in self.roles for r in ["director", "section_head", "reporting_officer", "center_head"]):
                return self.school == sub_school_norm
            
            if "hod" in self.roles:
                return self.school == sub_school_norm and self.department == subordinate_dept
                
        return False

def get_form_family(school: str) -> str:
    """
    Maps a school code to a form family (standard, media, design).
    """
    if not school:
        return "standard"
        
    s = normalize_school(school)
    school_map = {
        "SoCSEA": "standard", "SoBB": "standard", "SoCE": "standard",
        "SoEMR": "standard", "SoCM": "standard", "CISR": "standard",
        "SoMCS": "media",
        "SoHSS": "media",
        "SoD": "design", "SoAA": "design"
    }
    return school_map.get(s, "standard")

async def get_current_user(authorization: Annotated[Optional[str], Header()] = None) -> User:
    """
    Verifies the JWT from the Authorization header and returns the resolved User.
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

        from .local_auth import decode_access_token
        payload = decode_access_token(token)

        if payload.get("purpose"):
            raise HTTPException(status_code=401, detail="This token is not valid for API access.")

        role = payload.get("appraisal_role") or payload.get("role", "faculty")
        roles = [role] if isinstance(role, str) else role

        return User(
            id=payload.get("sub"),
            email=payload.get("email"),
            roles=roles,
            department=payload.get("department"),
            school=payload.get("school"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


CurrentUser = Annotated[User, Depends(get_current_user)]
