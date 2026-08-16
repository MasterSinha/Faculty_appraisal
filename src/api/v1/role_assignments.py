from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID
import uuid
from datetime import datetime
from typing import List, Optional

from src.setup.database import get_db
from src.setup.dependencies import CurrentUser, normalize_school
from src.models.core import Department, RoleAssignment, FacultyProfile, AppraisalConfig

router = APIRouter(prefix="/role-assignments", tags=["Role Assignments"])

class TransferRoleBody(BaseModel):
    role_type: str
    scope_id: str
    incoming_email: str

class RemoveRoleBody(BaseModel):
    role_type: str
    scope_id: str

@router.get("/active", response_model=List[dict])
async def get_active_assignments(
    current_user: CurrentUser,
    role_type: str = Query(...),
    scope_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Get active role assignments for a given role and scope.
    """
    query = (
        select(RoleAssignment, FacultyProfile)
        .join(FacultyProfile, RoleAssignment.user_id == FacultyProfile.id)
        .where(
            RoleAssignment.role_type == role_type.upper(),
            RoleAssignment.scope_id == scope_id,
            RoleAssignment.status == "active"
        )
    )
    res = await db.execute(query)
    rows = res.all()
    
    return [
        {
            "assignment_id": str(asg.id),
            "role_type": asg.role_type,
            "scope_id": asg.scope_id,
            "email": fac.email,
            "name": fac.full_name,
            "start_date": asg.start_date.isoformat() if asg.start_date else ""
        }
        for asg, fac in rows
    ]

@router.post("/transfer", response_model=dict)
async def transfer_role(
    body: TransferRoleBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Transfer a role (HOD, Director, Dean) to a new user.
    """
    # 1. Resolve requester profile
    profile_res = await db.execute(
        select(FacultyProfile).where(FacultyProfile.id == UUID(current_user.id))
    )
    profile = profile_res.scalar_one_or_none()
    if not profile or not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active requester profile required."
        )

    # 2. Authorization checks
    is_admin = any(r in current_user.roles for r in ("admin", "super_admin"))
    
    # 3. Resolve academic year
    open_cfg_res = await db.execute(
        select(AppraisalConfig).where(AppraisalConfig.is_open == True)
    )
    open_config = open_cfg_res.scalar_one_or_none()
    academic_year = open_config.academic_year if open_config else "2025-2026"

    # Find incoming user
    inc_res = await db.execute(
        select(FacultyProfile).where(
            FacultyProfile.email == body.incoming_email,
            FacultyProfile.is_active == True
        )
    )
    incoming_user = inc_res.scalar_one_or_none()
    if not incoming_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incoming user profile not found or inactive."
        )

    # Check boundaries and auth based on role_type
    role_type = body.role_type.upper()
    if role_type == "HOD":
        try:
            dept_uuid = UUID(body.scope_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scope_id for HOD (must be UUID)")
            
        dept_res = await db.execute(
            select(Department).where(Department.id == dept_uuid, Department.status == "active")
        )
        dept = dept_res.scalar_one_or_none()
        if not dept:
            raise HTTPException(status_code=404, detail="Active department not found.")
            
        is_director = profile.appraisal_role == "director"
        school_match = normalize_school(profile.school) == normalize_school(dept.school_code)
        if not (is_admin or (is_director and school_match)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requester must be an active Director of this school or an Admin."
            )
            
        if normalize_school(incoming_user.school) != normalize_school(dept.school_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incoming user belongs to a different school."
            )
            
    elif role_type == "DIRECTOR":
        is_dean = profile.appraisal_role == "dean"
        if not (is_admin or is_dean):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requester must be a Dean or an Admin."
            )
            
        if normalize_school(incoming_user.school) != normalize_school(body.scope_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incoming user belongs to a different school than the scope."
            )
            
    elif role_type == "DEAN":
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admins can assign Deans."
            )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported role_type: {body.role_type}")

    # Find and deactivate existing active assignment
    old_res = await db.execute(
        select(RoleAssignment).where(
            RoleAssignment.role_type == role_type,
            RoleAssignment.scope_id == body.scope_id,
            RoleAssignment.status == "active",
            RoleAssignment.academic_year == academic_year
        )
    )
    old_assignment = old_res.scalar_one_or_none()
    
    outgoing_user = None
    if old_assignment:
        old_assignment.status = "transferred"
        old_assignment.end_date = datetime.utcnow()
        
        # Resolve outgoing user
        out_res = await db.execute(
            select(FacultyProfile).where(FacultyProfile.id == old_assignment.user_id)
        )
        outgoing_user = out_res.scalar_one_or_none()

    # Create new assignment
    new_assignment = RoleAssignment(
        id=uuid.uuid4(),
        role_type=role_type,
        scope_type="department" if role_type == "HOD" else ("school" if role_type == "DIRECTOR" else "dean_type"),
        scope_id=body.scope_id,
        user_id=incoming_user.id,
        status="active",
        academic_year=academic_year,
        created_by=profile.id
    )
    db.add(new_assignment)

    # Apply role updates (side effects)
    incoming_user.appraisal_role = role_type.lower()
    if role_type == "HOD" and 'dept' in locals() and dept:
        incoming_user.department = dept.name
        
    if outgoing_user:
        other_res = await db.execute(
            select(RoleAssignment).where(
                RoleAssignment.user_id == outgoing_user.id,
                RoleAssignment.status == "active",
                RoleAssignment.id != new_assignment.id
            )
        )
        if not other_res.scalars().all():
            outgoing_user.appraisal_role = "faculty"

    await db.commit()
    await db.refresh(new_assignment)

    return {
        "assignment_id": str(new_assignment.id),
        "role_type": new_assignment.role_type,
        "scope_id": new_assignment.scope_id,
        "email": incoming_user.email,
        "name": incoming_user.full_name,
        "start_date": new_assignment.start_date.isoformat() if new_assignment.start_date else ""
    }

@router.post("/remove", response_model=dict)
async def remove_role(
    body: RemoveRoleBody,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Remove/vacate an active role assignment.
    """
    profile_res = await db.execute(
        select(FacultyProfile).where(FacultyProfile.id == UUID(current_user.id))
    )
    profile = profile_res.scalar_one_or_none()
    if not profile or not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active requester profile required."
        )

    is_admin = any(r in current_user.roles for r in ("admin", "super_admin"))
    
    # Resolve academic year
    open_cfg_res = await db.execute(
        select(AppraisalConfig).where(AppraisalConfig.is_open == True)
    )
    open_config = open_cfg_res.scalar_one_or_none()
    academic_year = open_config.academic_year if open_config else "2025-2026"

    # Find active assignment
    res = await db.execute(
        select(RoleAssignment).where(
            RoleAssignment.role_type == body.role_type.upper(),
            RoleAssignment.scope_id == body.scope_id,
            RoleAssignment.status == "active",
            RoleAssignment.academic_year == academic_year
        )
    )
    assignment = res.scalar_one_or_none()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active role assignment not found."
        )

    # Auth check
    role_type = body.role_type.upper()
    if role_type == "HOD":
        try:
            dept_uuid = UUID(body.scope_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scope_id for HOD")
        dept_res = await db.execute(select(Department).where(Department.id == dept_uuid))
        dept = dept_res.scalar_one_or_none()
        if dept:
            is_director = profile.appraisal_role == "director"
            school_match = normalize_school(profile.school) == normalize_school(dept.school_code)
            if not (is_admin or (is_director and school_match)):
                raise HTTPException(status_code=403, detail="Not authorized.")
    elif role_type == "DIRECTOR":
        is_dean = profile.appraisal_role == "dean"
        if not (is_admin or is_dean):
            raise HTTPException(status_code=403, detail="Not authorized.")
    elif role_type == "DEAN":
        if not is_admin:
            raise HTTPException(status_code=403, detail="Not authorized.")

    # Deactivate the assignment
    assignment.status = "transferred"
    assignment.end_date = datetime.utcnow()

    # Revert user role if they have no other active roles
    user_res = await db.execute(
        select(FacultyProfile).where(FacultyProfile.id == assignment.user_id)
    )
    user = user_res.scalar_one_or_none()
    if user:
        other_res = await db.execute(
            select(RoleAssignment).where(
                RoleAssignment.user_id == user.id,
                RoleAssignment.status == "active",
                RoleAssignment.id != assignment.id
            )
        )
        if not other_res.scalars().all():
            user.appraisal_role = "faculty"

    await db.commit()
    return {"message": f"Active {body.role_type} role assignment removed successfully."}
