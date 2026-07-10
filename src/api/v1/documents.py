import os
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from src.setup.database import get_db
from src.setup.dependencies import CurrentUser
from src.models.core import AppraisalDocument
from sqlalchemy import select
from typing import List

router = APIRouter(prefix="/appraisal-documents", tags=["Appraisal Documents"])

@router.get("/")
async def get_documents(
    request: Request,
    academic_year: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(AppraisalDocument).where(
        AppraisalDocument.faculty_email == current_user.email,
        AppraisalDocument.academic_year == academic_year
    ))
    docs = result.scalars().all()
    
    if request:
        app_url = str(request.base_url).rstrip("/")
    else:
        app_url = os.getenv("APP_URL", "").rstrip("/")
        
    for doc in docs:
        if doc.file_url and doc.file_url.startswith("/"):
            doc.file_url = f"{app_url}{doc.file_url}"
            
    return docs
