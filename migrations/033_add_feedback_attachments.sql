-- Migration 033: Add attachment columns to feedback table
-- Allows faculty/users to attach screenshots, PDFs, logs, or text files to feedback submissions.

ALTER TABLE feedback
    ADD COLUMN IF NOT EXISTS attachment_filename VARCHAR(255),
    ADD COLUMN IF NOT EXISTS attachment_content_type VARCHAR(100),
    ADD COLUMN IF NOT EXISTS attachment_size INTEGER,
    ADD COLUMN IF NOT EXISTS attachment_storage_path VARCHAR(500);
