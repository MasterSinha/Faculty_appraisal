# migrations/

Manual SQL migration files for the Faculty Appraisal System.
There is no Alembic or automatic migration runner — all files are applied by hand.

---

## Two files, two purposes

| File | When to use |
|---|---|
| `Docs/schema.sql` | **Fresh install only.** Drops everything and recreates all tables, indexes, and triggers from scratch. Use this on a new server with an empty database. |
| `migrations/NNN_*.sql` | **Live DB upgrades.** Incremental changes applied to an existing database that already has data. Safe to run because they never drop tables or truncate data. |

They must stay in sync. Every change you apply via a migration file must also be reflected in `Docs/schema.sql`.

---

## Applied migrations — DO NOT modify or re-run

These have already been applied to the live database. Editing them will not change anything in the DB and will only create confusion.

| # | File | What it does |
|---|---|---|
| 001 | `001_unique_constraints.sql` | Composite UNIQUE constraints on declarations, snapshots, reviews, non-teaching appraisals |
| 002 | `002_fix_appraisal_role_constraint.sql` | Expanded `appraisal_role` CHECK to include `admin`, `staff`, `section_head` |
| 003 | `003_create_feedback_table.sql` | Created `feedback` table with category CHECK constraint + indexes |
| 004 | `004_add_indexes.sql` | Performance indexes on all Part A/B tables, faculty_profiles, declarations |
| 005 | `005_add_is_verified_column.sql` | Added `is_verified boolean` column to `faculty_profiles` |
| 006 | `006_appraisal_config_and_announcements.sql` | Created `appraisal_config` table (cycle open/close) and `announcements` table |
| 007 | `007_section_scores_and_password_reset.sql` | Added `section_scores jsonb` to `appraisal_reviews`; created `password_reset_tokens` table |
| 008 | `008_add_audience_to_announcements.sql` | Added target audience columns to announcements table |
| 009 | `009_add_module_config_table.sql` | Created appraisal module configuration table |
| 010 | `010_add_is_active_to_faculty_profiles.sql` | Added is_active status column to faculty profiles |
| 011 | `011_widen_announcement_audience.sql` | Widened the scope and audience check for announcements |
| 012 | `012_add_reports_to_registrar.sql` | Added reports_to_registrar flag to faculty profiles |
| 013 | `013_add_hr_super_admin_roles.sql` | Added hr and super_admin roles to appraisal role checks |
| 014 | `014_add_pending_registrar_review_status.sql` | Added "Pending Registrar Review" workflow state |
| 015 | `015_add_pending_ro_review_status.sql` | Added "Pending RO Review" workflow state |
| 016 | `016_add_reporting_officer_email.sql` | Added reporting_officer_email column to faculty profiles |
| 017 | `017_add_registrar_email.sql` | Added registrar_email column to faculty profiles |
| 018 | `018_nt_workflow_system.sql` | Non-teaching appraisal form workflow system table setup |
| 019 | `019_rejection_resubmission.sql` | Added resubmission and rejection workflow attributes |
| 020 | `020_reviewer_snapshots.sql` | Created reviewer draft snapshots table |
| 021 | `021_widen_reviewer_role_check.sql` | Added registrar, reporting_officer, section_head to reviewer role CHECKs |
| 022 | `022_nt_assignment_unique_constraints.sql` | Added unique constraints to non-teaching assignment tables |
| 023 | `023_add_mfa_support.sql` | Added Multi-Factor Authentication (MFA) parameters |
| 024 | `024_add_part_c_and_d_scores.sql` | Added part_c_total, part_d_total to declarations and part_c_score, part_d_score to reviews |
| 025 | `025_create_part_c_tables.sql` | Created tables for Part C sections (event_organisation, alumni_engagement, placement_mentoring) |

`seed_admin_user.sql` is a one-time setup file, not a schema migration. Run it once on a fresh install to create the first admin account.

---

## How to add a new migration

1. **Create the file** — name it `006_describe_your_change.sql` (next number in sequence).
   - Use `IF NOT EXISTS` / `IF EXISTS` guards so the file is safe to re-run by accident.
   - Keep it focused — one logical change per file.

2. **Apply it to the live DB** — via Cloud SQL Studio (GCP) or `psql` (on-premise):
   ```bash
   psql -U postgres -f migrations/006_describe_your_change.sql
   ```

3. **Update `Docs/schema.sql`** — apply the same change to the relevant table/index definition so that new installs stay in sync.

4. **Update the table above** — add a row for your new file.

---

## Setting up a brand new database

```bash
# 1. Full schema (tables, indexes, triggers, app_user role)
psql -U postgres -f Docs/schema.sql

# 2. First admin account
psql -U postgres -f migrations/seed_admin_user.sql
```

Do NOT run migrations 001–007 after a fresh install — `Docs/schema.sql` already includes all of them.
