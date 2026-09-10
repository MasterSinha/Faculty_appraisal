-- Migration 003: Create feedback table
-- Stores user-submitted queries, bug reports, and feedback from the frontend form.

CREATE TABLE IF NOT EXISTS feedback (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(80),
    email       VARCHAR(254)  NOT NULL,
    category    VARCHAR       NOT NULL CHECK (category IN ('query', 'feedback', 'bug', 'suggestion', 'other')),
    subject     VARCHAR(120)  NOT NULL,
    message     VARCHAR(5000) NOT NULL,
    status      VARCHAR       NOT NULL DEFAULT 'new',
    ip_address  VARCHAR,
    user_agent  VARCHAR(512),
    submitted_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_category ON feedback (category);
CREATE INDEX IF NOT EXISTS idx_feedback_status   ON feedback (status);
CREATE INDEX IF NOT EXISTS idx_feedback_submitted ON feedback (submitted_at DESC);
