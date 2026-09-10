-- Migration 001: Add composite unique constraints
-- These enforce the (email, academic_year) composite key that the application
-- already assumes via its upsert logic, preventing duplicate rows from race conditions.
--
-- IMPORTANT: Run the deduplication CTEs first if the DB already has data.
-- They keep the most-recently-updated row per group and delete the rest.
-- If your DB is fresh (no existing data), skip straight to the ALTER TABLE statements.

-- ============================================================
-- STEP 1: Deduplicate (safe to run even on a clean DB)
-- ============================================================

-- declarations
DELETE FROM declarations
WHERE id NOT IN (
    SELECT DISTINCT ON (faculty_email, academic_year) id
    FROM declarations
    ORDER BY faculty_email, academic_year, updated_at DESC NULLS LAST
);

-- appraisal_snapshots
DELETE FROM appraisal_snapshots
WHERE id NOT IN (
    SELECT DISTINCT ON (faculty_email, academic_year) id
    FROM appraisal_snapshots
    ORDER BY faculty_email, academic_year, updated_at DESC NULLS LAST
);

-- appraisal_reviews  (keyed by faculty + year + reviewer role)
DELETE FROM appraisal_reviews
WHERE id NOT IN (
    SELECT DISTINCT ON (faculty_email, academic_year, reviewer_role) id
    FROM appraisal_reviews
    ORDER BY faculty_email, academic_year, reviewer_role, updated_at DESC NULLS LAST
);

-- non_teaching_appraisals
DELETE FROM non_teaching_appraisals
WHERE id NOT IN (
    SELECT DISTINCT ON (staff_email, academic_year) id
    FROM non_teaching_appraisals
    ORDER BY staff_email, academic_year, updated_at DESC NULLS LAST
);

-- ============================================================
-- STEP 2: Add constraints
-- ============================================================

ALTER TABLE declarations
    DROP CONSTRAINT IF EXISTS uq_declarations_email_year;
ALTER TABLE declarations
    ADD CONSTRAINT uq_declarations_email_year
    UNIQUE (faculty_email, academic_year);

ALTER TABLE appraisal_snapshots
    DROP CONSTRAINT IF EXISTS uq_snapshots_email_year;
ALTER TABLE appraisal_snapshots
    ADD CONSTRAINT uq_snapshots_email_year
    UNIQUE (faculty_email, academic_year);

ALTER TABLE appraisal_reviews
    DROP CONSTRAINT IF EXISTS uq_reviews_email_year_role;
ALTER TABLE appraisal_reviews
    ADD CONSTRAINT uq_reviews_email_year_role
    UNIQUE (faculty_email, academic_year, reviewer_role);

ALTER TABLE non_teaching_appraisals
    DROP CONSTRAINT IF EXISTS uq_non_teaching_email_year;
ALTER TABLE non_teaching_appraisals
    ADD CONSTRAINT uq_non_teaching_email_year
    UNIQUE (staff_email, academic_year);
