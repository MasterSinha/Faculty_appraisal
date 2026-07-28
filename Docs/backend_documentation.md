# Backend Architecture & Database Documentation

This document provides a comprehensive technical reference for the backend system powering the **Appraisal Form 2.0** application.

---

## 1. Backend Architecture Overview

### 1.1 Technology Stack

```
+-----------------------------------------------------------------------+
|                             API LAYER                                 |
|                       FastAPI (Python 3.10+)                          |
|         - Uvicorn ASGI Server                                         |
|         - OpenAPI / Swagger Auto-documentation                        |
|         - Pydantic Models for Validation & Serialization               |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                       AUTHENTICATION & SECURITY                       |
|         - OAuth2 + Bearer JWT Tokens (PyJWT / python-jose)            |
|         - Passlib + bcrypt Password Hashing                            |
|         - Role-Based Access Control (RBAC) Guard Interceptors         |
|         - Hashed One-Time Password Reset Tokens                        |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                    SERVICE & WORKFLOW ENGINE LAYER                    |
|         - Multi-Tier Workflow Engine (HOD -> Director -> Dean -> VC)   |
|         - Snapshot & Table-Shredding Persistence Engine               |
|         - School-Specific Rule Dispatchers (SoEMR, CISR, General)     |
|         - Multi-part Document Attachment Manager                       |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                          DATABASE LAYER                               |
|                  PostgreSQL 14+ with `pgcrypto`                        |
|         - Normalized Atomic Section Tables                            |
|         - JSONB Hybrid Snapshot Storage (`appraisal_snapshots`)       |
|         - Automated `updated_at` Triggers & Custom Functions          |
+-----------------------------------------------------------------------+
```

### 1.2 Key Architectural Patterns

1. **Hybrid Persistence (Shredded Tables + JSONB Snapshots)**:
   - **Shredded Relational Tables**: Every section row (teaching process, publications, research projects, IPR, etc.) is shredded into individual normalized SQL tables with per-row reviewer score columns (`hod_score`, `director_score`, `dean_score`, `vc_score`). This enables atomic SQL queries, reporting, and direct score aggregation.
   - **JSONB Snapshots**: Full form states are saved atomically in `appraisal_snapshots` as JSONB payloads, allowing instantaneous UI re-hydration, draft saving, and exact point-in-time state preservation.

2. **Dynamic Workflow & Multi-Tier Hierarchy Engine**:
   - The backend dynamically calculates the review pipeline based on the subject's `appraisal_role` and `school`:
     - **Standard Schools** (SoCSEA, SoBB, SoCE, SoC, SoMCS, SoD, SoAA): `Director → Dean → VC`
     - **School with HOD** (SoEMR): `HOD → Director → Dean → VC`
     - **Standalone Research Center** (CISR): `Center Head → VC`
     - **Non-Teaching Staff**: `Reporting Officer → Registrar → VC`

3. **Stateless JWT Authentication & Security**:
   - Authentication relies on signed JWT Bearer Tokens in HTTP `Authorization` headers.
   - Password security is enforced via bcrypt hashing.
   - Email verification (`is_verified`) gates initial login.
   - Password reset uses single-use token hashes stored in `password_reset_tokens`.

---

## 2. Database Schema & Tables

The PostgreSQL database contains 40 tables organized into **Core System/Auth**, **Teaching Form Sections (Part A & B)**, **Review & Persistence**, **Non-Teaching Appraisal**, and **System/Admin Control**.

### 2.1 Core System & Auth Tables

#### Table: `faculty_profiles`
Stores user accounts, credentials, organizational placement, and appraisal roles.

| Column | Data Type | Constraints / Default | Description |
| :--- | :--- | :--- | :--- |
| `id` | `uuid` | `PRIMARY KEY`, `default gen_random_uuid()` | Unique user identifier |
| `email` | `text` | `NOT NULL`, `UNIQUE` | User email address (login credential) |
| `password_hash` | `text` | `NULLABLE` | Bcrypt hash of password |
| `employee_id` | `text` | `NULLABLE` | University employee identifier |
| `full_name` | `text` | `NOT NULL` | Full name of the user |
| `qualification` | `text` | `NULLABLE` | Educational qualification |
| `designation` | `text` | `NULLABLE` | Job designation (e.g. Assistant Professor) |
| `department` | `text` | `NULLABLE` | Academic department name |
| `school` | `text` | `NULLABLE` | School / Center code |
| `teaching_experience` | `text` | `NULLABLE` | Experience duration string |
| `phone` | `text` | `NULLABLE` | Contact phone number |
| `academic_year` | `text` | `NULLABLE` | Primary academic year |
| `appraisal_role` | `text` | `NOT NULL`, `default 'faculty'` | Role check constraint (`faculty`, `hod`, `center_head`, `director`, `dean`, `vc`, `non_teaching_staff`, `reporting_officer`, `section_head`, `registrar`, `staff`, `admin`) |
| `is_verified` | `boolean` | `NOT NULL`, `default false` | Email verification flag |
| `avatar` | `text` | `NULLABLE` | Profile avatar URL |
| `created_at` | `timestamptz` | `NOT NULL`, `default now()` | Creation timestamp |
| `updated_at` | `timestamptz` | `NOT NULL`, `default now()` | Last update timestamp |

**Indexes**:
- `faculty_profiles_role_idx` on `(appraisal_role)`
- `faculty_profiles_school_department_idx` on `(school, department)`
- `idx_faculty_profiles_school` on `(school)`

---

#### Table: `declarations`
Header record for a submitted faculty self-appraisal for a given academic year.

| Column | Data Type | Constraints / Default | Description |
| :--- | :--- | :--- | :--- |
| `id` | `uuid` | `PRIMARY KEY`, `default gen_random_uuid()` | Record UUID |
| `faculty_email` | `text` | `NOT NULL`, `FK -> faculty_profiles(email)` | Faculty member email |
| `academic_year` | `text` | `NOT NULL` | Academic year (e.g., "2025-2026") |
| `part_a_total` | `numeric` | `NOT NULL`, `default 0` | Total self-score for Part A |
| `part_b_total` | `numeric` | `NOT NULL`, `default 0` | Total self-score for Part B |
| `grand_total` | `numeric` | `NOT NULL`, `default 0` | Combined self-score |
| `status` | `text` | `NOT NULL`, `default 'Pending Review'` | Overall workflow status |
| `submitted_at` | `timestamptz` | `NOT NULL`, `default now()` | Timestamp of submission |
| `created_at` | `timestamptz` | `NOT NULL`, `default now()` | Creation timestamp |
| `updated_at` | `timestamptz` | `NOT NULL`, `default now()` | Last update timestamp |

**Constraints**: `UNIQUE (faculty_email, academic_year)`  
**Indexes**: `declarations_faculty_year_idx`, `idx_declarations_academic_year`, `idx_declarations_status`

---

#### Table: `appraisal_reviews`
Stores reviewer scores, remarks, and audit trail per review tier.

| Column | Data Type | Constraints / Default | Description |
| :--- | :--- | :--- | :--- |
| `id` | `uuid` | `PRIMARY KEY`, `default gen_random_uuid()` | Review record ID |
| `faculty_email` | `text` | `NOT NULL` | Target faculty email |
| `academic_year` | `text` | `NOT NULL` | Academic year |
| `reviewer_email` | `text` | `NULLABLE` | Email of reviewer |
| `reviewer_role` | `text` | `NOT NULL`, Check (`hod`, `center_head`, `director`, `dean`, `vc`) | Role tier of reviewer |
| `part_a_score` | `numeric` | `NOT NULL`, `default 0` | Reviewer total for Part A |
| `part_b_score` | `numeric` | `NOT NULL`, `default 0` | Reviewer total for Part B |
| `total_score` | `numeric` | `NOT NULL`, `default 0` | Reviewer grand total |
| `remarks` | `text` | `NULLABLE` | Reviewer qualitative feedback |
| `section_scores` | `jsonb` | `NOT NULL`, `default '{}'` | Section-by-section breakdown |
| `status` | `text` | `NOT NULL` | Status output after this review |
| `reviewed_at` | `timestamptz` | `NOT NULL`, `default now()` | Review timestamp |
| `created_at` | `timestamptz` | `NOT NULL`, `default now()` | Record creation timestamp |
| `updated_at` | `timestamptz` | `NOT NULL`, `default now()` | Last update timestamp |

**Constraints**: `UNIQUE (faculty_email, academic_year, reviewer_role)`  
**Indexes**: `appraisal_reviews_faculty_year_idx`, `idx_appraisal_reviews_year`

---

#### Table: `appraisal_snapshots`
Atomic full-form JSONB snapshot store.

| Column | Data Type | Constraints / Default | Description |
| :--- | :--- | :--- | :--- |
| `id` | `uuid` | `PRIMARY KEY`, `default gen_random_uuid()` | Snapshot ID |
| `faculty_email` | `text` | `NOT NULL` | Target faculty email |
| `academic_year` | `text` | `NOT NULL` | Academic year |
| `payload` | `jsonb` | `NOT NULL` | Complete form JSON payload |
| `created_at` | `timestamptz` | `NOT NULL`, `default now()` | Creation timestamp |
| `updated_at` | `timestamptz` | `NOT NULL`, `default now()` | Last update timestamp |

**Constraints**: `UNIQUE (faculty_email, academic_year)`

---

#### Table: `appraisal_documents`
Stores supporting attachment metadata.

| Column | Data Type | Constraints / Default | Description |
| :--- | :--- | :--- | :--- |
| `id` | `uuid` | `PRIMARY KEY`, `default gen_random_uuid()` | Document ID |
| `faculty_email` | `text` | `NOT NULL` | Owner faculty email |
| `academic_year` | `text` | `NOT NULL` | Academic year |
| `form_family` | `text` | `NULLABLE` | Form code (standard/media/design) |
| `section` | `text` | `NOT NULL` | Section key (e.g. `journals`) |
| `section_title` | `text` | `NULLABLE` | Human-readable section title |
| `max_marks` | `numeric` | `NULLABLE` | Max marks allocated |
| `row_no` | `integer` | `NULLABLE` | Corresponding row index |
| `doc_key` | `text` | `NULLABLE` | Frontend document key (e.g. `journals0`) |
| `file_name` | `text` | `NOT NULL` | Original uploaded filename |
| `file_type` | `text` | `NULLABLE` | MIME type |
| `file_url` | `text` | `NULLABLE` | Public storage URL |
| `storage_path` | `text` | `NULLABLE` | Cloud storage internal path |
| `uploaded_at` | `timestamptz` | `NOT NULL`, `default now()` | Upload timestamp |
| `created_at` | `timestamptz` | `NOT NULL`, `default now()` | Record creation timestamp |
| `updated_at` | `timestamptz` | `NOT NULL`, `default now()` | Trigger update timestamp |

**Indexes**: `appraisal_documents_faculty_year_idx`

---

### 2.2 Teaching Section Tables (Shredded Row Tables)

Each teaching section table contains common identifying columns (`id`, `faculty_email`, `academic_year`, `form_family`, `section_title`, `max_marks`, `row_no`, `score`) and **four multi-tier reviewer score columns** (`hod_score`, `director_score`, `dean_score`, `vc_score`).

| Table Name | Section Description | Specific Business Columns |
| :--- | :--- | :--- |
| `teaching_process` | Section A1: Lectures & Practicals | `semester`, `course_code`, `planned_classes`, `conducted_classes` |
| `course_files` | Section A2: Course Files | `course`, `title`, `details` (Check: `1.Available`, `2.Partially Available`, `3.Not Available`) |
| `innovative_teaching` | Section A3: Innovative Methods | `details` *(Unique: faculty_email, academic_year)* |
| `projects_guided` | Section A4: UG/PG Project Guidance | `label` |
| `qualification_enhancement`| Section A5: Qualification Enhancement | `label` |
| `student_feedback` | Section A6: Student Feedback | `course_code`, `feedback_1`, `feedback_2` |
| `department_activities` | Section A7: Department Activities | `activity`, `nature` |
| `university_activities` | Section A8: University Activities | `activity`, `nature` |
| `social_contributions` | Section A9: Social Contributions | `activity`, `status`, `details` |
| `industry_connect` | Section A10: Industry Connect | `name`, `details` |
| `acr_scores` | Section A11: ACR Scores | `label` |
| `journal_publications` | Section B1: Journal Papers | `title`, `journal`, `issn`, `indexing` |
| `popular_writings` | Section B1(ii): Popular Media/Film | `media`, `film` |
| `book_publications` | Section B2: Books & Chapters | `title`, `book`, `issn`, `isbn`, `publisher`, `coauthor`, `first_author` |
| `ict_pedagogy` | Section B3: ICT & E-Content | `title`, `description`, `type`, `quadrant` |
| `research_guidance` | Section B4(a): PhD/PG Supervision | `degree`, `student_name`, `thesis` |
| `research_projects` | Section B4(b): Internal Projects | `title`, `agency`, `sanction_date`, `amount`, `role`, `project_status` |
| `external_research_projects`| Section B4(c): External Projects | `title`, `agency`, `sanction_date`, `amount`, `role`, `project_status` |
| `ipr_records` | Section B5(a): IPR & Copyrights | `title`, `scope`, `ipr_date`, `ipr_status`, `file_no` |
| `patents` | Section B5(a): Patents | `title`, `type`, `scope`, `patent_date`, `patent_status`, `file_no` |
| `awards` | Section B5(b): Awards | `title`, `award_date`, `agency`, `level` |
| `conferences` | Section B6: Conference Papers | `title`, `type`, `organization`, `level` |
| `research_proposals` | Section B7(a): Research Proposals | `title`, `duration`, `agency`, `amount` |
| `products_developed` | Section B7(b): Lab Products | `details`, `usage` |
| `self_development` | Section B8(a): FDP & Workshops | `program`, `duration`, `organization` |
| `industrial_training` | Section B8(b): Industrial Training | `company`, `duration`, `nature` |

---

### 2.3 Non-Teaching Appraisal Tables

#### Table: `non_teaching_appraisals`
Main header and state table for non-teaching staff appraisals.

| Column | Data Type | Constraints / Default | Description |
| :--- | :--- | :--- | :--- |
| `id` | `uuid` | `PRIMARY KEY`, `default gen_random_uuid()` | Appraisal ID |
| `staff_email` | `text` | `NOT NULL` | Non-teaching staff email |
| `academic_year` | `text` | `NOT NULL` | Academic year |
| `payload` | `jsonb` | `NOT NULL` | Full non-teaching appraisal payload |
| `status` | `text` | `NOT NULL`, `default 'Draft'` Check (`Draft`, `Submitted`, `Reporting Officer Reviewed`, `Registrar Reviewed`, `VC Approved`) | Workflow stage |
| `self_total` | `numeric` | `NOT NULL`, `default 0` | Self total score |
| `ro_total` | `numeric` | `NOT NULL`, `default 0` | Reporting Officer total |
| `registrar_total` | `numeric` | `NOT NULL`, `default 0` | Registrar total |
| `vc_total` | `numeric` | `NOT NULL`, `default 0` | VC total |
| `submitted_at` | `timestamptz` | `NULLABLE` | Timestamp of self-submission |
| `ro_reviewed_at` | `timestamptz` | `NULLABLE` | Timestamp of RO review |
| `registrar_reviewed_at` | `timestamptz` | `NULLABLE` | Timestamp of Registrar review |
| `vc_reviewed_at` | `timestamptz` | `NULLABLE` | Timestamp of VC approval |
| `created_at` | `timestamptz` | `NOT NULL`, `default now()` | Record creation timestamp |
| `updated_at` | `timestamptz` | `NOT NULL`, `default now()` | Last update timestamp |

**Constraints**: `UNIQUE (staff_email, academic_year)`

---

#### Table: `non_teaching_part_a_items`
Part A self-assessment items for non-teaching staff.

| Column | Data Type | Description |
| :--- | :--- | :--- |
| `id` | `uuid PRIMARY KEY` | Item UUID |
| `staff_email` | `text NOT NULL` | Staff email |
| `academic_year` | `text NOT NULL` | Academic year |
| `item_key` | `text NOT NULL` | `selfResp` / `selfContrib` / `selfAchieve` |
| `title` | `text NOT NULL` | Item title |
| `max_marks` | `numeric NOT NULL` | Maximum marks allocated |
| `details` | `text` | Staff description |
| `self_marks`, `ro_marks`, `registrar_marks`, `vc_marks` | `numeric` | Scores awarded per tier |

---

#### Table: `non_teaching_part_b_ratings`
Part B authority rating parameters for non-teaching staff.

| Column | Data Type | Description |
| :--- | :--- | :--- |
| `id` | `uuid PRIMARY KEY` | Rating record ID |
| `staff_email`, `academic_year` | `text NOT NULL` | Staff credentials |
| `section_key` | `text NOT NULL` | `profComp`, `quality`, `personal`, `regular` |
| `section_title` | `text NOT NULL` | Section title |
| `max_marks` | `numeric NOT NULL` | Max marks |
| `parameter_no` | `integer NOT NULL` | Parameter index |
| `parameter_label` | `text NOT NULL` | Parameter label |
| `ro_rating`, `registrar_rating`, `vc_rating` | `numeric` | Marks assigned by authorities |

---

### 2.4 Administrative & System Tables

#### Table: `appraisal_config`
Controls window open/close dates per academic year.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `serial` | `PRIMARY KEY` | Config ID |
| `academic_year` | `varchar` | `NOT NULL UNIQUE` | Target academic year |
| `is_open` | `boolean` | `NOT NULL default false` | Submission toggle |
| `submission_start` | `timestamptz` | `NULLABLE` | Window start date |
| `submission_end` | `timestamptz` | `NULLABLE` | Window end date |

---

#### Table: `announcements`
Admin-managed notices displayed to users.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `serial` | `PRIMARY KEY` | Notice ID |
| `title` | `varchar(200)` | `NOT NULL` | Notice title |
| `body` | `varchar(5000)`| `NOT NULL` | Notice text content |
| `audience` | `varchar(50)` | `NOT NULL default 'all'` Check (`all`, `faculty`, `hod`, `dean`, `non_teaching_staff`) | Audience scope |
| `is_active` | `boolean` | `NOT NULL default true` | Visibility toggle |

---

#### Table: `password_reset_tokens`
Stores hashed single-use tokens for password recovery.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `uuid` | `PRIMARY KEY` | Token UUID |
| `email` | `text` | `NOT NULL` | User email |
| `token_hash` | `text` | `NOT NULL UNIQUE` | SHA256/bcrypt token hash |
| `expires_at` | `timestamptz` | `NOT NULL` | Expiration time |
| `used` | `boolean` | `NOT NULL default false` | Single-use flag |

---

## 3. Backend API Reference

Base Endpoint URL: `/api/v1`  
Authentication: HTTP Header `Authorization: Bearer <token>` for all protected routes.

### 3.1 Authentication & Profile APIs

| Method | Endpoint | Purpose | Request Body / Params | Response Body | Auth Req | Controller / Model |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/auth/login` | Authenticate user & issue JWT | `email`, `password` | `{ token, profile }` | None | `auth_controller.login` / `UserModel` |
| `POST` | `/auth/register` | Register new user account | Full profile payload & password | `{ message, email }` | None | `auth_controller.register` / `UserModel` |
| `GET` | `/auth/verify-email` | Verify user email from token | `token` (Query) | Redirect to `/login?verified=true` | None | `auth_controller.verify_email` |
| `GET` | `/auth/me` | Fetch active user profile | None | User profile object | Bearer JWT | `auth_controller.get_me` / `UserModel` |
| `PUT` | `/auth/me` | Update user profile details | Profile update fields | Updated profile object | Bearer JWT | `auth_controller.update_me` / `UserModel` |
| `POST` | `/auth/change-password` | Change user password | `current_password`, `new_password` | `{ message }` | Bearer JWT | `auth_controller.change_password` |
| `POST` | `/auth/forgot-password` | Send password reset email | `email` | `{ message }` | None | `auth_controller.forgot_password` |
| `POST` | `/auth/reset-password` | Reset password using token | `token`, `new_password` | `{ message }` | None | `auth_controller.reset_password` |

---

### 3.2 Teaching Staff Appraisal APIs

| Method | Endpoint | Purpose | Request Body / Params | Response Body | Auth Req | Controller / Model |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/appraisal/snapshot` | Fetch user's saved draft/form | `academic_year` (Query) | Snapshot object or `null` | Bearer JWT | `appraisal_controller.get_snapshot` |
| `PUT` | `/appraisal/snapshot` | Save form draft snapshot | `academic_year`, `payload` | `{ message: "Snapshot saved" }` | Bearer JWT | `appraisal_controller.save_snapshot` |
| `POST` | `/appraisal/submit` | Final self-appraisal submission | Form JSON, `totals`, `docs`, workflow metadata | `{ message, submitted_at }` | Bearer JWT | `appraisal_controller.submit` |
| `GET` | `/appraisal/status` | Fetch submission declaration & review chain progress | `academic_year` (Query) | `{ declaration, reviews: [] }` | Bearer JWT | `appraisal_controller.get_status` |

---

### 3.3 Reviewer & Workflow Management APIs

| Method | Endpoint | Purpose | Request Body / Params | Response Body | Auth Req | Controller / Model |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/dashboard/subordinates` | Fetch review queue for reviewer role | `academic_year`, `reviewer_role`, `pending_status`, `reviewer_school` | Array of subordinate summary objects | Bearer JWT | `reviewer_controller.get_subordinates` |
| `GET` | `/dashboard/faculty/{email}` | Load specific faculty member's full form snapshot & review history | `academic_year` (Query) | Full snapshot payload + per-row review scores | Bearer JWT | `reviewer_controller.get_faculty_snapshot` |
| `PUT` | `/appraisal-remarks/hod/{email}` | Submit HOD review scores & remarks | Review payload (`part_a_score`, `part_b_score`, `section_scores`, `remarks`) | `{ message, status }` | Bearer JWT (HOD) | `reviewer_controller.submit_hod_review` |
| `PUT` | `/appraisal-remarks/center-head/{email}` | Submit Center Head review (CISR) | Review payload | `{ message, status }` | Bearer JWT (Center Head) | `reviewer_controller.submit_center_head_review` |
| `PUT` | `/appraisal-remarks/director/{email}` | Submit Director review scores & remarks | Review payload | `{ message, status }` | Bearer JWT (Director) | `reviewer_controller.submit_director_review` |
| `PUT` | `/appraisal-remarks/dean/{email}` | Submit Dean review scores & remarks | Review payload | `{ message, status }` | Bearer JWT (Dean) | `reviewer_controller.submit_dean_review` |
| `PUT` | `/appraisal-remarks/final/{email}` | Submit VC final review & decision | Review payload | `{ message, status: "Reviewed" }` | Bearer JWT (VC) | `reviewer_controller.submit_vc_final_review` |

---

### 3.4 Non-Teaching Staff Appraisal APIs

| Method | Endpoint | Purpose | Request Body / Params | Response Body | Auth Req | Controller / Model |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/non-teaching/appraisal` | Fetch staff member's non-teaching form | `academic_year` (Query) | Non-teaching record with `payload` | Bearer JWT | `non_teaching_controller.get_appraisal` |
| `PUT` | `/non-teaching/appraisal` | Save draft or submit non-teaching form | `staff_email`, `academic_year`, `payload`, `status` | Updated non-teaching record | Bearer JWT | `non_teaching_controller.save_appraisal` |
| `GET` | `/non-teaching/subordinates` | Fetch review queue for non-teaching reviewers | `academic_year` (Query) | Array of non-teaching staff submissions | Bearer JWT | `non_teaching_controller.get_subordinates` |
| `PUT` | `/non-teaching/review/{staffEmail}` | Submit review by RO / Registrar / VC | `academic_year`, `payload`, `status`, `remarks` | Updated non-teaching record | Bearer JWT | `non_teaching_controller.submit_review` |

---

### 3.5 Supporting Documents, Uploads & System APIs

| Method | Endpoint | Purpose | Request Body / Params | Response Body | Auth Req | Controller / Model |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/upload` | Upload supporting document file | `multipart/form-data` (`file`, `folder`) | `{ url, publicId, name, type }` | Bearer JWT | `file_controller.upload_file` |
| `GET` | `/appraisal-documents` | Fetch uploaded documents map | `academic_year` (Query) | Array of document metadata objects | Bearer JWT | `file_controller.get_documents` |
| `GET` | `/announcements` | Fetch active system announcements | None | Array of active announcement objects | None | `system_controller.get_announcements` |
| `POST` | `/feedback` | Submit public query or feedback | `name`, `email`, `category`, `subject`, `message` | `{ message: "Feedback submitted" }` | None | `system_controller.submit_feedback` |
| `GET` | `/academic-years/available` | Fetch available academic cycle years | None | Array of cycle strings (e.g. `["2025-2026", "2026-2027"]`) | None | `system_controller.get_academic_years` |
