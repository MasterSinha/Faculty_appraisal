import { useState, useCallback, useMemo } from 'react';
import { C } from '../../constants/colors';
import { api } from '../../api/client';
import { useFetch } from '../../hooks/useFetch';
import { logAction } from '../../utils/activityLog';
import { Loading, ApiError } from '../../components/LoadingState';
import { inp, lbl, pBtn } from '../../constants/styleTokens';
import { I } from '../../components/icons';
import Badge from '../../components/Badge';
import PageHead from '../../components/PageHead';
import { SCHOOLS } from '../../constants/schools';

// ── Constants ──────────────────────────────────────────────────────────────────

const ROLE_OPTIONS = [
  { value: 'all',                label: 'Everyone',     color: C.accent  },
  { value: 'faculty',            label: 'Faculty',      color: '#a78bfa' },
  { value: 'hod',                label: 'HOD',          color: C.yellow  },
  { value: 'director',           label: 'Director',     color: C.green   },
  { value: 'dean',               label: 'Dean',         color: '#22d3ee' },
  { value: 'non_teaching_staff', label: 'Non-Teaching', color: C.orange  },
  { value: 'registrar',          label: 'Registrar',    color: '#f472b6' },
];

// ── Helpers ────────────────────────────────────────────────────────────────────

function toArr(str) {
  const parts = (str ?? 'all').split(',').map(s => s.trim()).filter(Boolean);
  return parts.length ? parts : ['all'];
}
function toStr(arr) { return arr.length ? arr.join(',') : 'all'; }
function isSchoolCode(t) { return SCHOOLS.some(s => s.code === t); }
function tokenLabel(t) { return ROLE_OPTIONS.find(r => r.value === t)?.label ?? t; }
function tokenColor(t) {
  if (isSchoolCode(t)) return C.yellow;
  return ROLE_OPTIONS.find(r => r.value === t)?.color ?? C.accent;
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

// ── ToggleSwitch ───────────────────────────────────────────────────────────────

function ToggleSwitch({ checked, onChange }) {
  return (
    <div onClick={onChange} style={{
      width: 38, height: 22, borderRadius: 11, position: 'relative', cursor: 'pointer',
      background: checked ? C.green : 'rgba(255,255,255,.1)',
      border: `1.5px solid ${checked ? C.green : 'rgba(255,255,255,.12)'}`,
      transition: 'all .2s', flexShrink: 0,
    }}>
      <div style={{
        position: 'absolute', top: 2, left: checked ? 17 : 2,
        width: 14, height: 14, borderRadius: '50%', background: '#fff',
        transition: 'left .2s', boxShadow: '0 1px 4px rgba(0,0,0,.35)',
      }} />
    </div>
  );
}

// ── AudiencePicker ─────────────────────────────────────────────────────────────

function AudiencePicker({ selected, onChange }) {
  const selectedSchools = selected.filter(s => isSchoolCode(s));
  const selectedRoles   = selected.filter(s => !isSchoolCode(s) && s !== 'all');
  const currentSchool   = selectedSchools.length === 1 ? selectedSchools[0] : 'all';

  const handleSchoolChange = (code) => {
    if (code === 'all') onChange(selectedRoles.length ? selectedRoles : ['all']);
    else onChange([code, ...selectedRoles]);
  };

  const toggleRole = (role) => {
    const newRoles = selectedRoles.includes(role)
      ? selectedRoles.filter(r => r !== role)
      : [...selectedRoles, role];
    const schools = currentSchool === 'all' ? [] : [currentSchool];
    onChange(newRoles.length === 0 && schools.length === 0 ? ['all'] : [...schools, ...newRoles]);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
      {/* School select */}
      <select
        className="ifield"
        value={currentSchool}
        onChange={e => handleSchoolChange(e.target.value)}
        style={{
          width: '100%', padding: '7px 11px', borderRadius: 7, fontSize: 12,
          fontWeight: 600, cursor: 'pointer', appearance: 'none',
          background: currentSchool !== 'all' ? `${C.yellow}0d` : 'rgba(255,255,255,.04)',
          border: `1px solid ${currentSchool !== 'all' ? `${C.yellow}30` : 'rgba(255,255,255,.08)'}`,
          color: currentSchool !== 'all' ? C.yellow : C.text, outline: 'none',
        }}>
        <option value="all">All Schools</option>
        {SCHOOLS.map(s => (
          <option key={s.code} value={s.code}>{s.code} — {s.full}</option>
        ))}
      </select>

      {/* Role chips — single horizontal row, scrollable */}
      <div style={{
        display: 'flex', gap: 5, overflowX: 'auto', paddingBottom: 2,
        scrollbarWidth: 'none', msOverflowStyle: 'none',
      }}>
        {ROLE_OPTIONS.filter(r => r.value !== 'all').map(r => {
          const on = selectedRoles.includes(r.value);
          return (
            <button key={r.value} type="button" className="act-btn"
              onClick={() => toggleRole(r.value)}
              style={{
                padding: '3px 9px', borderRadius: 5, fontSize: 11, fontWeight: 600,
                cursor: 'pointer', transition: 'all .15s', flexShrink: 0,
                border: `1px solid ${on ? r.color + '45' : 'rgba(255,255,255,.08)'}`,
                background: on ? `${r.color}18` : 'rgba(255,255,255,.03)',
                color: on ? r.color : C.muted,
              }}>
              {r.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── AudienceTokens (read-only display) ────────────────────────────────────────

function AudienceTokens({ audience }) {
  const tokens = toArr(audience);
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {tokens.map(t => {
        const color = tokenColor(t);
        return (
          <span key={t} style={{
            fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 10,
            fontFamily: "'JetBrains Mono',monospace",
            background: `${color}14`, color,
            border: `1px solid ${color}25`,
          }}>{tokenLabel(t)}</span>
        );
      })}
    </div>
  );
}

// ── NoticeRow ──────────────────────────────────────────────────────────────────

function NoticeRow({ n, onEdit, onDelete, deleting }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div style={{
      display: 'flex', gap: 0, borderRadius: 12, overflow: 'hidden',
      background: 'rgba(255,255,255,.025)',
      border: '1px solid rgba(255,255,255,.06)',
      transition: 'border-color .15s',
    }}>
      {/* Left accent bar */}
      <div style={{
        width: 3, flexShrink: 0,
        background: n.is_active
          ? 'linear-gradient(180deg,#34d399,#059669)'
          : 'rgba(255,255,255,.1)',
      }} />

      <div style={{ flex: 1, padding: '14px 16px', minWidth: 0 }}>
        {/* Top row: title + badge */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 6 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 700, fontSize: 13, color: C.text, lineHeight: 1.35,
              marginBottom: 5 }}>
              {n.title}
            </div>
            <AudienceTokens audience={n.audience} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
            <Badge color={n.is_active ? 'green' : 'red'} dot>
              {n.is_active ? 'Live' : 'Off'}
            </Badge>
          </div>
        </div>

        {/* Body */}
        {n.body && (
          <div
            onClick={() => setExpanded(e => !e)}
            style={{
              fontSize: 12, color: C.muted, lineHeight: 1.65, marginTop: 8,
              cursor: 'pointer',
              ...(expanded ? {} : {
                display: '-webkit-box', WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical', overflow: 'hidden',
              }),
            }}>
            {n.body}
          </div>
        )}

        {/* Footer */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginTop: 10, paddingTop: 10, borderTop: '1px solid rgba(255,255,255,.04)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 11, color: C.muted,
              fontFamily: "'JetBrains Mono',monospace" }}>{fmtDate(n.created_at)}</span>
            {n.created_by && (
              <span style={{ fontSize: 11, color: C.muted }}>by {n.created_by}</span>
            )}
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="act-btn" onClick={onEdit}
              style={{ width: 30, height: 28, borderRadius: 7, cursor: 'pointer',
                background: `${C.accent}10`, border: `1px solid ${C.accent}25`,
                color: C.accent, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <I.edit size={12} />
            </button>
            <button className="act-btn" onClick={onDelete} disabled={deleting}
              style={{ width: 30, height: 28, borderRadius: 7, cursor: 'pointer',
                color: C.red, background: 'rgba(248,113,113,.07)',
                border: '1px solid rgba(248,113,113,.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                opacity: deleting ? .5 : 1 }}>
              {deleting ? <span style={{ fontSize: 11 }}>…</span> : <I.trash size={12} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

const EMPTY = { title: '', body: '', audiences: ['all'], is_active: true, send_email: true };

export default function AnnouncementsPage() {
  const [form,        setForm]        = useState(EMPTY);
  const [saving,      setSaving]      = useState(false);
  const [status,      setStatus]      = useState(null);
  const [tick,        setTick]        = useState(0);
  const [deleting,    setDeleting]    = useState(null);
  const [editing,     setEditing]     = useState(null);
  const [editSaving,  setEditSaving]  = useState(false);
  const [editErr,     setEditErr]     = useState(null);
  const [filter] = useState('all');

  const refresh = useCallback(() => setTick(t => t + 1), []);

  const { data: raw, loading, error } = useFetch(() => api.announcements.list(), [tick]);
  const notices = Array.isArray(raw) ? raw : (raw?.announcements ?? raw?.items ?? []);

  const visible = useMemo(() => notices.filter(n => {
    if (filter === 'live' && !n.is_active) return false;
    if (filter === 'off'  &&  n.is_active) return false;
    return true;
  }), [notices, filter]);

  const handlePublish = async () => {
    if (!form.title.trim() || !form.body.trim()) {
      setStatus({ ok: false, msg: 'Title and message are required.' });
      return;
    }
    setSaving(true); setStatus(null);
    try {
      await api.announcements.create({
        title: form.title, body: form.body,
        audience: toStr(form.audiences), is_active: form.is_active,
        send_email: form.is_active && form.send_email,
      });
      setStatus({ ok: true, msg: 'Published successfully.' });
      logAction('announcement_created', 'Announcement Posted', form.title, { title: form.title });
      setForm(EMPTY);
      refresh();
    } catch (e) {
      setStatus({ ok: false, msg: e.message });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this announcement?')) return;
    setDeleting(id);
    try {
      const notice = notices.find(n => n.id === id);
      const title = notice ? notice.title : `ID ${id}`;
      await api.announcements.remove(id);
      logAction('announcement_deleted', 'Announcement Deleted', title, { title });
      refresh();
    }
    finally { setDeleting(null); }
  };

  const saveEdit = async () => {
    setEditSaving(true); setEditErr(null);
    try {
      const { id, audiences, ...rest } = editing;
      await api.announcements.update(id, { ...rest, audience: toStr(audiences) });
      logAction('announcement_updated', 'Announcement Updated', editing.title, { title: editing.title });
      setEditing(null); refresh();
    } catch (e) {
      setEditErr(e.message);
    } finally {
      setEditSaving(false);
    }
  };

  return (
    <div className="page-enter" style={{ overflow: 'hidden' }}>
      <style>{`@keyframes drawerIn{from{transform:translateX(100%)}to{transform:translateX(0)}}`}</style>

      {/* ── Edit drawer ─────────────────────────────────────────────────── */}
      {editing && (
        <>
          <div onClick={() => setEditing(null)} style={{
            position: 'fixed', inset: 0, zIndex: 900,
            background: 'rgba(0,0,0,.45)', backdropFilter: 'blur(3px)',
          }} />
          <div style={{
            position: 'fixed', top: 0, right: 0, height: '100vh', width: 400, zIndex: 901,
            display: 'flex', flexDirection: 'column',
            background: C.surf, borderLeft: '1px solid rgba(255,255,255,.08)',
            boxShadow: '-24px 0 60px rgba(0,0,0,.6)',
            animation: 'drawerIn .2s ease',
          }}>
            {/* Drawer header */}
            <div style={{ padding: '20px 24px', borderBottom: '1px solid rgba(255,255,255,.07)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 15, color: C.text }}>Edit Announcement</div>
                <div style={{ fontSize: 11, color: C.muted, marginTop: 2,
                  fontFamily: "'JetBrains Mono',monospace" }}>#{editing.id}</div>
              </div>
              <button className="act-btn" onClick={() => setEditing(null)} style={{
                width: 32, height: 32, borderRadius: 8, border: '1px solid rgba(255,255,255,.1)',
                background: 'transparent', cursor: 'pointer', color: C.muted, fontSize: 18,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>×</button>
            </div>

            {/* Drawer fields */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px',
              display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <label style={lbl}>Title</label>
                <input className="ifield" value={editing.title} style={inp}
                  onChange={e => setEditing(p => ({ ...p, title: e.target.value }))} />
              </div>

              <div>
                <label style={lbl}>Target Audience</label>
                <div style={{ padding: '14px', borderRadius: 10,
                  background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.07)' }}>
                  <AudiencePicker
                    selected={editing.audiences}
                    onChange={audiences => setEditing(p => ({ ...p, audiences }))}
                  />
                </div>
              </div>

              <div>
                <label style={lbl}>Message</label>
                <textarea className="ifield" value={editing.body} rows={5}
                  onChange={e => setEditing(p => ({ ...p, body: e.target.value }))}
                  style={{ ...inp, resize: 'vertical', lineHeight: 1.6 }} />
              </div>

              <div style={{
                padding: '12px 14px', borderRadius: 10, display: 'flex',
                alignItems: 'center', gap: 12,
                background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.06)',
              }}>
                <ToggleSwitch
                  checked={editing.is_active}
                  onChange={() => setEditing(p => ({ ...p, is_active: !p.is_active }))}
                />
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600,
                    color: editing.is_active ? C.green : C.muted }}>
                    {editing.is_active ? 'Live — visible to recipients' : 'Hidden — draft only'}
                  </div>
                </div>
              </div>

              {editErr && (
                <div style={{ padding: '10px 12px', borderRadius: 8, fontSize: 12,
                  color: C.red, background: 'rgba(248,113,113,.08)',
                  border: '1px solid rgba(248,113,113,.2)' }}>
                  {editErr}
                </div>
              )}
            </div>

            {/* Drawer footer */}
            <div style={{ padding: '14px 24px', borderTop: '1px solid rgba(255,255,255,.07)',
              display: 'flex', gap: 10, flexShrink: 0 }}>
              <button className="act-btn" style={{ ...pBtn, flex: 1 }}
                onClick={saveEdit} disabled={editSaving}>
                {editSaving ? 'Saving…' : 'Save Changes'}
              </button>
              <button className="act-btn" onClick={() => setEditing(null)} style={{
                padding: '9px 16px', background: 'transparent', color: C.muted,
                border: '1px solid rgba(255,255,255,.1)', borderRadius: 8,
                cursor: 'pointer', fontSize: 13, fontWeight: 600,
              }}>Cancel</button>
            </div>
          </div>
        </>
      )}

      {/* ── Page header ─────────────────────────────────────────────────── */}
      <PageHead
        title="Announcements"
        sub="Broadcast notices to faculty by role or school"
      />

      {/* ── Two-column layout ───────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '380px minmax(0,1fr)', gap: 20, height: 'calc(100vh - 155px)' }}>

        {/* ══ Compose panel ════════════════════════════════════════════ */}
        <div style={{
          borderRadius: 14, background: 'var(--c-card)',
          border: '1px solid rgba(255,255,255,.08)',
          boxShadow: '0 4px 24px rgba(0,0,0,.3)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0,
        }}>

          {/* Top accent line */}
          <div style={{ height: 3, background: 'linear-gradient(90deg,#3b82f6,#818cf8,#a78bfa)', flexShrink: 0 }} />

          {/* ── Header ── */}
          <div style={{
            padding: '12px 16px', flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            borderBottom: '1px solid rgba(255,255,255,.06)',
            background: 'linear-gradient(135deg,rgba(59,130,246,.07) 0%,transparent 70%)',
          }}>
            <div style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
              <div style={{
                width: 28, height: 28, borderRadius: 7, flexShrink: 0,
                background: 'linear-gradient(135deg,#3b82f6,#818cf8)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: '0 2px 8px rgba(59,130,246,.4)',
              }}>
                <I.send size={12} stroke="#fff" />
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 800, color: C.text, letterSpacing: -.2 }}>
                  New Announcement
                </div>
                <div style={{ fontSize: 10, color: C.muted }}>Compose & broadcast</div>
              </div>
            </div>
            <div onClick={() => setForm(p => ({ ...p, is_active: !p.is_active }))} style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '3px 9px', borderRadius: 20, cursor: 'pointer', userSelect: 'none',
              background: form.is_active ? 'rgba(52,211,153,.12)' : 'rgba(255,255,255,.06)',
              border: `1px solid ${form.is_active ? 'rgba(52,211,153,.25)' : 'rgba(255,255,255,.1)'}`,
              transition: 'all .2s',
            }}>
              <div style={{
                width: 5, height: 5, borderRadius: '50%',
                background: form.is_active ? C.green : C.muted,
                boxShadow: form.is_active ? `0 0 6px ${C.green}` : 'none',
              }} />
              <span style={{ fontSize: 10, fontWeight: 700, color: form.is_active ? C.green : C.muted }}>
                {form.is_active ? 'Live' : 'Draft'}
              </span>
            </div>
          </div>

          {/* ── Form body ── */}
          <div style={{
            flex: 1, minHeight: 0, padding: '14px 16px',
            display: 'flex', flexDirection: 'column', gap: 12, overflow: 'hidden',
          }}>

            {/* Title */}
            <div style={{ flexShrink: 0 }}>
              <label style={{
                display: 'block', fontSize: 10, fontWeight: 700, letterSpacing: .6,
                textTransform: 'uppercase', color: C.muted, marginBottom: 5,
              }}>Title</label>
              <input className="ifield" value={form.title}
                onChange={e => setForm(p => ({ ...p, title: e.target.value }))}
                placeholder="e.g. Submission deadline extended to June 30"
                style={{ ...inp, fontSize: 12,
                  borderColor: form.title ? 'rgba(59,130,246,.35)' : undefined }} />
            </div>

            {/* Divider */}
            <div style={{ height: 1, background: 'rgba(255,255,255,.05)', flexShrink: 0 }} />

            {/* Audience */}
            <div style={{ flexShrink: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 7 }}>
                <label style={{
                  fontSize: 10, fontWeight: 700, letterSpacing: .6,
                  textTransform: 'uppercase', color: C.muted,
                }}>Audience</label>
                <div style={{ display: 'flex', gap: 3 }}>
                  {form.audiences.slice(0, 3).map(t => {
                    const col = tokenColor(t);
                    return (
                      <span key={t} style={{
                        fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 5,
                        background: `${col}14`, color: col, border: `1px solid ${col}25`,
                        fontFamily: "'JetBrains Mono',monospace",
                      }}>{tokenLabel(t)}</span>
                    );
                  })}
                  {form.audiences.length > 3 && (
                    <span style={{ fontSize: 9, color: C.muted }}>+{form.audiences.length - 3}</span>
                  )}
                </div>
              </div>
              <AudiencePicker
                selected={form.audiences}
                onChange={audiences => setForm(p => ({ ...p, audiences }))}
              />
            </div>

            {/* Divider */}
            <div style={{ height: 1, background: 'rgba(255,255,255,.05)', flexShrink: 0 }} />

            {/* Message — fills all remaining space */}
            <div style={{ flex: 1, minHeight: 160, display: 'flex', flexDirection: 'column' }}>
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                marginBottom: 6, flexShrink: 0,
              }}>
                <label style={{
                  fontSize: 10, fontWeight: 700, letterSpacing: .6,
                  textTransform: 'uppercase', color: C.muted,
                }}>Message</label>
                <span style={{
                  fontSize: 9, fontWeight: 600, fontFamily: "'JetBrains Mono',monospace",
                  color: form.body.length > 900 ? C.red : form.body.length > 600 ? C.yellow : C.muted,
                }}>
                  {form.body.length}/1000
                </span>
              </div>
              <textarea className="ifield" value={form.body} maxLength={1000}
                onChange={e => setForm(p => ({ ...p, body: e.target.value }))}
                placeholder="Write your announcement here…"
                style={{
                  ...inp, flex: 1, resize: 'none', lineHeight: 1.7, fontSize: 12,
                  borderColor: form.body ? 'rgba(52,211,153,.25)' : undefined, minHeight: 150,
                }} />
              <div style={{ marginTop: 5, height: 3, borderRadius: 2,
                background: 'rgba(255,255,255,.06)', flexShrink: 0 }}>
                <div style={{
                  height: '100%', borderRadius: 2,
                  width: `${form.body.length / 10}%`,
                  background: form.body.length > 900 ? C.red : form.body.length > 600 ? C.yellow : C.green,
                  transition: 'width .2s, background .3s',
                }} />
              </div>
            </div>

            {/* Status */}
            {status && (
              <div style={{
                flexShrink: 0, padding: '8px 11px', borderRadius: 7, fontSize: 11,
                display: 'flex', alignItems: 'center', gap: 7,
                color: status.ok ? C.green : C.red,
                background: status.ok ? 'rgba(52,211,153,.08)' : 'rgba(248,113,113,.08)',
                border: `1px solid ${status.ok ? 'rgba(52,211,153,.2)' : 'rgba(248,113,113,.2)'}`,
              }}>
                <span>{status.ok ? '✓' : '!'}</span>{status.msg}
              </div>
            )}
          </div>

          {/* ── Options bar ── */}
          <div style={{
            padding: '10px 16px', flexShrink: 0,
            borderTop: '1px solid rgba(255,255,255,.05)',
            display: 'flex', gap: 7,
          }}>
            {[
              {
                on: form.is_active,
                label: form.is_active ? 'Live' : 'Draft',
                sub: form.is_active ? 'Visible to faculty' : 'Hidden draft',
                col: C.green,
                toggle: () => setForm(p => ({ ...p, is_active: !p.is_active })),
                disabled: false,
              },
              {
                on: form.is_active && form.send_email,
                label: 'Send Email',
                sub: form.is_active && form.send_email ? 'Notify recipients' : 'No email',
                col: '#3b82f6',
                toggle: () => { if (form.is_active) setForm(p => ({ ...p, send_email: !p.send_email })); },
                disabled: !form.is_active,
              },
            ].map(opt => (
              <div key={opt.label} onClick={opt.toggle} style={{
                flex: 1, display: 'flex', alignItems: 'center', gap: 8,
                padding: '7px 10px', borderRadius: 8,
                cursor: opt.disabled ? 'default' : 'pointer',
                background: opt.on ? `${opt.col}08` : 'rgba(255,255,255,.03)',
                border: `1px solid ${opt.on ? `${opt.col}20` : 'rgba(255,255,255,.06)'}`,
                opacity: opt.disabled ? 0.4 : 1, transition: 'all .2s', userSelect: 'none',
              }}>
                <ToggleSwitch checked={opt.on} onChange={opt.toggle} />
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: opt.on ? opt.col : C.muted }}>
                    {opt.label}
                  </div>
                  <div style={{ fontSize: 9, color: C.muted, marginTop: 1 }}>{opt.sub}</div>
                </div>
              </div>
            ))}
          </div>

          {/* ── Footer ── */}
          <div style={{
            padding: '10px 16px', flexShrink: 0,
            borderTop: '1px solid rgba(255,255,255,.05)',
            display: 'flex', gap: 7, background: 'rgba(255,255,255,.015)',
          }}>
            <button className="act-btn" onClick={handlePublish} disabled={saving} style={{
              flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              padding: '10px 0', borderRadius: 9, cursor: saving ? 'default' : 'pointer',
              fontFamily: 'inherit', fontSize: 13, fontWeight: 700, color: '#fff', border: 'none',
              background: saving ? 'rgba(59,130,246,.4)' : 'linear-gradient(135deg,#3b82f6,#818cf8)',
              boxShadow: saving ? 'none' : '0 4px 14px rgba(59,130,246,.4)',
              opacity: saving ? .7 : 1, transition: 'all .2s',
            }}>
              <I.send size={13} stroke="#fff" />
              {saving ? 'Publishing…' : form.is_active ? 'Publish Now' : 'Save Draft'}
            </button>
            <button className="act-btn" onClick={() => { setForm(EMPTY); setStatus(null); }} style={{
              padding: '10px 14px', borderRadius: 9, cursor: 'pointer',
              fontFamily: 'inherit', fontSize: 12, fontWeight: 600,
              color: C.muted, background: 'transparent', border: '1px solid rgba(255,255,255,.1)',
            }}>Clear</button>
          </div>
        </div>

        {/* ══ Feed panel ═══════════════════════════════════════════════ */}
        <div style={{ height: '100%', minHeight: 0, overflowY: 'auto', paddingRight: 2 }}>
            {loading && <Loading />}
            {error   && <ApiError message={error} />}

            {/* Empty state */}
            {!loading && !error && visible.length === 0 && (
              <div style={{
                borderRadius: 14, padding: '60px 24px', textAlign: 'center',
                background: 'rgba(255,255,255,.02)', border: '1px solid rgba(255,255,255,.05)',
              }}>
                <div style={{
                  width: 56, height: 56, borderRadius: 14, margin: '0 auto 16px',
                  background: `${C.accent}10`, border: `1px solid ${C.accent}20`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <I.send size={24} stroke={C.accent} />
                </div>
                <div style={{ fontSize: 15, fontWeight: 700, color: C.text, marginBottom: 6 }}>
                  {filter !== 'all' ? 'No matches found' : 'No announcements yet'}
                </div>
                <div style={{ fontSize: 12, color: C.muted, lineHeight: 1.7, maxWidth: 260, margin: '0 auto' }}>
                  {filter !== 'all'
                    ? 'Try adjusting the filter above'
                    : 'Use the composer on the left to broadcast your first notice'}
                </div>
              </div>
            )}

            {/* Notice list */}
            {!loading && !error && visible.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingBottom: 12 }}>
                {visible.map(n => (
                  <NoticeRow
                    key={n.id}
                    n={n}
                    deleting={deleting === n.id}
                    onDelete={() => handleDelete(n.id)}
                    onEdit={() => setEditing({
                      id: n.id, title: n.title, body: n.body ?? '',
                      audiences: toArr(n.audience), is_active: n.is_active ?? true,
                    })}
                  />
                ))}
              </div>
            )}
        </div>
      </div>
    </div>
  );
}
