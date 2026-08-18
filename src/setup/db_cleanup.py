import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func, update
from src.setup.database import Base, AsyncSessionLocal

logger = logging.getLogger(__name__)

async def run_db_cleanup():
    """
    Startup database cleanup and self-healing:
    1. Normalizes all email columns across all tables (lowercases and trims them).
    2. Identifies and merges/deletes duplicate faculty profiles with same email.
    """
    # Import all models to ensure they are registered on Base.metadata
    try:
        from src.models import core, non_teaching, part_a, part_b
    except Exception as e:
        logger.error(f"Error importing models for database cleanup: {e}")
        return

    async with AsyncSessionLocal() as session:
        try:
            logger.info("Starting database self-healing and email normalization...")
            
            # Step 1: Find and merge duplicate faculty profiles (case-insensitive and space-insensitive)
            from src.models.core import FacultyProfile, Declaration, Department, RoleAssignment
            
            # Find duplicate emails
            dup_stmt = (
                select(func.lower(func.trim(FacultyProfile.email)), func.count(FacultyProfile.id))
                .group_by(func.lower(func.trim(FacultyProfile.email)))
                .having(func.count(FacultyProfile.id) > 1)
            )
            dup_res = await session.execute(dup_stmt)
            duplicates = dup_res.all()
            
            if duplicates:
                logger.info(f"Found {len(duplicates)} duplicate emails to resolve.")
                for email_norm, count in duplicates:
                    if not email_norm:
                        continue
                    logger.info(f"Resolving duplicate email '{email_norm}' (count: {count})...")
                    
                    # Fetch all profiles with this email (case-insensitive)
                    profiles_stmt = (
                        select(FacultyProfile)
                        .where(func.lower(func.trim(FacultyProfile.email)) == email_norm)
                        .order_by(
                            FacultyProfile.is_active.desc(),
                            FacultyProfile.is_verified.desc(),
                            FacultyProfile.created_at.desc()
                        )
                    )
                    p_res = await session.execute(profiles_stmt)
                    profiles = p_res.scalars().all()
                    
                    if len(profiles) <= 1:
                        continue
                        
                    primary = profiles[0]
                    duplicates_to_remove = profiles[1:]
                    
                    logger.info(f"Keeping primary profile ID {primary.id} for {email_norm}.")
                    
                    for dup in duplicates_to_remove:
                        logger.info(f"Merging and deleting duplicate profile ID {dup.id}...")
                        
                        # Update references in Declarations
                        await session.execute(
                            update(Declaration)
                            .where(Declaration.part_d_released_by == dup.id)
                            .values(part_d_released_by=primary.id)
                        )
                        
                        # Update Department created_by
                        await session.execute(
                            update(Department)
                            .where(Department.created_by == dup.id)
                            .values(created_by=primary.id)
                        )
                        
                        # Update RoleAssignment user_id and created_by
                        await session.execute(
                            update(RoleAssignment)
                            .where(RoleAssignment.user_id == dup.id)
                            .values(user_id=primary.id)
                        )
                        await session.execute(
                            update(RoleAssignment)
                            .where(RoleAssignment.created_by == dup.id)
                            .values(created_by=primary.id)
                        )
                        
                        # Delete the duplicate profile
                        await session.delete(dup)
                        
                await session.commit()
                logger.info("Duplicate faculty profiles resolved successfully.")
            else:
                logger.info("No duplicate faculty profiles found.")

            # Step 2: Normalize all email columns across all tables dynamically
            for table_name, table in Base.metadata.tables.items():
                for column in table.columns:
                    if "email" in column.name.lower():
                        col_name = column.name
                        logger.info(f"Normalizing column {table_name}.{col_name}...")
                        await session.execute(
                            text(f"UPDATE {table_name} SET {col_name} = LOWER(TRIM({col_name})) WHERE {col_name} IS NOT NULL")
                        )
            await session.commit()
            logger.info("Email normalization completed successfully.")
                
        except Exception as e:
            await session.rollback()
            logger.error(f"Error running database cleanup: {e}", exc_info=True)
