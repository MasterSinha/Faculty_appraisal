-- Migration: 023_add_mfa_support.sql
-- Description: Create mfa_otps table to store transient MFA session tokens and OTP codes.

CREATE TABLE IF NOT EXISTS mfa_otps (
    id UUID PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    mfa_token VARCHAR(255) NOT NULL UNIQUE,
    otp_code VARCHAR(10) NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mfa_otps_token ON mfa_otps(mfa_token);
CREATE INDEX IF NOT EXISTS idx_mfa_otps_email ON mfa_otps(email);
