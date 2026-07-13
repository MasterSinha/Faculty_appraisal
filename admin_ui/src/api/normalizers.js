/* Normalizers — translate exact backend response shapes into frontend-friendly objects */
import { ALL_SCHOOL_CODES } from '../constants/schools';

// ---------------------------------------------------------------------------
// Stats  →  GET /api/v1/admin/stats
// ---------------------------------------------------------------------------
export function normalizeStats(raw) {
  raw = raw ?? {};

  const adminCount      = raw.by_role?.admin       ?? 0;
  const superAdminCount = raw.by_role?.super_admin ?? 0;
  const total = (raw.total_registered ?? raw.total_faculty ?? raw.total ?? 0) - adminCount - superAdminCount;

  // teaching_submission_pipeline = { "Pending Review": 30, "Approved": 90, ... }
  // Any faculty who has a Declaration record counts as "submitted"
  const pipeline = raw.teaching_submission_pipeline ?? {};
  const submitted = Object.values(pipeline).reduce((sum, n) => sum + (n ?? 0), 0);
  const pending = total - submitted;

  // by_school_submitted = { "SoCSEA": { "Pending Review": 10, "Approved": 45 }, ... }
  // by_school_registered = { "SoCSEA": 55, "SoBB": 40, ... }
  const bySchoolSub = raw.by_school_submitted ?? {};
  const bySchoolReg = raw.by_school_registered ?? {};

  const allSchools = new Set([...Object.keys(bySchoolSub), ...Object.keys(bySchoolReg)]);

  const bySchool = Array.from(allSchools)
    .filter(s => ALL_SCHOOL_CODES.includes(s))
    .map(school => {
      const statusMap = bySchoolSub[school] ?? {};
      const sub       = Object.values(statusMap).reduce((s, n) => s + (n ?? 0), 0);
      const total_s   = bySchoolReg[school] ?? sub;
      return { name: school, sub, pend: total_s - sub, total: total_s };
    })
    .sort((a, b) => a.name.localeCompare(b.name));

  return {
    total,
    submitted,
    pending,
    bySchool,
    bySchoolSub,
    availableYears: raw.available_years ?? [],
    academicYear:   raw.academic_year   ?? null,
    byRole:         raw.by_role         ?? {},
    pipeline,
    nonTeachingPipeline: raw.non_teaching_pipeline ?? {},
  };
}

// ---------------------------------------------------------------------------
// Users  →  GET /api/v1/admin/users
// ---------------------------------------------------------------------------
export function normalizeUsers(raw, isSuperAdmin = false) {
  raw = raw ?? [];
  const arr = Array.isArray(raw) ? raw : (raw.users ?? raw.items ?? []);
  return arr
    .filter(u => {
      const r = u.appraisal_role ?? u.role;
      if (r === 'super_admin') return false;
      if (r === 'admin') return isSuperAdmin;
      return true;
    })
    .map(u => ({
      id:          u.email,
      name:        u.full_name ?? u.name ?? u.email,
      email:       u.email,
      dept:        u.department ?? u.dept ?? '—',
      school:      u.school ?? '—',
      role:        u.appraisal_role ?? 'faculty',
      designation: u.designation ?? '—',
      employeeId:  u.employee_id ?? '—',
      phone:       u.phone ?? '—',
      qualification:      u.qualification ?? '—',
      teachingExperience: u.teaching_experience ?? '—',
      status:      u.is_verified === false ? 'Unverified' : 'Active',
      yr:          u.created_at ? new Date(u.created_at).getFullYear().toString() : '—',
      sub:         false,
      reports_to_registrar:    u.reports_to_registrar    ?? false,
      reporting_officer_email: u.reporting_officer_email ?? '',
      registrar_email:         u.registrar_email         ?? '',
    }));
}

// ---------------------------------------------------------------------------
// Feedback  →  GET /api/v1/feedback
// ---------------------------------------------------------------------------
export function normalizeFeedback(raw) {
  raw = raw ?? [];
  const arr = Array.isArray(raw) ? raw : (raw.items ?? raw.feedback ?? []);
  return arr.map(f => ({
    id:      f.id,
    user:    f.name ?? f.email ?? 'Unknown',
    av:      (f.name ?? f.email ?? 'UK').split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase(),
    subject: f.subject ?? '',
    msg:     f.message ?? f.description ?? '',
    cat:     (f.category ?? '').toLowerCase() === 'bug' ? 'Bug' : 'Query',
    date:    f.submitted_at
               ? new Date(f.submitted_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
               : '—',
    status:  f.status
               ? f.status.charAt(0).toUpperCase() + f.status.slice(1).replace(/_/g, ' ')
               : 'Open',
  }));
}
