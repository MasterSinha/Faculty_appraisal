# School of Humanities and Social Sciences (SoHSS) Implementation Guide

This document describes the architectural mapping and implementation details for integrating the new **School of Humanities and Social Sciences (SoHSS)** into the Faculty Appraisal 2.0 system.

---

## 1. Overview & Requirements
The School of Humanities and Social Sciences (SoHSS) is a new academic unit requiring full integration. To avoid database restructuring, schema additions, or new endpoints, **SoHSS** behaves exactly like the **School of Media & Communication Studies (SoMCS)**.

### Core Behaviors:
- **Appraisal Form Family**: Media (`FORM_B` / `media`).
- **Workflow Routing**: Faculty -> Director -> Dean (Non-Engineering) -> VC.
- **HOD Routing**: Bypassed (SoHSS does not have HOD routing configured).
- **Dean Division**: Non-Engineering division.
- **Reviewer Permissions**: Shared with SoMCS authority scopes.

---

## 2. Input Normalization & Aliases
Faculty profiles may be registered or updated with various styles of school names. The system provides automatic mapping for the following aliases:

| Alias Casing / Text | Normalized Canonical Code |
| :--- | :--- |
| `sohss` | `SoHSS` |
| `hss` | `SoHSS` |
| `humanities` | `SoHSS` |
| `social sciences` | `SoHSS` |
| `humanities and social sciences` | `SoHSS` |
| `school of humanities and social sciences` | `SoHSS` |

---

## 3. Backend Integration Summary (`Faculty_appraisal`)

### 3.1 School Normalization
- Added `normalize_school` to `dependencies.py` which takes a raw string and returns `"SoHSS"` if it matches any of the aliases.
- Configured a SQLAlchemy `@validates("school")` decorator on the `FacultyProfile` database model in `src/models/core.py` to intercept writes and normalize the field before persisting.
- Added normalization calls to the `User` class initializer and the `has_authority_over` hierarchy checker to guarantee authorization is checked against normalized codes.

### 3.2 Routing & Permissions
- Registered `"SoHSS"` as a member of `NON_ENGINEERING_SCHOOLS` in `dependencies.py`.
- Mapped `"SoHSS"` to return `"media"` in the `get_form_family` mapping helper.
- Added `"SoHSS"` to `VALID_ANNOUNCEMENT_AUDIENCES` in `src/models/core.py` and `_SCHOOL_CODES` in `src/api/v1/announcements.py` for target messaging support.
- Normalized query filters inside `get_subordinates` in `src/api/v1/dashboard.py`.

---

## 4. Frontend Integration Summary (`Appraisal-form-2.0`)

### 4.1 Routing & Constants
- Added the SoHSS school configuration to `universityHierarchy.js`:
  ```javascript
  {
    code: "SoHSS",
    name: "School of Humanities and Social Sciences",
    label: "SoHSS - School of Humanities and Social Sciences",
    deanTrack: DEAN_TRACKS.NON_ENGINEERING,
    hodDepartments: [],
    aliases: [
      "sohss",
      "hss",
      "humanities",
      "social sciences",
      "humanities and social sciences",
      "school of humanities and social sciences",
    ],
  }
  ```
- Added `"SoHSS"` to the `FORM_TYPES.MEDIA_COMM` array in `formRouting.js`.

### 4.2 Form Layout & Validation
- Updated `isMediaCommSchool` inside `CreativeSchoolAppraisalForm.jsx` to return `true` if the school code or any of its name strings match `SoHSS`/`HSS`/`Humanities`. This ensures they share the exact layout, section fields (like Popular Writings), and validation rules.

### 4.3 Visual Configuration & Dynamic Headings
- Registered SoHSS colors and icons in `SCHOOL_VISUALS` in the Non-Engineering Dean Dashboard and `SCHOOL_META` in the VC Dashboard.
- Added `"SoHSS"` to `NON_ENGINEERING_REVIEW_SCHOOLS` in the Director Dashboard.
- Refactored `MediaCommDashboard.jsx` to dynamically switch titles, alert prompts, loading messages, and report exports based on the active user's school code (`SoHSS` vs `SoMCS`).
