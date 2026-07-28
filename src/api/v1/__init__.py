from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, distinct
from src.setup.database import get_db
from src.models.core import Declaration, AppraisalConfig
from src.models.non_teaching import NonTeachingAppraisal
from typing import List

from .auth import router as auth_router
from .appraisal import router as appraisal_router
from .documents import router as documents_router
from .dashboard import router as dashboard_router
from .remarks import router as remarks_router
from .non_teaching import router as non_teaching_router
from .upload import router as upload_router
from .admin import router as admin_router
from .feedback import router as feedback_router
from .announcements import router as announcements_router

router = APIRouter()

@router.get("/academic-years/available", response_model=List[str], tags=["System"])
async def get_academic_years(db: AsyncSession = Depends(get_db)):
    t_res = await db.execute(select(distinct(Declaration.academic_year)))
    nt_res = await db.execute(select(distinct(NonTeachingAppraisal.academic_year)))
    cfg_res = await db.execute(select(distinct(AppraisalConfig.academic_year)))
    
    available_years = sorted(
        set(
            [r[0] for r in t_res.all() if r[0]] +
            [r[0] for r in nt_res.all() if r[0]] +
            [r[0] for r in cfg_res.all() if r[0]]
        ),
        reverse=True,
    )
    return available_years

router.include_router(auth_router)
router.include_router(appraisal_router)
router.include_router(documents_router)
router.include_router(dashboard_router)
router.include_router(remarks_router)
router.include_router(non_teaching_router)
router.include_router(upload_router)
router.include_router(admin_router)
router.include_router(feedback_router)
router.include_router(announcements_router)
