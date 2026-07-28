# Appraisal 2.0: Backend Code & Documentation Gap Analysis

This document outlines a thorough review of the newly added `backend_documentation.md` against the active FastAPI Python backend implementation (`Faculty_appraisal`) and the new React/Vite frontend (`Appraisal-form-2.0`).

---

## 1. High-Level Thoughts & Overall Alignment

> [!NOTE]
> **Excellent Architectural Alignment:**  
> The core architectural patterns described in the documentation (normalized shredded tables for detailed sections + JSONB snapshots for UI re-hydration and drafts) are fully implemented. The frontend (`appraisalPersistence.js`) normalizes and maps keys correctly for submission, and the backend (`shred_form` in `appraisal.py`) correctly shreds the JSON data into normalized relational tables.

All the core tables for Teaching Staff (Part A and Part B) match the PostgreSQL database schema and SQLAlchemy models perfectly, and key mappings (such as aliases for variables) are handled correctly on both ends.

---

## 2. Key Findings & Critical Discrepancies

### 🚨 2.1 Multi-Factor Authentication (MFA) Mismatch
* **Backend Implementation:** The backend (`auth.py` lines 72–74) defaults `MFA_ENABLED` to `true` (unless overridden in the `.env`). When enabled, the login endpoint `/auth/login` returns a prompt response containing `{"mfa_required": true, "mfa_token": "..."}` and requires verification through `/auth/verify-mfa`.
* **Frontend Implementation:** The frontend (`Login.jsx`, `authService.js`) **has no implementation** or UI pages for MFA.
* **Documentation Gaps:** `/auth/verify-mfa` is completely omitted from Section 3.1 of `backend_documentation.md`.
* **Impact:** If `MFA_ENABLED=false` is not set explicitly in the environment variables, users will not be able to log in, because the frontend will redirect them back to the login page on receipt of the MFA challenge.

### 📋 2.2 Undocumented Database Tables
Several tables exist in `schema.sql` and `models/` that are omitted from Section 2 of `backend_documentation.md`:

| Omitted Table | Category | Purpose / Description |
| :--- | :--- | :--- |
| `form_section_definitions` | System / Core | Defines max marks, storage tables, and fields for dynamically rendered sections. |
| `module_config` | System Control | Master toggles for enabling self-appraisals, peer reviews, etc. |
| `mfa_otps` | Security | Stores temporary MFA OTP codes sent to users. |
| `reviewer_snapshots` | Review / Cache | Stores reviewer drafts dynamically (using `ReviewerSnapshot` model). |
| `nt_designations` | Non-Teaching | Defines workflow roles for non-teaching approval steps (e.g. Registrar, RO). |
| `nt_workflow_templates` | Non-Teaching | Templates representing chains of approvals. |
| `nt_workflow_template_steps`| Non-Teaching | Individual steps mapping to a template and designation. |
| `nt_workflow_assignments` | Non-Teaching | Mappings between templates and non-teaching staff emails/departments. |
| `nt_workflow_instances` | Non-Teaching | Live runtime workflow instances for submitted appraisals. |
| `nt_workflow_instance_steps`| Non-Teaching | Individual status tracks of each workflow step for a live instance. |

### 🔗 2.3 Undocumented API Endpoints
The following API groups and individual routes are missing from the `backend_documentation.md` but are actively present in the codebase and used by the frontend:

#### 1. Reviewer Draft Endpoints (`remarks.py`)
* `GET` `/api/v1/appraisal-remarks/draft/{email}` (Loads reviewer draft snapshots).
* `PUT` `/api/v1/appraisal-remarks/draft/{email}` (Saves reviewer draft snapshots).
* *Status:* Fully integrated into the frontend (`reviewWorkflow.js:490` and `reviewWorkflow.js:508`).

#### 2. Non-Teaching Workflow Endpoints (`non_teaching.py`)
* `GET` `/api/v1/non-teaching/workflow-template` (Fetches template structure).
* `GET` `/api/v1/non-teaching/workflow/{email}` (Fetches workflow tracking status for a staff member).
* *Status:* Actively utilized by the frontend (`nonTeachingWorkflow.js:804`).

#### 3. Administrative API Router (`admin.py`)
The entire prefix `/api/v1/admin/*` is omitted. This prefix includes 30+ endpoints handling:
* System stats (`/stats`).
* Global system config (`/config`).
* Test emails (`/test-email`).
* User profiles CRUD (`/users`, `/users/{email}`).
* Dropdown lookups (`/registrars`, `/reporting-officers`).
* Non-Teaching workflow configuration (templates, steps, assignments, designations).
* Submission lists and logs.
* Database backups/restores and transitions.

---

## 3. Analysis of Previously Resolved Gaps

Several files in the documentation (`BACKEND_CHANGES_REQUIRED.md` and `Missing.md`) listed required fixes. A review of the codebase confirms that **all of them have been successfully implemented**:

1. **Registrar Assignment Feature:** `registrar_email` column is added to `faculty_profiles`, admin endpoints can create/update it, and `GET /api/v1/admin/registrars` lists options. Registrars now only see their subordinates.
2. **Direct-to-Registrar Workflow for Non-Teaching:** In `non_teaching.py`, if a staff member has `reports_to_registrar = True`, the submission correctly starts status as `Pending Registrar Review` instead of `Draft`.
3. **Feedback page 403:** Handled in `feedback.py` (checks for both `admin` and `super_admin`).
4. **NT Status on subordinates list:** Implemented in `dashboard.py`, which overlays `NonTeachingAppraisal` statuses into the `Declaration` result.

---

## 4. Key Recommendations

1. **Update `backend_documentation.md`:** Incorporate the dynamic Non-Teaching workflow tables, reviewer drafts, and administrative endpoints. This is critical for the upcoming **Spring Boot Migration** to prevent the rewrite team from leaving out critical APIs.
2. **MFA Environment Safe-guarding:** Ensure that `MFA_ENABLED=false` is documented as mandatory for standard deployments unless a frontend MFA panel is scheduled for development.
3. **Deprecate Obsolete Documents:** Move `Missing.md` and `BACKEND_CHANGES_REQUIRED.md` to an archivals directory or mark them as resolved so developers aren't confused.
