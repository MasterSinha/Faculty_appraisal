import { useState, useEffect, useMemo } from 'react';
import { C } from '../../constants/colors';
import { I } from '../../components/icons';
import PageHead from '../../components/PageHead';
import { api } from '../../api/client';
import { getLog, clearLog } from '../../utils/activityLog';

// ── Inline localStorage helpers ───────────────────────────────────────────────

function getSecLog()  { try { return JSON.parse(localStorage.getItem('dyp_security_events') || '[]'); } catch { return []; } }
function clearSecLog() { localStorage.removeItem('dyp_security_events'); }

// ── Metadata ──────────────────────────────────────────────────────────────────

const SEC_CFG = {
  unauthorized: { label: 'Unauthorized',  color: C.red,    icon: I.lock   },
  forbidden:    { label: 'Forbidden',     color: C.orange, icon: I.shield },
  rate_limited: { label: 'Rate Limited',  color: C.yellow, icon: I.clock  },
  login_failed: { label: 'Login Failed',  color: C.red,    icon: I.key    },
};

const ADMIN_CFG = {
  user_created:         { label: 'User Created',         color: C.green,   icon: I.addUser },
  user_deleted:         { label: 'User Deleted',         color: C.red,     icon: I.trash   },
  user_updated:         { label: 'User Updated',         color: C.accent,  icon: I.edit    },
  user_activated:       { label: 'User Activated',       color: C.green,   icon: I.check   },
  user_deactivated:     { label: 'User Deactivated',     color: C.yellow,  icon: I.clock   },
  announcement_created: { label: 'Announcement Posted',  color: C.accent,  icon: I.send    },
  announcement_updated: { label: 'Announcement Updated', color: '#a78bfa', icon: I.edit    },
  announcement_deleted: { label: 'Announcement Deleted', color: C.red,     icon: I.trash   },
};

const STATUS_CFG = {
  'Reviewed':                { color: C.green,   label: 'Reviewed'          },
  'Pending VC Review':       { color: '#a78bfa', label: 'VC Review'         },
  'Pending Dean Review':     { color: C.accent,  label: 'Dean Review'       },
  'Pending Director Review': { color: C.orange,  label: 'Director Review'   },
  'Pending Review':          { color: C.yellow,  label: 'HOD Review'        },
  'Submitted':               { color: C.yellow,  label: 'HOD Review'        },
};

const ROLE_LABELS = {
  faculty: 'Faculty', hod: 'HOD', director: 'Director',
  dean: 'Dean', vc: 'VC', registrar: 'Registrar', center_head: 'Center Head',
};

const TEACHING_ROLES = new Set(['faculty', 'hod', 'director', 'dean', 'center_head']);

const FAC_CFG = {
  login:      { label: 'Faculty Login',      color: C.accent,  icon: I.key     },
  save:       { label: 'Draft Saved',        color: C.yellow,  icon: I.edit    },
  submission: { label: 'Appraisal Submitted', color: C.green,   icon: I.send    },
  review:     { label: 'Form Reviewed',      color: '#a78bfa', icon: I.check   },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmtTime = iso => new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
const fmtShort = iso => new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

function dateLabel(iso) {
  const d = new Date(iso), today = new Date(), yest = new Date(today);
  yest.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === yest.toDateString()) return 'Yesterday';
  return d.toLocaleDateString('en-US', { day: 'numeric', month: 'long', year: 'numeric' });
}

function groupByDate(entries) {
  const map = new Map();
  for (const e of entries) {
    const k = dateLabel(e.at);
    if (!map.has(k)) map.set(k, []);
    map.get(k).push(e);
  }
  return [...map.entries()];
}

// ── Reusable UI ───────────────────────────────────────────────────────────────

function TabBtn({ active, icon: Icon, label, badge, onClick }) {
  return (
    <button className="act-btn" onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 7, padding: '7px 15px', borderRadius: 7,
      cursor: 'pointer', fontSize: 12, fontWeight: active ? 700 : 500, transition: 'all .15s',
      background: active ? `${C.accent}15` : 'transparent',
      border: `1px solid ${active ? C.accent : 'transparent'}`,
      color: active ? C.accent : C.muted,
    }}>
      <Icon size={13} stroke={active ? C.accent : C.muted} />
      {label}
      {badge > 0 && (
        <span style={{
          fontSize: 9, fontWeight: 800, padding: '1px 5px', borderRadius: 4,
          background: `${C.red}25`, color: C.red, fontFamily: "'JetBrains Mono',monospace",
        }}>{badge}</span>
      )}
    </button>
  );
}

function StatusBadge({ color, label }) {
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 5,
      background: `${color}18`, border: `1px solid ${color}30`, color,
    }}>{label}</span>
  );
}

function EmptyState({ icon: Icon = I.clock, title, sub }) {
  return (
    <div style={{
      borderRadius: 14, padding: '56px 24px', textAlign: 'center',
      background: 'rgba(255,255,255,.02)', border: '1px solid rgba(255,255,255,.05)',
    }}>
      <div style={{
        width: 48, height: 48, borderRadius: 12, margin: '0 auto 14px',
        background: `${C.accent}10`, border: `1px solid ${C.accent}20`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon size={20} stroke={C.accent} />
      </div>
      <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 5 }}>{title}</div>
      <div style={{ fontSize: 12, color: C.muted, lineHeight: 1.7, maxWidth: 260, margin: '0 auto' }}>{sub}</div>
    </div>
  );
}

function TimelineRow({ icon: Icon, color, title, detail, time, tags, isLast }) {
  return (
    <div style={{ display: 'flex', gap: 12 }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 12, flexShrink: 0 }}>
        <div style={{
          width: 9, height: 9, borderRadius: '50%', background: color,
          flexShrink: 0, marginTop: 5, boxShadow: `0 0 0 3px ${color}22`,
        }} />
        {!isLast && <div style={{ width: 1.5, flex: 1, background: 'rgba(255,255,255,.06)', marginTop: 4, minHeight: 22 }} />}
      </div>
      <div style={{ flex: 1, paddingBottom: isLast ? 0 : 12 }}>
        <div style={{
          padding: '10px 13px', borderRadius: 9,
          background: 'rgba(255,255,255,.025)', border: '1px solid rgba(255,255,255,.06)',
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
              <div style={{
                width: 28, height: 28, borderRadius: 7, flexShrink: 0,
                background: `${color}15`, border: `1px solid ${color}28`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon size={12} stroke={color} />
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{title}</div>
                <div style={{ fontSize: 11, color: C.muted, marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{detail}</div>
              </div>
            </div>
            <span style={{ fontSize: 10, color: C.muted, flexShrink: 0, fontFamily: "'JetBrains Mono',monospace" }}>{time}</span>
          </div>
          {tags?.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 7 }}>
              {tags.map((t, i) => (
                <span key={i} style={{
                  fontSize: 10, padding: '1px 7px', borderRadius: 5,
                  background: 'rgba(255,255,255,.05)', border: '1px solid rgba(255,255,255,.08)',
                  color: C.subtle, fontFamily: "'JetBrains Mono',monospace",
                }}>{t}</span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DateGroup({ dateKey, entries, renderRow }) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: C.muted, letterSpacing: .6, textTransform: 'uppercase' }}>{dateKey}</span>
        <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,.05)' }} />
        <span style={{ fontSize: 10, color: C.muted, fontFamily: "'JetBrains Mono',monospace" }}>{entries.length}</span>
      </div>
      {entries.map((e, i) => renderRow(e, i === entries.length - 1))}
    </div>
  );
}

// ── Security Events Tab ───────────────────────────────────────────────────────

function SecurityTab() {
  const [log, setLog] = useState(() => getSecLog());
  const [typeFilter, setTypeFilter] = useState('all');
  const [confirm, setConfirm] = useState(false);

  const filtered = typeFilter === 'all' ? log : log.filter(e => e.type === typeFilter);
  const groups = groupByDate(filtered);

  const counts = useMemo(() => {
    const m = { unauthorized: 0, forbidden: 0, rate_limited: 0, login_failed: 0 };
    for (const e of log) if (e.type in m) m[e.type]++;
    return m;
  }, [log]);

  const handleClear = () => {
    if (!confirm) { setConfirm(true); return; }
    clearSecLog(); setLog([]); setConfirm(false);
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        {Object.entries(SEC_CFG).map(([k, cfg]) => {
          const active = typeFilter === k;
          return (
            <button key={k} className="act-btn" onClick={() => setTypeFilter(active ? 'all' : k)} style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '6px 11px', borderRadius: 7,
              cursor: 'pointer', fontSize: 11, fontWeight: active ? 700 : 500,
              background: active ? `${cfg.color}15` : `${cfg.color}08`,
              border: `1px solid ${active ? cfg.color : `${cfg.color}30`}`,
              color: active ? cfg.color : C.muted,
            }}>
              <cfg.icon size={11} stroke={active ? cfg.color : C.muted} />
              {cfg.label}
              <span style={{ fontFamily: "'JetBrains Mono',monospace", opacity: .7 }}>{counts[k]}</span>
            </button>
          );
        })}
        {log.length > 0 && (
          <>
            <div style={{ flex: 1 }} />
            <button className="act-btn" onClick={handleClear} onBlur={() => setConfirm(false)} style={{
              padding: '6px 12px', borderRadius: 7, fontSize: 11, fontWeight: 600, cursor: 'pointer',
              color: confirm ? C.red : C.muted,
              background: confirm ? 'rgba(248,113,113,.08)' : 'transparent',
              border: `1px solid ${confirm ? 'rgba(248,113,113,.3)' : 'rgba(255,255,255,.1)'}`,
            }}>
              {confirm ? 'Confirm Clear?' : 'Clear Log'}
            </button>
          </>
        )}
      </div>

      {log.length === 0 ? (
        <EmptyState icon={I.shield} title="No security events"
          sub="Unauthorized access, forbidden requests, and rate limit violations are captured here automatically." />
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: C.muted, fontSize: 13 }}>
          No {typeFilter.replace('_', ' ')} events recorded.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {groups.map(([dk, entries]) => (
            <DateGroup key={dk} dateKey={dk} entries={entries} renderRow={(e, isLast) => {
              const cfg = SEC_CFG[e.type] ?? { label: e.type, color: C.muted, icon: I.clock };
              return (
                <TimelineRow key={e.id}
                  icon={cfg.icon} color={cfg.color}
                  title={cfg.label}
                  detail={e.detail || e.endpoint}
                  time={fmtTime(e.at)}
                  tags={[`HTTP ${e.statusCode}`, e.endpoint].filter(Boolean)}
                  isLast={isLast}
                />
              );
            }} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Faculty Status Tab ────────────────────────────────────────────────────────

function FacultyTab() {
  const [cycles, setCycles]       = useState([]);
  const [year, setYear]           = useState('');
  const [logs, setLogs]           = useState([]);
  const [loading, setLoading]     = useState(false);
  const [err, setErr]             = useState(null);
  const [typeFilter, setTypeFilter] = useState('all');
  const [search, setSearch]       = useState('');

  useEffect(() => {
    api.cycle.list()
      .then(c => {
        const sorted = (c || []).sort((a, b) => b.academic_year.localeCompare(a.academic_year));
        setCycles(sorted);
        if (sorted.length) setYear(sorted[0].academic_year);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!year) return;
    setLoading(true); setErr(null);
    api.logs.facultyActivity({ academic_year: year })
      .then(data => {
        setLogs(Array.isArray(data) ? data : []);
      })
      .catch(e => setErr(e.message))
      .finally(() => setLoading(false));
  }, [year]);

  const filtered = useMemo(() => {
    return logs.filter(e => {
      if (typeFilter !== 'all' && e.type !== typeFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          e.detail.toLowerCase().includes(q) ||
          e.title.toLowerCase().includes(q) ||
          (e.meta?.email || e.meta?.faculty_email || '').toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [logs, typeFilter, search]);

  const groups = useMemo(() => groupByDate(filtered), [filtered]);

  const counts = useMemo(() => {
    const m = { login: 0, save: 0, submission: 0, review: 0 };
    for (const e of logs) if (e.type in m) m[e.type]++;
    return m;
  }, [logs]);

  return (
    <div>
      {/* Year + search row */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <select value={year} onChange={e => setYear(e.target.value)} style={{
          background: 'rgba(255,255,255,.05)', border: '1px solid rgba(255,255,255,.12)',
          borderRadius: 7, padding: '6px 10px', color: C.text, fontSize: 12, cursor: 'pointer',
        }}>
          {cycles.map(c => <option key={c.academic_year} value={c.academic_year}>{c.academic_year}</option>)}
        </select>

        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search name or email…"
          style={{
            background: 'rgba(255,255,255,.05)', border: '1px solid rgba(255,255,255,.1)',
            borderRadius: 7, padding: '6px 11px', color: C.text, fontSize: 12,
            outline: 'none', width: 200,
          }}
        />
      </div>

      {/* Role + status filter row */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <button className="act-btn" onClick={() => setTypeFilter('all')} style={{
          padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: typeFilter === 'all' ? 700 : 500,
          cursor: 'pointer',
          background: typeFilter === 'all' ? `${C.accent}15` : 'transparent',
          border: `1px solid ${typeFilter === 'all' ? C.accent : 'rgba(255,255,255,.08)'}`,
          color: typeFilter === 'all' ? C.accent : C.muted,
        }}>
          All Actions <span style={{ opacity: .55, marginLeft: 4 }}>({logs.length})</span>
        </button>

        {Object.entries(FAC_CFG).map(([k, cfg]) => {
          const active = typeFilter === k;
          return (
            <button key={k} className="act-btn" onClick={() => setTypeFilter(active ? 'all' : k)} style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 6,
              cursor: 'pointer', fontSize: 11, fontWeight: active ? 700 : 500,
              background: active ? `${cfg.color}15` : 'transparent',
              border: `1px solid ${active ? cfg.color : 'rgba(255,255,255,.08)'}`,
              color: active ? cfg.color : C.muted,
            }}>
              <cfg.icon size={11} stroke={active ? cfg.color : C.muted} />
              {cfg.label}
              <span style={{ opacity: .55, marginLeft: 4 }}>({counts[k]})</span>
            </button>
          );
        })}
      </div>

      {loading && <div style={{ textAlign: 'center', padding: '40px 0', color: C.muted, fontSize: 13 }}>Loading…</div>}
      {err     && <div style={{ textAlign: 'center', padding: '40px 0', color: C.red,  fontSize: 13 }}>{err}</div>}

      {!loading && !err && filtered.length === 0 && (
        <EmptyState icon={I.clock} title="No actions found"
          sub={logs.length === 0 ? 'No actions recorded for this cycle yet.' : 'No actions match your filters.'} />
      )}

      {!loading && !err && filtered.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {groups.map(([dateKey, entries]) => (
            <DateGroup
              key={dateKey}
              dateKey={dateKey}
              entries={entries}
              renderRow={(e, isLast) => {
                const cfg = FAC_CFG[e.type] ?? { label: e.type, color: C.muted, icon: I.clock };
                const metaTokens = Object.values(e.meta || {}).filter(Boolean);
                return (
                  <TimelineRow
                    key={e.id}
                    icon={cfg.icon}
                    color={cfg.color}
                    title={e.title}
                    detail={e.detail}
                    time={fmtTime(e.at)}
                    tags={metaTokens}
                    isLast={isLast}
                  />
                );
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Admin Actions Tab ─────────────────────────────────────────────────────────

function AdminTab() {
  const [log, setLog]       = useState(() => getLog());
  const [filter, setFilter] = useState('all');
  const [confirm, setConfirm] = useState(false);

  const filtered = log.filter(e => {
    if (filter === 'users')         return e.type.startsWith('user_');
    if (filter === 'announcements') return e.type.startsWith('announcement_');
    return true;
  });
  const groups = groupByDate(filtered);

  const handleClear = () => {
    if (!confirm) { setConfirm(true); return; }
    clearLog(); setLog([]); setConfirm(false);
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        {[
          { k: 'all',           label: 'All',           count: log.length },
          { k: 'users',         label: 'Users',         count: log.filter(e => e.type.startsWith('user_')).length },
          { k: 'announcements', label: 'Announcements', count: log.filter(e => e.type.startsWith('announcement_')).length },
        ].map(f => {
          const active = filter === f.k;
          return (
            <button key={f.k} className="act-btn" onClick={() => setFilter(f.k)} style={{
              padding: '5px 11px', borderRadius: 7, fontSize: 11, fontWeight: active ? 700 : 500,
              cursor: 'pointer',
              background: active ? `${C.accent}15` : 'transparent',
              border: `1px solid ${active ? C.accent : 'rgba(255,255,255,.08)'}`,
              color: active ? C.accent : C.muted,
            }}>
              {f.label}
              <span style={{ opacity: .55, marginLeft: 4 }}>({f.count})</span>
            </button>
          );
        })}
        {log.length > 0 && (
          <>
            <div style={{ flex: 1 }} />
            <button className="act-btn" onClick={handleClear} onBlur={() => setConfirm(false)} style={{
              padding: '6px 12px', borderRadius: 7, fontSize: 11, fontWeight: 600, cursor: 'pointer',
              color: confirm ? C.red : C.muted,
              background: confirm ? 'rgba(248,113,113,.08)' : 'transparent',
              border: `1px solid ${confirm ? 'rgba(248,113,113,.3)' : 'rgba(255,255,255,.1)'}`,
            }}>
              {confirm ? 'Confirm Clear?' : 'Clear Log'}
            </button>
          </>
        )}
      </div>

      {log.length === 0 ? (
        <EmptyState icon={I.clock} title="No admin actions"
          sub="User management, announcements, and other admin actions appear here automatically." />
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: C.muted, fontSize: 13 }}>
          No {filter} actions recorded yet.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {groups.map(([dk, entries]) => (
            <DateGroup key={dk} dateKey={dk} entries={entries} renderRow={(e, isLast) => {
              const cfg = ADMIN_CFG[e.type] ?? { label: e.type, color: C.muted, icon: I.clock };
              return (
                <TimelineRow key={e.id}
                  icon={cfg.icon} color={cfg.color}
                  title={cfg.label}
                  detail={e.detail}
                  time={fmtTime(e.at)}
                  tags={Object.values(e.meta || {}).filter(Boolean)}
                  isLast={isLast}
                />
              );
            }} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function MonitoringPage() {
  const [tab, setTab] = useState('security');
  const secCount = getSecLog().length;

  return (
    <div className="page-enter">
      <PageHead
        title="Activity Monitor"
        sub="Security events, faculty submission status, and admin action history — all in one place"
      />

      {/* Tab strip */}
      <div style={{
        display: 'flex', gap: 3, marginBottom: 20, padding: 4,
        background: 'rgba(255,255,255,.03)', borderRadius: 10,
        border: '1px solid rgba(255,255,255,.07)', width: 'fit-content',
      }}>
        <TabBtn active={tab === 'security'} icon={I.shield} label="Security Events" badge={secCount} onClick={() => setTab('security')} />
        <TabBtn active={tab === 'faculty'}  icon={I.users}  label="Faculty Status"                   onClick={() => setTab('faculty')}  />
        <TabBtn active={tab === 'admin'}    icon={I.clock}  label="Admin Actions"                    onClick={() => setTab('admin')}    />
      </div>

      {tab === 'security' && <SecurityTab />}
      {tab === 'faculty'  && <FacultyTab  />}
      {tab === 'admin'    && <AdminTab    />}
    </div>
  );
}
