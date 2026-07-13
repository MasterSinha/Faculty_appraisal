import { useState } from 'react';
import { C } from '../../constants/colors';
import { I } from '../../components/icons';
import PageHead from '../../components/PageHead';
import { getLog, clearLog } from '../../utils/activityLog';

const ACTION_META = {
  user_created:         { label: 'User Created',         color: C.green,   icon: I.addUser },
  user_deleted:         { label: 'User Deleted',         color: C.red,     icon: I.trash   },
  user_updated:         { label: 'User Updated',         color: C.accent,  icon: I.edit    },
  user_activated:       { label: 'User Activated',       color: C.green,   icon: I.check   },
  user_deactivated:     { label: 'User Deactivated',     color: C.yellow,  icon: I.clock   },
  announcement_created: { label: 'Announcement Posted',  color: C.accent,  icon: I.send    },
  announcement_updated: { label: 'Announcement Updated', color: '#a78bfa', icon: I.edit    },
  announcement_deleted: { label: 'Announcement Deleted', color: C.red,     icon: I.trash   },
  transition_executed:  { label: 'Appraisal Cycle Shifted', color: C.green,   icon: I.refresh },
  revert_executed:      { label: 'Appraisal Cycle Reverted', color: C.yellow,  icon: I.clock   },
};

const FILTERS = [
  { key: 'all',           label: 'All'           },
  { key: 'users',         label: 'Users'         },
  { key: 'announcements', label: 'Announcements' },
];

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

function dateLabel(iso) {
  const d = new Date(iso);
  const today     = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString())     return 'Today';
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString('en-US', { day: 'numeric', month: 'long', year: 'numeric' });
}

function groupByDate(entries) {
  const map = new Map();
  for (const e of entries) {
    const key = dateLabel(e.at);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(e);
  }
  return [...map.entries()];
}

function isToday(iso) {
  return new Date(iso).toDateString() === new Date().toDateString();
}
function isThisWeek(iso) {
  return Date.now() - new Date(iso) < 7 * 86400 * 1000;
}

// ── EntryRow ───────────────────────────────────────────────────────────────────

function EntryRow({ entry, isLast }) {
  const cfg  = ACTION_META[entry.type] ?? { label: entry.type, color: C.muted, icon: I.clock };
  const Icon = cfg.icon;
  const metaTokens = Object.values(entry.meta || {}).filter(Boolean);

  return (
    <div style={{ display: 'flex', gap: 14 }}>
      {/* Timeline spine */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
        width: 12, flexShrink: 0 }}>
        <div style={{
          width: 10, height: 10, borderRadius: '50%', background: cfg.color,
          flexShrink: 0, marginTop: 5,
          boxShadow: `0 0 0 3px ${cfg.color}22`,
        }} />
        {!isLast && (
          <div style={{ width: 1.5, flex: 1, background: 'rgba(255,255,255,.06)',
            marginTop: 4, minHeight: 24 }} />
        )}
      </div>

      {/* Card */}
      <div style={{ flex: 1, paddingBottom: isLast ? 0 : 14, minWidth: 0 }}>
        <div style={{
          padding: '11px 14px', borderRadius: 10,
          background: 'rgba(255,255,255,.025)',
          border: '1px solid rgba(255,255,255,.06)',
          transition: 'border-color .15s',
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start',
            justifyContent: 'space-between', gap: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
              <div style={{
                width: 30, height: 30, borderRadius: 8, flexShrink: 0,
                background: `${cfg.color}15`, border: `1px solid ${cfg.color}28`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon size={13} stroke={cfg.color} />
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{cfg.label}</div>
                <div style={{ fontSize: 11, color: C.muted, marginTop: 1,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {entry.detail}
                </div>
              </div>
            </div>
            <span style={{
              fontSize: 10, color: C.muted, flexShrink: 0,
              fontFamily: "'JetBrains Mono',monospace",
            }}>
              {fmtTime(entry.at)}
            </span>
          </div>

          {metaTokens.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 8 }}>
              {metaTokens.map((v, i) => (
                <span key={i} style={{
                  fontSize: 10, padding: '2px 8px', borderRadius: 6,
                  background: 'rgba(255,255,255,.05)',
                  border: '1px solid rgba(255,255,255,.08)',
                  color: C.subtle, fontFamily: "'JetBrains Mono',monospace",
                }}>
                  {v}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function HistoryPage() {
  const [log,     setLog]     = useState(() => getLog());
  const [filter,  setFilter]  = useState('all');
  const [confirm, setConfirm] = useState(false);

  const refresh = () => setLog(getLog());

  const handleClear = () => {
    if (!confirm) { setConfirm(true); return; }
    clearLog(); setLog([]); setConfirm(false);
  };

  const filtered = log.filter(e => {
    if (filter === 'users')         return e.type.startsWith('user_');
    if (filter === 'announcements') return e.type.startsWith('announcement_');
    return true;
  });

  const groups   = groupByDate(filtered);
  const todayN   = log.filter(e => isToday(e.at)).length;
  const weekN    = log.filter(e => isThisWeek(e.at)).length;

  return (
    <div className="page-enter">
      <PageHead
        title="Activity History"
        sub="Complete record of all admin actions"
        action={
          log.length > 0 && (
            <button
              className="act-btn"
              onClick={handleClear}
              onBlur={() => setConfirm(false)}
              style={{
                padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600,
                cursor: 'pointer',
                color: confirm ? C.red : C.muted,
                background: confirm ? 'rgba(248,113,113,.08)' : 'transparent',
                border: `1px solid ${confirm ? 'rgba(248,113,113,.3)' : 'rgba(255,255,255,.1)'}`,
                transition: 'all .15s',
              }}>
              {confirm ? 'Confirm Clear?' : 'Clear History'}
            </button>
          )
        }
      />

      {/* ── Stats bar ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        {[
          { label: 'Total',     value: log.length, color: C.accent },
          { label: 'Today',     value: todayN,     color: C.green  },
          { label: 'This Week', value: weekN,       color: '#a78bfa'},
        ].map(s => (
          <div key={s.label} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 14px', borderRadius: 9,
            background: `${s.color}0d`, border: `1px solid ${s.color}22`,
          }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: s.color }} />
            <span style={{ fontSize: 12, color: C.muted }}>{s.label}</span>
            <span style={{ fontSize: 16, fontWeight: 800, color: s.color,
              fontFamily: "'JetBrains Mono',monospace", marginLeft: 2 }}>{s.value}</span>
          </div>
        ))}

        <div style={{ width: 1, height: 18, background: 'rgba(255,255,255,.1)', flexShrink: 0 }} />

        {/* Filter tabs */}
        {FILTERS.map(f => {
          const count  = f.key === 'all' ? log.length
            : f.key === 'users' ? log.filter(e => e.type.startsWith('user_')).length
            : log.filter(e => e.type.startsWith('announcement_')).length;
          const active = filter === f.key;
          return (
            <button key={f.key} className="act-btn" onClick={() => setFilter(f.key)} style={{
              padding: '6px 12px', borderRadius: 7, fontSize: 12, fontWeight: active ? 700 : 500,
              cursor: 'pointer',
              border: `1px solid ${active ? C.accent : 'rgba(255,255,255,.08)'}`,
              background: active ? `${C.accent}15` : 'transparent',
              color: active ? C.accent : C.subtle,
            }}>
              {f.label}
              <span style={{ opacity: .55, fontSize: 11, marginLeft: 5 }}>({count})</span>
            </button>
          );
        })}
      </div>

      {/* ── Timeline ──────────────────────────────────────────────────── */}
      {log.length === 0 ? (
        /* Empty state */
        <div style={{
          borderRadius: 14, padding: '72px 24px', textAlign: 'center',
          background: 'rgba(255,255,255,.02)', border: '1px solid rgba(255,255,255,.05)',
        }}>
          <div style={{
            width: 56, height: 56, borderRadius: 14, margin: '0 auto 16px',
            background: `${C.accent}10`, border: `1px solid ${C.accent}20`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <I.clock size={24} stroke={C.accent} />
          </div>
          <div style={{ fontSize: 15, fontWeight: 700, color: C.text, marginBottom: 6 }}>
            No activity yet
          </div>
          <div style={{ fontSize: 12, color: C.muted, lineHeight: 1.7, maxWidth: 260, margin: '0 auto' }}>
            Actions like adding users, posting announcements, and managing feedback will appear here automatically.
          </div>
        </div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '48px 0', color: C.muted, fontSize: 13 }}>
          No {filter} actions recorded yet.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {groups.map(([dateKey, entries]) => (
            <div key={dateKey}>
              {/* Date group header */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14,
              }}>
                <span style={{
                  fontSize: 11, fontWeight: 700, color: C.muted,
                  letterSpacing: .6, textTransform: 'uppercase',
                }}>
                  {dateKey}
                </span>
                <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,.05)' }} />
                <span style={{
                  fontSize: 10, color: C.muted,
                  fontFamily: "'JetBrains Mono',monospace",
                }}>
                  {entries.length} action{entries.length !== 1 ? 's' : ''}
                </span>
              </div>

              {/* Entries */}
              {entries.map((entry, i) => (
                <EntryRow
                  key={entry.id}
                  entry={entry}
                  isLast={i === entries.length - 1}
                />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
