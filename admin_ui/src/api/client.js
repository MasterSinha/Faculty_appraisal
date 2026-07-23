const BASE = '/api/v1'

function getToken() {
  return localStorage.getItem('admin_token')
}

function _logSecEvent(type, endpoint, statusCode, detail, email = null) {
  try {
    const entry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      type, endpoint, statusCode, detail, email,
      at: new Date().toISOString(),
    };
    const raw = localStorage.getItem('dyp_security_events');
    const existing = raw ? JSON.parse(raw) : [];
    localStorage.setItem('dyp_security_events', JSON.stringify([entry, ...existing].slice(0, 1000)));
  } catch {}
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = { ...options.headers }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  })

  const data = await res.json().catch(() => null)

  if (res.status === 401) {
    _logSecEvent('unauthorized', path, 401, data?.detail || 'Token rejected or session expired');
    if (localStorage.getItem('admin_token')) {
      localStorage.removeItem('admin_token')
      localStorage.removeItem('admin_profile')
      window.location.href = '/panel/login'
      return
    }
    throw new Error(data?.user_message || data?.detail || 'Invalid credentials')
  }

  if (res.status === 403) {
    _logSecEvent('forbidden', path, 403, data?.detail || 'Access denied — insufficient role');
  }

  if (res.status === 429) {
    _logSecEvent('rate_limited', path, 429, data?.detail || 'Too many requests — possible brute force');
  }

  if (!res.ok) {
    const msg = data?.user_message || data?.detail || `Server error (${res.status})`
    throw new Error(msg)
  }

  return data
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------
async function login(email, password) {
  const data = await request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  if (!data?.profile) throw new Error('Unexpected response from server.')
  if (!['admin', 'super_admin'].includes(data.profile.appraisal_role)) {
    throw new Error('This account does not have admin access.')
  }
  localStorage.setItem('admin_token', data.token)
  localStorage.setItem('admin_profile', JSON.stringify(data.profile))
  return data
}

function logout() {
  localStorage.removeItem('admin_token')
  localStorage.removeItem('admin_profile')
}

function getProfile() {
  const raw = localStorage.getItem('admin_profile')
  return raw ? JSON.parse(raw) : null
}

// ---------------------------------------------------------------------------
// Faculty / users
// ---------------------------------------------------------------------------
const users = {
  list: (params = {}) => request('/admin/users?' + new URLSearchParams(params)),
  create: (data) => request('/admin/users', { method: 'POST', body: JSON.stringify(data) }),
  update: (email, data) => request(`/admin/users/${encodeURIComponent(email)}`, { method: 'PUT', body: JSON.stringify(data) }),
  remove: (email) => request(`/admin/users/${encodeURIComponent(email)}`, { method: 'DELETE' }),
  reportingOfficers: () => request('/admin/reporting-officers'),
  registrars: () => request('/admin/registrars'),
}

// ---------------------------------------------------------------------------
// Stats / submission tracking
// ---------------------------------------------------------------------------
const stats = {
  get: (academic_year) => {
    const qs = academic_year ? `?academic_year=${academic_year}` : ''
    return request(`/admin/stats${qs}`)
  },
}

// ---------------------------------------------------------------------------
// Faculty marks (super_admin only)
// ---------------------------------------------------------------------------
const marks = {
  list: (academic_year, schools = '') => {
    const qs = new URLSearchParams({ academic_year })
    if (schools) qs.set('schools', schools)
    return request(`/dashboard/subordinates?${qs}`)
  },
  detail: (email, academic_year) =>
    request(`/dashboard/faculty/${encodeURIComponent(email)}?academic_year=${encodeURIComponent(academic_year)}`),
}

// ---------------------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------------------
const feedback = {
  list: (params = {}) => request('/feedback?' + new URLSearchParams(params)),
  get: (id) => request(`/feedback/${id}`),
}

// ---------------------------------------------------------------------------
// Config (settings)
// ---------------------------------------------------------------------------
const config = {
  get: () => request('/admin/config'),
  update: (data) => request('/admin/config', { method: 'PUT', body: JSON.stringify(data) }),
}

// ---------------------------------------------------------------------------
// Appraisal cycle config
// ---------------------------------------------------------------------------
const cycle = {
  list:   ()                   => request('/admin/appraisal-config'),
  create: (data)               => request('/admin/appraisal-config', { method: 'POST', body: JSON.stringify(data) }),
  update: (academic_year, data)=> request(`/admin/appraisal-config/${encodeURIComponent(academic_year)}`, { method: 'PUT', body: JSON.stringify(data) }),
  remove: (academic_year)      => request(`/admin/appraisal-config/${encodeURIComponent(academic_year)}`, { method: 'DELETE' }),
}

// ---------------------------------------------------------------------------
// Pending faculty (dedicated endpoint — faster than filtering /admin/users)
// ---------------------------------------------------------------------------
const pending = {
  list: (params = {}) => request('/admin/pending-faculty?' + new URLSearchParams(params)),
}

// ---------------------------------------------------------------------------
// Submissions — per-faculty form status list (requires backend: GET /admin/submissions)
// Returns: [{ email, full_name, school, department, appraisal_role, status, submitted_at }]
// ---------------------------------------------------------------------------
const submissions = {
  list: (params = {}) => request('/admin/submissions?' + new URLSearchParams(params)),
}

// ---------------------------------------------------------------------------
// Logs — faculty activity logs (requires backend: GET /admin/faculty-activity-logs)
// ---------------------------------------------------------------------------
const logs = {
  facultyActivity: (params = {}) => request('/admin/faculty-activity-logs?' + new URLSearchParams(params)),
}

// ---------------------------------------------------------------------------
// Announcements
// ---------------------------------------------------------------------------
const announcements = {
  list:   (params = {}) => request('/admin/announcements?' + new URLSearchParams(params)),
  create: (data)        => request('/admin/announcements', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data)    => request(`/admin/announcements/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  remove: (id)          => request(`/admin/announcements/${id}`, { method: 'DELETE' }),
}

// ---------------------------------------------------------------------------
// AI assistant
// ---------------------------------------------------------------------------
const ai = {
  ask: (prompt) => request('/admin/ai', { method: 'POST', body: JSON.stringify({ prompt }) }),
}

// ---------------------------------------------------------------------------
// Analytics export (file downloads — returns a Blob, not JSON)
// ---------------------------------------------------------------------------
async function downloadFile(path) {
  const token = getToken()
  const res = await fetch(`${BASE}${path}`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(data?.user_message || `Download failed (${res.status})`)
  }
  return res.blob()
}

const exportData = {
  submissions: (params = {}) => downloadFile('/admin/export/submissions?' + new URLSearchParams(params)),
  faculty:     (params = {}) => downloadFile('/admin/export/faculty?' + new URLSearchParams(params)),
}

// ---------------------------------------------------------------------------
// Non-teaching workflow — live chain per staff member
// ---------------------------------------------------------------------------
const workflow = {
  getTemplate:   (role, reportsDirectly = false) =>
    request(`/non-teaching/workflow-template?role=${encodeURIComponent(role)}&reports_directly=${reportsDirectly}`),
  getForFaculty: (email, academicYear) =>
    request(`/non-teaching/workflow/${encodeURIComponent(email)}?academic_year=${encodeURIComponent(academicYear)}`),
}

// ---------------------------------------------------------------------------
// Designations — catalog of approval designations used in NT workflows
// ---------------------------------------------------------------------------
const designations = {
  list:   ()          => request('/admin/nt-designations'),
  create: (data)      => request('/admin/nt-designations', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data)  => request(`/admin/nt-designations/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(data) }),
  remove: (id)        => request(`/admin/nt-designations/${encodeURIComponent(id)}`, { method: 'DELETE' }),
}

// ---------------------------------------------------------------------------
// Workflow templates — named approval chains with ordered designation steps
// ---------------------------------------------------------------------------
const workflowTemplates = {
  list:            ()               => request('/admin/nt-workflow-templates'),
  create:          (data)           => request('/admin/nt-workflow-templates', { method: 'POST', body: JSON.stringify(data) }),
  update:          (id, data)       => request(`/admin/nt-workflow-templates/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(data) }),
  remove:          (id)             => request(`/admin/nt-workflow-templates/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  setDefault:      (id)             => request(`/admin/nt-workflow-templates/${encodeURIComponent(id)}/set-default`, { method: 'PUT' }),
  addStep:         (id, data)       => request(`/admin/nt-workflow-templates/${encodeURIComponent(id)}/steps`, { method: 'POST', body: JSON.stringify(data) }),
  updateStep:      (id, stepNo, d)  => request(`/admin/nt-workflow-templates/${encodeURIComponent(id)}/steps/${stepNo}`, { method: 'PUT', body: JSON.stringify(d) }),
  removeStep:      (id, stepNo)     => request(`/admin/nt-workflow-templates/${encodeURIComponent(id)}/steps/${stepNo}`, { method: 'DELETE' }),
  reorderSteps:    (id, steps)      => request(`/admin/nt-workflow-templates/${encodeURIComponent(id)}/reorder`, { method: 'PUT', body: JSON.stringify({ steps }) }),
  listAssignments: ()               => request('/admin/nt-workflow-assignments'),
  assign:          (data)           => request('/admin/nt-workflow-assignments', { method: 'POST', body: JSON.stringify(data) }),
  removeAssignment:(id)             => request(`/admin/nt-workflow-assignments/${encodeURIComponent(id)}`, { method: 'DELETE' }),
}

// Helper for large file uploads with progress tracking
async function uploadRequest(path, file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const token = getToken();
    
    xhr.open('POST', `${BASE}${path}`);
    
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }
    
    // Track upload progress
    if (xhr.upload && onProgress) {
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const percent = Math.round((event.loaded / event.total) * 100);
          onProgress(percent);
        }
      });
    }
    
    xhr.onload = () => {
      let data = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch (e) {}
      
      if (xhr.status === 401) {
        _logSecEvent('unauthorized', path, 401, data?.detail || 'Token rejected or session expired');
        if (localStorage.getItem('admin_token')) {
          localStorage.removeItem('admin_token');
          localStorage.removeItem('admin_profile');
          window.location.href = '/panel/login';
          return;
        }
        reject(new Error(data?.user_message || data?.detail || 'Invalid credentials'));
      }
      
      if (xhr.status === 403) {
        _logSecEvent('forbidden', path, 403, data?.detail || 'Access denied');
      }
      
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data);
      } else {
        const msg = data?.user_message || data?.detail || `Server error (${xhr.status})`;
        reject(new Error(msg));
      }
    };
    
    xhr.onerror = () => {
      reject(new Error('Network error occurred.'));
    };
    
    const fd = new FormData();
    fd.append('file', file);
    xhr.send(fd);
  });
}

// ---------------------------------------------------------------------------
// Current admin profile
// ---------------------------------------------------------------------------
const profile = {
  get:    ()     => request('/auth/me'),
  update: (data) => request('/auth/me', { method: 'PUT', body: JSON.stringify(data) }),
}

async function downloadFileWithProgress(path, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const token = getToken();
    
    xhr.open('GET', `${BASE}${path}`);
    xhr.responseType = 'blob';
    
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }
    
    if (onProgress) {
      xhr.onprogress = (event) => {
        if (event.lengthComputable) {
          const percent = Math.round((event.loaded / event.total) * 100);
          onProgress(percent, event.loaded, event.total);
        } else {
          onProgress(0, event.loaded, 0);
        }
      };
    }
    
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response);
      } else {
        const reader = new FileReader();
        reader.onload = () => {
          try {
            const data = JSON.parse(reader.result);
            reject(new Error(data?.user_message || data?.detail || `Download failed (${xhr.status})`));
          } catch {
            reject(new Error(`Download failed (${xhr.status})`));
          }
        };
        reader.onerror = () => reject(new Error(`Download failed (${xhr.status})`));
        reader.readAsText(xhr.response);
      }
    };
    
    xhr.onerror = () => {
      reject(new Error('Network error occurred during download.'));
    };
    
    xhr.send();
  });
}

const developer = {
  migrateUrls: (old_pattern) => request(`/admin/migrate-urls?old_pattern=${encodeURIComponent(old_pattern)}`, { method: 'POST' }),
  backupDb: (onProgress) => downloadFileWithProgress('/admin/backup/db', onProgress),
  backupUploads: (onProgress) => downloadFileWithProgress('/admin/backup/uploads', onProgress),
  restoreDb: (file, onProgress) => {
    return uploadRequest('/admin/restore/db', file, onProgress);
  },
  restoreUploads: (file, onProgress) => {
    return uploadRequest('/admin/restore/uploads', file, onProgress);
  },
  getPuzzle: () => request('/admin/transition/puzzle'),
  switchYear: (from_year, to_year) => request('/admin/transition/switch', {
    method: 'POST',
    body: JSON.stringify({ from_year, to_year })
  }),
  revertYear: (from_year, to_year, token, answer) => request('/admin/transition/revert', {
    method: 'POST',
    body: JSON.stringify({ from_year, to_year, token, answer })
  }),
}

export const api = { login, logout, getProfile, users, stats, feedback, config, cycle, pending, submissions, logs, announcements, ai, export: exportData, marks, workflow, designations, workflowTemplates, profile, developer }
