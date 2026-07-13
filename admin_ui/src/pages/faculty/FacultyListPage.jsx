import { useState, useCallback, useRef, useEffect, useMemo, memo } from 'react';
import { useNavigate } from 'react-router-dom';
import { C } from '../../constants/colors';
import { api } from '../../api/client';
import { logAction } from '../../utils/activityLog';
import { normalizeUsers } from '../../api/normalizers';
import { useFetch } from '../../hooks/useFetch';
import { Loading, ApiError } from '../../components/LoadingState';
import { inp, lbl, pBtn } from '../../constants/styleTokens';
import { SCHOOLS } from '../../constants/schools';
import { I } from '../../components/icons';
import Badge from '../../components/Badge';
import Av from '../../components/Av';
import PageHead from '../../components/PageHead';

// ── Role config ────────────────────────────────────────────────────────────────
const ROLE_META = {
  faculty:            { label: 'Faculty',           color: C.accent  },
  hod:                { label: 'HOD',               color: '#a78bfa' },
  director:           { label: 'Director',          color: C.yellow  },
  dean:               { label: 'Dean',              color: C.green   },
  vc:                 { label: 'VC',                color: '#f472b6' },
  registrar:          { label: 'Registrar',         color: '#22d3ee' },
  non_teaching_staff: { label: 'Non-Teaching',      color: C.orange  },
  reporting_officer:  { label: 'Reporting Officer', color: '#fb923c' },
  center_head:        { label: 'Center Head',       color: '#a78bfa' },
  section_head:       { label: 'Section Head',      color: C.yellow  },
  staff:              { label: 'Staff',             color: C.muted   },
  admin:              { label: 'Admin',             color: C.green   },
  hr:                 { label: 'HR',                color: C.yellow  },
};
function roleMeta(r) { return ROLE_META[r] ?? { label: r ?? 'Unknown', color: C.muted }; }

const PAGE_SIZE = 25;

// ── Small helpers ──────────────────────────────────────────────────────────────
function initials(name) {
  return (name ?? '').split(' ').map(w => w[0]).filter(Boolean).slice(0, 2).join('').toUpperCase() || '?';
}

function RolePill({ role }) {
  const { label, color } = roleMeta(role);
  return (
    <span style={{
      display: 'inline-block', padding: '3px 9px', borderRadius: 20,
      fontSize: 11, fontWeight: 600, letterSpacing: .2,
      background: `${color}15`, color, border: `1px solid ${color}28`,
      whiteSpace: 'nowrap',
    }}>
      {label}
    </span>
  );
}

function IconBtn({ icon: Icon, label, color = C.accent, bg, border, onClick, disabled, loading }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      title={label}
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: 32, height: 32, borderRadius: 8, border: border ?? `1px solid ${color}28`,
        background: hover ? `${color}20` : (bg ?? `${color}0e`),
        color, cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? .4 : 1, transition: 'all .15s', flexShrink: 0,
      }}
    >
      {loading ? <span style={{ fontSize: 9 }}>…</span> : <Icon size={13} />}
    </button>
  );
}

// ── Multi-select dropdown ──────────────────────────────────────────────────────
const MultiSelectDropdown = memo(function MultiSelectDropdown({ noun, options, selected, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const h = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [open]);
  const toggle = val => { const n = new Set(selected); n.has(val) ? n.delete(val) : n.add(val); onChange(n); };
  const active = selected.size > 0;
  const label = active
    ? (selected.size === 1 ? (options.find(o => selected.has(o.value))?.label ?? [...selected][0]) : `${selected.size} ${noun}`)
    : `All ${noun}`;
  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={() => setOpen(o => !o)} style={{
        display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 12px',
        borderRadius: 8, cursor: 'pointer', fontSize: 12, fontWeight: active ? 600 : 400,
        border: `1px solid ${active ? C.accent + '55' : 'rgba(255,255,255,.1)'}`,
        background: active ? `${C.accent}10` : 'rgba(255,255,255,.04)', color: active ? C.accent : C.subtle,
        whiteSpace: 'nowrap', minWidth: 120,
      }}>
        <span style={{ flex: 1, textAlign: 'left' }}>{label}</span>
        <span style={{ opacity: .4, fontSize: 9 }}>▾</span>
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, zIndex: 400,
          background: C.surf, border: '1px solid rgba(255,255,255,.12)',
          borderRadius: 10, boxShadow: '0 16px 40px rgba(0,0,0,.7)',
          minWidth: 220, maxHeight: 300, display: 'flex', flexDirection: 'column',
        }}>
          <div style={{ padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,.08)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: .7 }}>Filter by {noun}</span>
            {active && <button onClick={() => onChange(new Set())} style={{ fontSize: 11, color: C.accent, background: 'none', border: 'none', cursor: 'pointer', fontWeight: 700 }}>Clear</button>}
          </div>
          <div style={{ overflowY: 'auto', padding: '6px 0' }}>
            {options.map(opt => (
              <label key={opt.value} style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px', cursor: 'pointer',
                background: selected.has(opt.value) ? `${C.accent}14` : 'transparent',
                borderLeft: selected.has(opt.value) ? `2px solid ${C.accent}` : '2px solid transparent',
              }}>
                <input type="checkbox" checked={selected.has(opt.value)} onChange={() => toggle(opt.value)}
                  style={{ accentColor: C.accent, cursor: 'pointer', width: 14, height: 14, flexShrink: 0 }} />
                {opt.dot && <span style={{ width: 8, height: 8, borderRadius: '50%', background: opt.dot, flexShrink: 0 }} />}
                <span style={{ fontSize: 12, fontWeight: selected.has(opt.value) ? 600 : 400, color: selected.has(opt.value) ? C.text : C.muted }}>{opt.label}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});

// ── Pagination ─────────────────────────────────────────────────────────────────
function getPageNums(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const out = [1];
  if (current > 3) out.push('…');
  for (let p = Math.max(2, current - 1); p <= Math.min(total - 1, current + 1); p++) out.push(p);
  if (current < total - 2) out.push('…');
  out.push(total);
  return out;
}

// ── Edit drawer ────────────────────────────────────────────────────────────────
function EditDrawer({ user: f, onClose, onSaved }) {
  const profile = api.getProfile();
  const isSuperAdmin = profile?.appraisal_role === 'super_admin';
  const isNT = f.role === 'non_teaching_staff';
  const [form, setForm]   = useState({
    full_name:               f.name === f.email ? '' : f.name,
    department:              f.dept === '—' ? '' : f.dept,
    school:                  f.school === '—' ? '' : f.school,
    phone:                   f.phone === '—' ? '' : f.phone,
    appraisal_role:          f.role ?? 'faculty',
    reports_to_registrar:    f.reports_to_registrar ?? false,
    reporting_officer_email: f.reporting_officer_email ?? '',
    registrar_email:         f.registrar_email ?? '',
  });
  const [saving,         setSaving]         = useState(false);
  const [err,            setErr]            = useState(null);
  const [ros,            setRos]            = useState([]);
  const [registrarsList, setRegistrarsList] = useState([]);

  useEffect(() => {
    if (!isNT) return;
    Promise.all([api.users.reportingOfficers(), api.users.registrars()])
      .then(([roData, regData]) => {
        setRos(Array.isArray(roData)  ? roData  : []);
        setRegistrarsList(Array.isArray(regData) ? regData : []);
      })
      .catch(() => {});
  }, [isNT]);

  const set = k => e => setForm(p => ({ ...p, [k]: e.target.value }));

  async function save() {
    setSaving(true); setErr(null);
    try {
      await api.users.update(f.email, form);
      logAction('user_updated', 'User Updated', `${form.full_name || f.email} (${form.appraisal_role || f.role})`, { name: form.full_name, email: f.email, role: form.appraisal_role || f.role });
      onSaved();
      onClose();
    }
    catch (e) { setErr(e.message); }
    finally { setSaving(false); }
  }

  const rm = roleMeta(f.role);

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 900, background: 'rgba(0,0,0,.45)', backdropFilter: 'blur(3px)' }} />
      <div style={{
        position: 'fixed', top: 0, right: 0, height: '100vh', width: 360,
        zIndex: 901, display: 'flex', flexDirection: 'column',
        background: C.surf, borderLeft: '1px solid rgba(255,255,255,.08)',
        boxShadow: '-24px 0 60px rgba(0,0,0,.55)',
        animation: 'drawerIn .22s cubic-bezier(.22,1,.36,1)',
      }}>
        {/* Header */}
        <div style={{ padding: '18px 20px', borderBottom: '1px solid rgba(255,255,255,.07)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15, color: C.text }}>Edit User</div>
            <div style={{ fontSize: 11, color: C.muted, marginTop: 2, fontFamily: "'JetBrains Mono',monospace" }}>{f.email}</div>
          </div>
          <button onClick={onClose} style={{ width: 30, height: 30, borderRadius: 8, border: '1px solid rgba(255,255,255,.1)', background: 'transparent', cursor: 'pointer', color: C.muted, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>×</button>
        </div>

        {/* Avatar strip */}
        <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,.05)', display: 'flex', alignItems: 'center', gap: 13, background: 'rgba(255,255,255,.02)', flexShrink: 0 }}>
          <Av init={initials(f.name)} color={rm.color} size={42} />
          <div>
            <div style={{ fontWeight: 600, fontSize: 13, color: C.text }}>{f.name}</div>
            <RolePill role={f.role} />
          </div>
        </div>

        {/* Form */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {[
              { l: 'Full Name',  k: 'full_name',  placeholder: 'e.g. Dr. Ravi Kumar' },
              { l: 'Phone',      k: 'phone',      placeholder: '+91 98...' },
              { l: 'Department', k: 'department', placeholder: 'e.g. Computer Science' },
            ].map(({ l, k, placeholder }) => (
              <div key={k}>
                <label style={lbl}>{l}</label>
                <input className="ifield" style={inp} placeholder={placeholder} value={form[k] ?? ''} onChange={set(k)} />
              </div>
            ))}

            <div>
              <label style={lbl}>Role</label>
              <select className="ifield" style={inp} value={form.appraisal_role} onChange={set('appraisal_role')}>
                {Object.entries(ROLE_META)
                  .filter(([val]) => {
                    if (['vc', 'admin', 'hr'].includes(val)) {
                      return isSuperAdmin;
                    }
                    return true;
                  })
                  .map(([val, { label }]) => (
                    <option key={val} value={val}>{label}</option>
                  ))
                }
              </select>
            </div>

            {form.appraisal_role === 'non_teaching_staff' && (
              <>
                <div>
                  <label style={lbl}>Reporting Officer</label>
                  <select className="ifield" style={inp}
                    value={form.reporting_officer_email}
                    onChange={e => setForm(p => ({ ...p, reporting_officer_email: e.target.value }))}>
                    <option value="">— None / Not Required —</option>
                    {ros.map(r => (
                      <option key={r.email} value={r.email}>
                        {r.full_name || r.email}{r.department ? ` — ${r.department}` : ''}
                      </option>
                    ))}
                  </select>
                  <div style={{ fontSize: 10, color: C.muted, marginTop: 4 }}>
                    Leave blank if the approval chain skips the RO step.
                  </div>
                </div>
                <div>
                  <label style={lbl}>Registrar</label>
                  <select className="ifield" style={inp}
                    value={form.registrar_email}
                    onChange={e => setForm(p => ({ ...p, registrar_email: e.target.value }))}>
                    <option value="">— None / Not Required —</option>
                    {registrarsList.map(r => (
                      <option key={r.email} value={r.email}>
                        {r.full_name || r.email}{r.department ? ` — ${r.department}` : ''}
                      </option>
                    ))}
                  </select>
                  <div style={{ fontSize: 10, color: C.muted, marginTop: 4 }}>
                    Leave blank if the approval chain skips the Registrar step.
                  </div>
                </div>
              </>
            )}

            <div>
              <label style={lbl}>School</label>
              <select className="ifield" style={inp} value={form.school ?? ''} onChange={set('school')}>
                <option value="">— None —</option>
                {SCHOOLS.map(s => <option key={s.code} value={s.code}>{s.full} ({s.code})</option>)}
              </select>
            </div>
          </div>

          {err && <div style={{ marginTop: 14, padding: '9px 12px', borderRadius: 8, fontSize: 12, color: C.red, background: 'rgba(248,113,113,.08)', border: '1px solid rgba(248,113,113,.2)' }}>{err}</div>}
        </div>

        {/* Footer */}
        <div style={{ padding: '14px 20px', borderTop: '1px solid rgba(255,255,255,.07)', display: 'flex', gap: 10, flexShrink: 0 }}>
          <button style={{ ...pBtn, flex: 1 }} onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
          <button onClick={onClose} style={{ padding: '9px 16px', background: 'transparent', color: C.muted, border: '1px solid rgba(255,255,255,.1)', borderRadius: 8, cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>
            Cancel
          </button>
        </div>
      </div>
    </>
  );
}

// ── Resolve effective workflow template for an NT staff member ─────────────────
function resolveTemplateName(f, assignments, templates) {
  const byEmail = assignments.find(a => a.staff_email === f.email);
  if (byEmail) return byEmail.template_name;
  const byRole = assignments.find(a => a.appraisal_role === f.role);
  if (byRole) return byRole.template_name;
  if (f.dept && f.dept !== '—') {
    const byDept = assignments.find(a => a.department === f.dept);
    if (byDept) return byDept.template_name;
  }
  const def = templates.find(t => t.is_default);
  return def ? def.name : null;
}

// ── User row ───────────────────────────────────────────────────────────────────
const UserRow = memo(function UserRow({ f, selected, onSelect, onEdit, onToggle, onDelete, verifying, removing, templateName, emailToName }) {
  const [hover, setHover] = useState(false);
  const rm       = roleMeta(f.role);
  const isActive = f.status === 'Active';
  const isNT     = f.role === 'non_teaching_staff';

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'grid',
        gridTemplateColumns: '44px 48px 1fr 150px 155px 105px 114px',
        alignItems: 'center',
        padding: '0 4px',
        borderRadius: 10,
        background: selected
          ? `${C.accent}0d`
          : hover ? 'rgba(255,255,255,.03)' : 'transparent',
        border: `1px solid ${selected ? `${C.accent}25` : hover ? 'rgba(255,255,255,.07)' : 'transparent'}`,
        transition: 'all .12s',
        cursor: 'default',
        minHeight: 62,
      }}
    >
      {/* Checkbox */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <input type="checkbox" checked={selected} onChange={onSelect}
          style={{ cursor: 'pointer', accentColor: C.accent, width: 14, height: 14 }} />
      </div>

      {/* Avatar */}
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <Av init={initials(f.name)} color={isActive ? rm.color : C.muted} size={36} />
      </div>

      {/* Name + email */}
      <div style={{ minWidth: 0, paddingRight: 12 }}>
        <div style={{ fontWeight: 600, fontSize: 13, color: C.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {f.name}
        </div>
        <div style={{ fontSize: 11, color: C.muted, marginTop: 1, fontFamily: "'JetBrains Mono',monospace", overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {f.email}
        </div>
        {/* NT staff path indicator */}
        {isNT && (
          <div style={{ marginTop: 3, display: 'flex', flexDirection: 'column', gap: 1 }}>
            {templateName && (
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10, fontWeight: 700, color: '#22d3ee', fontFamily: "'JetBrains Mono',monospace" }}>
                <span style={{ fontSize: 7 }}>●</span>
                {templateName}
              </div>
            )}
            {(f.reporting_officer_email || f.registrar_email) && (
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {f.reporting_officer_email && (
                  <span style={{ fontSize: 9, color: '#fb923c', fontWeight: 600 }}>
                    RO: {emailToName?.(f.reporting_officer_email) ?? f.reporting_officer_email}
                  </span>
                )}
                {f.registrar_email && (
                  <span style={{ fontSize: 9, color: '#22d3ee', fontWeight: 600 }}>
                    Reg: {emailToName?.(f.registrar_email) ?? f.registrar_email}
                  </span>
                )}
              </div>
            )}
            {isNT && !templateName && !f.reporting_officer_email && !f.registrar_email && (
              <span style={{ fontSize: 9, color: C.muted }}>No workflow assigned</span>
            )}
          </div>
        )}
      </div>

      {/* Role */}
      <div style={{ paddingRight: 10 }}>
        <RolePill role={f.role} />
      </div>

      {/* School / Dept */}
      <div style={{ minWidth: 0, paddingRight: 10 }}>
        {f.school !== '—' ? (
          <>
            <div style={{ fontSize: 12, fontWeight: 700, color: C.accent, fontFamily: "'JetBrains Mono',monospace", overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {f.school}
            </div>
            {f.dept !== '—' && (
              <div style={{ fontSize: 11, color: C.muted, marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {f.dept}
              </div>
            )}
          </>
        ) : <span style={{ color: 'rgba(255,255,255,.15)', fontSize: 18 }}>—</span>}
      </div>

      {/* Status */}
      <div>
        <Badge color={isActive ? 'green' : 'red'} dot>{f.status}</Badge>
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
        <IconBtn icon={I.edit}  label="Edit user"   color={C.accent}  onClick={onEdit} />
        <IconBtn
          icon={I.check}
          label={isActive ? 'Deactivate' : 'Activate'}
          color={isActive ? C.yellow : C.green}
          onClick={onToggle}
          loading={verifying}
        />
        <IconBtn icon={I.trash} label="Delete user" color={C.red}
          bg="rgba(248,113,113,.08)" border="1px solid rgba(248,113,113,.25)"
          onClick={onDelete} loading={removing}
        />
      </div>
    </div>
  );
});

// ── Main page ──────────────────────────────────────────────────────────────────
export default function FacultyListPage() {
  const navigate = useNavigate();

  const [search,          setSearch]         = useState('');
  const [statusFilter,    setStatusFilter]   = useState('All');
  const [selectedSchools, setSelectedSchools]= useState(new Set());
  const [selectedRoles,   setSelectedRoles]  = useState(new Set());
  const [tick,            setTick]           = useState(0);
  const [selected,        setSelected]       = useState(new Set());
  const [page,            setPage]           = useState(1);

  const [editing,       setEditing]      = useState(null);
  const [verifying,     setVerifying]    = useState(null);
  const [removingEmail, setRemovingEmail]= useState(null);
  const [bulkRemoving,  setBulkRemoving] = useState(false);
  const [removeErr,     setRemoveErr]    = useState(null);

  const refresh = useCallback(() => setTick(t => t + 1), []);
  const { data: raw, loading, error } = useFetch(() => api.users.list(), [tick]);
  const { data: assignmentsRaw }      = useFetch(() => api.workflowTemplates.listAssignments(), [tick]);
  const { data: templatesRaw }        = useFetch(() => api.workflowTemplates.list(), [tick]);
  const profile    = api.getProfile();
  const isSuperAdmin = profile?.appraisal_role === 'super_admin';
  const users      = useMemo(() => normalizeUsers(raw, isSuperAdmin), [raw, isSuperAdmin]);
  const assignments = useMemo(() => assignmentsRaw ?? [], [assignmentsRaw]);
  const templates   = useMemo(() => templatesRaw   ?? [], [templatesRaw]);
  const emailToName  = useMemo(() => {
    const m = new Map(users.map(u => [u.email, u.name]));
    return (email) => m.get(email) ?? null;
  }, [users]);

  const rows = useMemo(() => {
    const q = search.toLowerCase();
    return users.filter(f =>
      (selectedSchools.size === 0 || selectedSchools.has(f.school)) &&
      (selectedRoles.size === 0   || selectedRoles.has(f.role))     &&
      (statusFilter === 'All'     || f.status === statusFilter)      &&
      (!q || f.name.toLowerCase().includes(q) || f.email.toLowerCase().includes(q))
    );
  }, [users, selectedSchools, selectedRoles, statusFilter, search]);

  const { totalPages, safePage, pageRows } = useMemo(() => {
    const total = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    const safe  = Math.min(page, total);
    return { totalPages: total, safePage: safe, pageRows: rows.slice((safe - 1) * PAGE_SIZE, safe * PAGE_SIZE) };
  }, [rows, page]);

  useEffect(() => { setPage(1); }, [search, selectedSchools, selectedRoles, statusFilter]);

  // Selection
  const visEmails     = pageRows.map(r => r.email);
  const selVisible    = visEmails.filter(e => selected.has(e));
  const allChecked    = visEmails.length > 0 && selVisible.length === visEmails.length;
  const someChecked   = selVisible.length > 0 && !allChecked;
  const toggleRow     = email => setSelected(prev => { const n = new Set(prev); n.has(email) ? n.delete(email) : n.add(email); return n; });
  const toggleAll     = () => {
    if (allChecked) setSelected(prev => { const n = new Set(prev); visEmails.forEach(e => n.delete(e)); return n; });
    else            setSelected(prev => new Set([...prev, ...visEmails]));
  };
  const clearSel = () => setSelected(new Set());

  // Actions
  const handleVerify = async (f, value) => {
    setVerifying(f.email);
    try {
      await api.users.update(f.email, { is_verified: value });
      logAction(value ? 'user_activated' : 'user_deactivated', value ? 'User Activated' : 'User Deactivated', `${f.name || f.email} (${f.role})`, { name: f.name, email: f.email, role: f.role });
      refresh();
    }
    catch (e) { setRemoveErr(e.message); }
    finally { setVerifying(null); }
  };

  const handleRemoveOne = async (f) => {
    if (!window.confirm(`Delete "${f.name}"?\n\nThis will permanently remove the user and all their appraisal data. This cannot be undone.`)) return;
    setRemovingEmail(f.email); setRemoveErr(null);
    try {
      await api.users.remove(f.email);
      logAction('user_deleted', 'User Deleted', `${f.name || f.email} (${f.role})`, { name: f.name, email: f.email, role: f.role });
      setSelected(prev => { const n = new Set(prev); n.delete(f.email); return n; });
      refresh();
    } catch (e) { setRemoveErr(e.message); }
    finally { setRemovingEmail(null); }
  };

  const handleBulkRemove = async () => {
    const targets = [...selected];
    if (!targets.length) return;
    const names = targets.map(email => { const u = users.find(u => u.email === email); return `• ${u ? u.name : email}`; }).join('\n');
    if (!window.confirm(`Permanently delete ${targets.length} user${targets.length > 1 ? 's' : ''}?\n\n${names}\n\nThis cannot be undone.`)) return;
    setBulkRemoving(true); setRemoveErr(null);
    const results = await Promise.allSettled(targets.map(email => api.users.remove(email)));
    const failed = results.filter(r => r.status === 'rejected');
    
    // Log successful deletions
    targets.forEach((email, i) => {
      if (results[i].status === 'fulfilled') {
        const u = users.find(u => u.email === email);
        logAction('user_deleted', 'User Deleted', `${u ? u.name : email}`, { name: u ? u.name : '', email });
      }
    });

    clearSel();
    if (failed.length) setRemoveErr(`${failed.length} deletion(s) failed: ${failed[0].reason?.message ?? ''}`);
    refresh(); setBulkRemoving(false);
  };

  // Print
  const handlePrint = () => {
    const now = new Date().toLocaleString('en-US', { month: 'long', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    const tableRows = rows.map((f, i) => `<tr class="${i % 2 ? 'alt' : ''}"><td class="num">${i + 1}</td><td><div class="name">${f.name}</div><div class="em">${f.email}</div></td><td><span class="badge">${roleMeta(f.role).label}</span></td><td>${f.school !== '—' ? f.school : '—'}</td><td>${f.dept !== '—' ? f.dept : '—'}</td><td><span class="s ${f.status === 'Active' ? 'act' : 'inact'}">${f.status}</span></td></tr>`).join('');
    const w = window.open('', '_blank', 'width=960,height=720');
    w.document.write(`<!DOCTYPE html><html><head><title>User List</title><style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,sans-serif;color:#111;font-size:12px;background:#fff}.page{padding:28px 32px}h1{font-size:17px;font-weight:800;margin-bottom:4px}.sub{font-size:11px;color:#6b7280;margin-bottom:18px}table{width:100%;border-collapse:collapse}thead tr{background:#f9fafb}th{padding:7px 10px;font-size:9px;font-weight:700;color:#6b7280;text-transform:uppercase;text-align:left;border-bottom:2px solid #e5e7eb}td{padding:7px 10px;border-bottom:1px solid #f3f4f6;vertical-align:top}tr.alt td{background:#fafafa}.num{text-align:center;color:#9ca3af;width:28px}.name{font-weight:700}.em{font-size:10px;color:#6b7280;font-family:monospace}.badge{display:inline-block;padding:2px 7px;border-radius:10px;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;font-size:9px;font-weight:700}.s{display:inline-block;padding:2px 7px;border-radius:10px;font-size:9px;font-weight:700}.act{background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0}.inact{background:#fff7ed;color:#c2410c;border:1px solid #fed7aa}@media print{@page{margin:10mm;size:A4 landscape}}</style></head><body><div class="page"><h1>User List — DYP Faculty Appraisal</h1><div class="sub">Generated: ${now} · ${rows.length} records</div><table><thead><tr><th>#</th><th>Name / Email</th><th>Role</th><th>School</th><th>Dept</th><th>Status</th></tr></thead><tbody>${tableRows}</tbody></table></div></body></html>`);
    w.document.close(); w.focus(); setTimeout(() => w.print(), 400);
  };

  // Options
  const activeCount     = users.filter(f => f.status === 'Active').length;
  const unverifiedCount = users.filter(f => f.status !== 'Active').length;
  const schoolOptions   = SCHOOLS.map(s => ({ value: s.code, label: `${s.code} — ${s.full}` }));
  const roleOptions     = Object.entries(ROLE_META).map(([value, { label, color }]) => ({ value, label, dot: color }));
  const anyFilter       = selectedSchools.size + selectedRoles.size + (statusFilter !== 'All' ? 1 : 0) + (search ? 1 : 0);

  return (
    <div className="page-enter">
      <style>{`
        @keyframes drawerIn { from { transform: translateX(100%) } to { transform: translateX(0) } }
      `}</style>

      {editing && (
        <EditDrawer user={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); refresh(); }} />
      )}

      <PageHead
        title="User List"
        sub={anyFilter > 0 ? `Showing ${rows.length} of ${users.length} users` : `${users.length} total users`}
      />

      {loading && <Loading />}
      {error   && <ApiError message={error} />}

      {!loading && !error && (
        <>
          {/* ── Stat chips ──────────────────────────────────────────────── */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
            {[
              { label: 'Total Users', value: users.length,    color: C.accent  },
              { label: 'Active',      value: activeCount,     color: C.green   },
              { label: 'Unverified',  value: unverifiedCount, color: C.yellow  },
            ].map(s => (
              <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px', borderRadius: 10, background: `${s.color}0d`, border: `1px solid ${s.color}22` }}>
                <div style={{ width: 7, height: 7, borderRadius: '50%', background: s.color }} />
                <span style={{ fontSize: 12, color: C.muted }}>{s.label}</span>
                <span style={{ fontSize: 18, fontWeight: 800, color: s.color, fontFamily: "'JetBrains Mono',monospace" }}>{s.value}</span>
              </div>
            ))}
          </div>

          {removeErr && (
            <div style={{ marginBottom: 14, padding: '10px 14px', borderRadius: 8, fontSize: 13, color: C.red, background: 'rgba(248,113,113,.08)', border: '1px solid rgba(248,113,113,.2)' }}>
              {removeErr}
            </div>
          )}

          {/* ── Main card ───────────────────────────────────────────────── */}
          <div style={{ background: C.surf, borderRadius: 14, border: '1px solid rgba(255,255,255,.07)', overflow: 'hidden' }}>

            {/* Toolbar */}
            <div style={{ padding: '14px 16px', borderBottom: '1px solid rgba(255,255,255,.06)', display: 'flex', flexDirection: 'column', gap: 10 }}>

              {/* Row 1: search + actions */}
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <div style={{ position: 'relative', flex: 1 }}>
                  <div style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', opacity: .3, pointerEvents: 'none' }}>
                    <I.search size={13} />
                  </div>
                  <input className="ifield" placeholder="Search by name or email…" value={search} onChange={e => setSearch(e.target.value)}
                    style={{ ...inp, paddingLeft: 34, fontSize: 13 }} />
                </div>
                <button onClick={handlePrint} disabled={rows.length === 0} style={{
                  padding: '8px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 5, color: C.subtle,
                  background: 'transparent', border: '1px solid rgba(255,255,255,.1)',
                  opacity: rows.length === 0 ? .35 : 1, whiteSpace: 'nowrap',
                }}>
                  <I.dl size={12} /> Print All
                </button>
                <button style={{ ...pBtn, whiteSpace: 'nowrap' }} onClick={() => navigate('/faculty/add')}>
                  <I.addUser size={13} /> Add User
                </button>
              </div>

              {/* Row 2: filters + status tabs + count */}
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <MultiSelectDropdown noun="Schools" options={schoolOptions} selected={selectedSchools} onChange={setSelectedSchools} />
                <MultiSelectDropdown noun="Roles"   options={roleOptions}   selected={selectedRoles}   onChange={setSelectedRoles} />

                <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,.1)', margin: '0 2px' }} />

                {[
                  { key: 'All', count: users.length },
                  { key: 'Active', count: activeCount },
                  { key: 'Unverified', count: unverifiedCount },
                ].map(({ key, count }) => {
                  const isActive = statusFilter === key;
                  return (
                    <button key={key} onClick={() => setStatusFilter(key)} style={{
                      padding: '6px 12px', borderRadius: 7, whiteSpace: 'nowrap',
                      fontSize: 12, fontWeight: isActive ? 700 : 500, cursor: 'pointer',
                      border: `1px solid ${isActive ? C.accent : 'rgba(255,255,255,.08)'}`,
                      background: isActive ? `${C.accent}15` : 'transparent',
                      color: isActive ? C.accent : C.subtle,
                    }}>
                      {key} <span style={{ opacity: .6 }}>({count})</span>
                    </button>
                  );
                })}

                {anyFilter > 0 && (
                  <button onClick={() => { setSearch(''); setSelectedSchools(new Set()); setSelectedRoles(new Set()); setStatusFilter('All'); }}
                    style={{ padding: '5px 10px', borderRadius: 6, border: '1px solid rgba(248,113,113,.25)', background: 'rgba(248,113,113,.08)', color: C.red, fontSize: 11, fontWeight: 600, cursor: 'pointer' }}>
                    Clear filters
                  </button>
                )}

                <span style={{ marginLeft: 'auto', fontSize: 12, color: C.muted, whiteSpace: 'nowrap' }}>
                  {rows.length > PAGE_SIZE
                    ? `${(safePage - 1) * PAGE_SIZE + 1}–${Math.min(safePage * PAGE_SIZE, rows.length)} of ${rows.length}`
                    : `${rows.length} ${rows.length === 1 ? 'record' : 'records'}`}
                </span>
              </div>
            </div>

            {/* Bulk action bar */}
            {selected.size > 0 && (
              <div style={{ padding: '10px 16px', background: 'rgba(248,113,113,.06)', borderBottom: '1px solid rgba(248,113,113,.15)', display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: C.red, flex: 1 }}>
                  {selected.size} user{selected.size > 1 ? 's' : ''} selected
                </span>
                <button onClick={handleBulkRemove} disabled={bulkRemoving} style={{ padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 600, cursor: 'pointer', color: C.red, background: 'rgba(248,113,113,.12)', border: '1px solid rgba(248,113,113,.3)', display: 'flex', alignItems: 'center', gap: 6, opacity: bulkRemoving ? .5 : 1 }}>
                  <I.trash size={12} />
                  {bulkRemoving ? 'Deleting…' : `Delete ${selected.size}`}
                </button>
                <button onClick={clearSel} style={{ padding: '6px 12px', borderRadius: 7, fontSize: 12, fontWeight: 600, cursor: 'pointer', color: C.muted, background: 'transparent', border: '1px solid rgba(255,255,255,.1)' }}>
                  Clear
                </button>
              </div>
            )}

            {/* Column header */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '44px 48px 1fr 150px 155px 105px 114px',
              padding: '8px 4px',
              borderBottom: '1px solid rgba(255,255,255,.06)',
              background: 'rgba(255,255,255,.015)',
            }}>
              {/* Select all */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <input
                  type="checkbox"
                  checked={allChecked}
                  ref={el => { if (el) el.indeterminate = someChecked; }}
                  onChange={toggleAll}
                  style={{ cursor: 'pointer', accentColor: C.accent, width: 14, height: 14 }}
                />
              </div>
              {['', 'User', 'Role', 'School / Dept', 'Status', 'Actions'].map((h, i) => (
                <div key={i} style={{ fontSize: 10, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: .6, paddingRight: 10, display: 'flex', alignItems: 'center' }}>
                  {h}
                </div>
              ))}
            </div>

            {/* Rows */}
            <div style={{ padding: '6px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
              {pageRows.length === 0 ? (
                <div style={{ padding: '48px 0', textAlign: 'center', color: C.muted, fontSize: 13 }}>
                  {anyFilter > 0 ? 'No users match the current filters.' : 'No users yet. Click "Add User" to get started.'}
                </div>
              ) : pageRows.map(f => (
                <UserRow
                  key={f.email}
                  f={f}
                  selected={selected.has(f.email)}
                  onSelect={() => toggleRow(f.email)}
                  onEdit={() => setEditing(f)}
                  onToggle={() => handleVerify(f, f.status !== 'Active')}
                  onDelete={() => handleRemoveOne(f)}
                  verifying={verifying === f.email}
                  removing={removingEmail === f.email}
                  templateName={f.role === 'non_teaching_staff' ? resolveTemplateName(f, assignments, templates) : null}
                  emailToName={emailToName}
                />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderTop: '1px solid rgba(255,255,255,.06)' }}>
                <span style={{ fontSize: 12, color: C.muted }}>Page {safePage} of {totalPages}</span>
                <div style={{ display: 'flex', gap: 4 }}>
                  <button onClick={() => setPage(p => p - 1)} disabled={safePage === 1}
                    style={{ minWidth: 30, height: 30, padding: '0 8px', borderRadius: 7, fontSize: 13, cursor: safePage === 1 ? 'default' : 'pointer', border: '1px solid rgba(255,255,255,.1)', background: 'transparent', color: safePage === 1 ? 'rgba(255,255,255,.2)' : C.subtle }}>
                    ‹
                  </button>
                  {getPageNums(safePage, totalPages).map((p, i) =>
                    p === '…'
                      ? <span key={`e${i}`} style={{ padding: '0 4px', color: C.muted, fontSize: 13, lineHeight: '30px' }}>…</span>
                      : <button key={p} onClick={() => setPage(p)}
                          style={{ minWidth: 30, height: 30, padding: '0 8px', borderRadius: 7, fontSize: 12, cursor: 'pointer', fontWeight: p === safePage ? 700 : 500, border: `1px solid ${p === safePage ? C.accent : 'rgba(255,255,255,.1)'}`, background: p === safePage ? `${C.accent}20` : 'transparent', color: p === safePage ? C.accent : C.subtle }}>
                          {p}
                        </button>
                  )}
                  <button onClick={() => setPage(p => p + 1)} disabled={safePage === totalPages}
                    style={{ minWidth: 30, height: 30, padding: '0 8px', borderRadius: 7, fontSize: 13, cursor: safePage === totalPages ? 'default' : 'pointer', border: '1px solid rgba(255,255,255,.1)', background: 'transparent', color: safePage === totalPages ? 'rgba(255,255,255,.2)' : C.subtle }}>
                    ›
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
