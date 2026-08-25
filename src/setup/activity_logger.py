import logging
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.core import ActivityLog, AppraisalConfig

logger = logging.getLogger(__name__)

async def log_activity(
    db: AsyncSession,
    type: str,
    title: str,
    detail: str,
    meta: Optional[dict] = None,
    academic_year: Optional[str] = None
):
    """
    Log an activity to the activity_logs table in the database.
    """
    try:
        if not academic_year:
            # Resolve the active academic year
            active_res = await db.execute(
                select(AppraisalConfig.academic_year).where(AppraisalConfig.is_open == True).limit(1)
            )
            academic_year = active_res.scalar_one_or_none()
            if not academic_year:
                # Fallback: get the latest academic year config
                latest_res = await db.execute(
                    select(AppraisalConfig.academic_year).order_by(AppraisalConfig.academic_year.desc()).limit(1)
                )
                academic_year = latest_res.scalar_one_or_none()

        log = ActivityLog(
            id=uuid.uuid4(),
            type=type,
            title=title,
            detail=detail,
            meta=meta or {},
            academic_year=academic_year,
            created_at=datetime.utcnow()
        )
        db.add(log)
        await db.commit()
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        logger.error(f"Error writing activity log: {e}", exc_info=True)
