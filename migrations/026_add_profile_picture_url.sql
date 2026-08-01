-- Migration: Add profile_picture_url to faculty_profiles table
ALTER TABLE faculty_profiles ADD COLUMN IF NOT EXISTS profile_picture_url VARCHAR;
