from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID
import uuid
from typing import List, Optional

from src.setup.database import get_db
from src.setup.dependencies import CurrentUser, normalize_school
from src.models.core import Department, RoleAssignment, FacultyProfile, AppraisalConfig
from src.crud.core import get_faculty_by_email

router = APIRouter(prefix="/schools", tags=["Departments & HODs"])

class DepartmentCreateBody(BaseModel):
    name: str

class HODAssignmentCreateBody(BaseModel):
    faculty_id: UUID
    department_id: UUID

class AssignFacultyBody(BaseModel):
    department: str

# ── Department Endpoints ───────────────────────────────────────────────────────

@router.get("/{school_code}/departments", response_model=List[dict])
async def list_departments(
    school_code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    List active departments for a school.
    No auth required as it is used during signup and registration.
    """
    norm_school = normalize_school(school_code)
    result = await db.execute(
        select(Department)
        .where(
            Department.school_code == norm_school,
            Department.status == "active"
        )
        .order_by(Department.name)
    )
    departments = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "name": d.name,
            "school_code": d.school_code
        }
        for d in departments
    ]

@router.post("/{school_code}/departments", response_model=dict)
async def create_department(
    school_code: str,
    body: DepartmentCreateBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a department.
    Auth: Requester must be an active Director of the same school, or an Admin.
    """
    norm_school = normalize_school(school_code)
    
    # Verify requester profile
    profile_res = await db.execute(
        select(FacultyProfile).where(FacultyProfile.id == UUID(current_user.id))
    )
    profile = profile_res.scalar_one_or_none()
    if not profile or not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active user profile required."
        )

    is_admin = any(r in current_user.roles for r in ("admin", "super_admin"))
    is_director = profile.appraisal_role == "director"

    if not (is_admin or (is_director and normalize_school(profile.school) == norm_school)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requester must be an active Director of this school or an Admin."
        )

    # Check duplicate active department
    exist_res = await db.execute(
        select(Department).where(
            Department.school_code == norm_school,
            Department.name == body.name,
            Department.status == "active"
        )
    )
    if exist_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department already exists."
        )

    new_dept = Department(
        id=uuid.uuid4(),
        school_code=norm_school,
        name=body.name,
        status="active",
        created_by=profile.id
    )
    db.add(new_dept)
    await db.commit()
    await db.refresh(new_dept)

    return {
        "id": str(new_dept.id),
        "name": new_dept.name,
        "school_code": new_dept.school_code
    }

@router.delete("/{school_code}/departments/{department_id}", response_model=dict)
async def delete_department(
    school_code: str,
    department_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Remove/deactivate a department (Soft Delete).
    Auth: Requester must be an active Director of the same school, or an Admin.
    """
    norm_school = normalize_school(school_code)
    
    # Verify requester profile
    profile_res = await db.execute(
        select(FacultyProfile).where(FacultyProfile.id == UUID(current_user.id))
    )
    profile = profile_res.scalar_one_or_none()
    if not profile or not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active user profile required."
        )

    is_admin = any(r in current_user.roles for r in ("admin", "super_admin"))
    is_director = profile.appraisal_role == "director"

    if not (is_admin or (is_director and normalize_school(profile.school) == norm_school)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requester must be an active Director of this school or an Admin."
        )

    # Find department
    dept_res = await db.execute(
        select(Department).where(
            Department.id == department_id,
            Department.school_code == norm_school
        )
    )
    dept = dept_res.scalar_one_or_none()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found."
        )

    dept.status = "inactive"
    await db.commit()

    return {"message": "Department deactivated successfully."}

# ── HOD Assignment Endpoints ──────────────────────────────────────────────────

@router.get("/{school_code}/hods", response_model=List[dict])
async def list_hods(
    school_code: str,
    academic_year: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    List HODs assigned in the school for the specified/active academic year.
    """
    norm_school = normalize_school(school_code)
    
    # Fallback to active academic year from config
    if not academic_year:
        open_cfg_res = await db.execute(
            select(AppraisalConfig).where(AppraisalConfig.is_open == True)
        )
        open_config = open_cfg_res.scalar_one_or_none()
        if open_config:
            academic_year = open_config.academic_year
        else:
            academic_year = "2025-2026" # Fallback

    # 1. Fetch active departments for this school
    dept_res = await db.execute(
        select(Department).where(
            Department.school_code == norm_school,
            Department.status == "active"
        )
    )
    depts = dept_res.scalars().all()
    dept_map = {str(d.id): d.name for d in depts}
    
    if not depts:
        return []

    # 2. Fetch role assignments corresponding to those departments
    query = (
        select(RoleAssignment, FacultyProfile)
        .join(FacultyProfile, RoleAssignment.user_id == FacultyProfile.id)
        .where(
            RoleAssignment.role_type == "HOD",
            RoleAssignment.scope_id.in_(dept_map.keys()),
            RoleAssignment.status == "active",
            RoleAssignment.academic_year == academic_year
        )
        .order_by(FacultyProfile.full_name)
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "assignment_id": str(asg.id),
            "faculty_id": str(asg.user_id),
            "name": fac.full_name,
            "email": fac.email,
            "department_id": asg.scope_id,
            "department_name": dept_map.get(asg.scope_id, "")
        }
        for asg, fac in rows
    ]

@router.post("/{school_code}/hods", response_model=dict)
async def assign_hod(
    school_code: str,
    body: HODAssignmentCreateBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Assign HOD of a department.
    Auth: Requester must be an active Director of the same school, or an Admin.
    """
    norm_school = normalize_school(school_code)
    
    # Verify requester profile
    profile_res = await db.execute(
        select(FacultyProfile).where(FacultyProfile.id == UUID(current_user.id))
    )
    profile = profile_res.scalar_one_or_none()
    if not profile or not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active user profile required."
        )

    is_admin = any(r in current_user.roles for r in ("admin", "super_admin"))
    is_director = profile.appraisal_role == "director"

    if not (is_admin or (is_director and normalize_school(profile.school) == norm_school)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requester must be an active Director of this school or an Admin."
        )

    # Resolve academic year
    open_cfg_res = await db.execute(
        select(AppraisalConfig).where(AppraisalConfig.is_open == True)
    )
    open_config = open_cfg_res.scalar_one_or_none()
    academic_year = open_config.academic_year if open_config else "2025-2026"

    # Verify target faculty profile
    target_res = await db.execute(
        select(FacultyProfile).where(FacultyProfile.id == body.faculty_id)
    )
    target_faculty = target_res.scalar_one_or_none()
    if not target_faculty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target faculty profile not found."
        )
    if normalize_school(target_faculty.school) != norm_school:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target faculty profile belongs to a different school."
        )

    # Verify department
    dept_res = await db.execute(
        select(Department).where(
            Department.id == body.department_id,
            Department.school_code == norm_school,
            Department.status == "active"
        )
    )
    dept = dept_res.scalar_one_or_none()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active department not found in this school."
        )

    # Check for existing assignment for this department and academic year
    dup_res = await db.execute(
        select(RoleAssignment).where(
            RoleAssignment.role_type == "HOD",
            RoleAssignment.scope_id == str(body.department_id),
            RoleAssignment.status == "active",
            RoleAssignment.academic_year == academic_year
        )
    )
    if dup_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HOD is already assigned for this department in this academic year."
        )

    # Create RoleAssignment
    assignment = RoleAssignment(
        id=uuid.uuid4(),
        role_type="HOD",
        scope_type="department",
        scope_id=str(body.department_id),
        user_id=body.faculty_id,
        status="active",
        academic_year=academic_year,
        created_by=profile.id
    )
    db.add(assignment)

    # Side-effect: Update target faculty role & department to HOD
    target_faculty.appraisal_role = "hod"
    target_faculty.department = dept.name

    await db.commit()
    await db.refresh(assignment)

    return {
        "assignment_id": str(assignment.id),
        "faculty_id": str(assignment.user_id),
        "department_id": str(assignment.scope_id),
        "academic_year": assignment.academic_year
    }

@router.delete("/{school_code}/hods/{assignment_id}", response_model=dict)
async def delete_hod_assignment(
    school_code: str,
    assignment_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete HOD assignment.
    Auth: Requester must be an active Director of the same school, or an Admin.
    """
    norm_school = normalize_school(school_code)
    
    # Verify requester profile
    profile_res = await db.execute(
        select(FacultyProfile).where(FacultyProfile.id == UUID(current_user.id))
    )
    profile = profile_res.scalar_one_or_none()
    if not profile or not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active user profile required."
        )

    is_admin = any(r in current_user.roles for r in ("admin", "super_admin"))
    is_director = profile.appraisal_role == "director"

    if not (is_admin or (is_director and normalize_school(profile.school) == norm_school)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requester must be an active Director of this school or an Admin."
        )

    # Find HODAssignment
    asg_res = await db.execute(
        select(RoleAssignment).where(RoleAssignment.id == assignment_id)
    )
    assignment = asg_res.scalar_one_or_none()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HOD assignment not found."
        )

    # side effect: Revert target faculty role back to 'faculty'
    faculty_res = await db.execute(
        select(FacultyProfile).where(FacultyProfile.id == assignment.user_id)
    )
    faculty = faculty_res.scalar_one_or_none()
    if faculty:
        # Check if they have other active assignments
        other_asgs_res = await db.execute(
            select(RoleAssignment).where(
                RoleAssignment.user_id == faculty.id,
                RoleAssignment.status == "active",
                RoleAssignment.id != assignment_id
            )
        )
        if not other_asgs_res.scalars().all():
            faculty.appraisal_role = "faculty"

    await db.delete(assignment)
    await db.commit()

    return {"message": "HOD assignment deleted successfully."}


# ── Faculty Program Assignment Endpoints ────────────────────────────────────────

@router.get("/{school_code}/faculty", response_model=List[dict])
async def list_school_faculty(
    school_code: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    List every active and inactive Faculty account for a school.
    Auth: requester must be an active Director of school_code, or Admin/VC.
    """
    norm_school = normalize_school(school_code)

    # Verify requester profile is active
    profile_res = await db.execute(
        select(FacultyProfile).where(FacultyProfile.id == UUID(current_user.id))
    )
    profile = profile_res.scalar_one_or_none()
    if not profile or not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active user profile required."
        )

    is_admin_or_vc = any(r in current_user.roles for r in ("admin", "super_admin", "vc"))
    is_director = profile.appraisal_role == "director"

    if not (is_admin_or_vc or (is_director and normalize_school(profile.school) == norm_school)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requester must be an active Director of this specific school, or Admin/VC."
        )

    # Fetch faculty
    fac_res = await db.execute(
        select(FacultyProfile)
        .where(
            FacultyProfile.appraisal_role == "faculty",
            FacultyProfile.school == norm_school
        )
        .order_by(FacultyProfile.full_name)
    )
    faculty_list = fac_res.scalars().all()

    return [
        {
            "email": f.email,
            "full_name": f.full_name,
            "department": f.department
        }
        for f in faculty_list
    ]


@router.post("/{school_code}/faculty/{email}/assign", response_model=dict)
async def assign_faculty_program(
    school_code: str,
    email: str,
    body: AssignFacultyBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Director sets a faculty member's program (department).
    Auth: requester must be an active Director of school_code.
    """
    norm_school = normalize_school(school_code)

    # Verify requester profile is active
    profile_res = await db.execute(
        select(FacultyProfile).where(FacultyProfile.id == UUID(current_user.id))
    )
    profile = profile_res.scalar_one_or_none()
    if not profile or not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active user profile required."
        )

    # Reject if the requester isn't the Director of this specific school
    is_director = profile.appraisal_role == "director"
    if not is_director or normalize_school(profile.school) != norm_school:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requester must be an active Director of this specific school."
        )

    # 1. department must match an active Department row where school_code equals path param
    dept_res = await db.execute(
        select(Department).where(
            Department.name == body.department,
            Department.school_code == norm_school,
            Department.status == "active"
        )
    )
    dept = dept_res.scalar_one_or_none()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found"
        )

    # 2. The target account (email) must exist, be is_active = true, have appraisal_role = "faculty", and belong to this same school_code
    target_user = await get_faculty_by_email(db, email)
    if not target_user or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty account not found"
        )

    if target_user.appraisal_role != "faculty" or normalize_school(target_user.school) != norm_school:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not a faculty account in this school"
        )

    # On success, set FacultyProfile.department to the given value and persist
    target_user.department = dept.name
    await db.commit()
    await db.refresh(target_user)

    return {
        "email": target_user.email,
        "full_name": target_user.full_name,
        "department": target_user.department
    }
