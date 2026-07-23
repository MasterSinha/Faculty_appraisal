import { useState, useMemo, memo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Sector,
} from 'recharts';
import { C } from '../../constants/colors';
import { api } from '../../api/client';
import { normalizeStats, normalizeUsers } from '../../api/normalizers';
import { AUTO_REFRESH_INTERVAL, useFetch } from '../../hooks/useFetch';
import { Loading, ApiError } from '../../components/LoadingState';
import { inp, smBtn, rateColor } from '../../constants/styleTokens';
import { SCHOOLS, SCHOOL_MAP } from '../../constants/schools';
import Badge from '../../components/Badge';
import Card from '../../components/Card';
import PageHead from '../../components/PageHead';
import LiveBadge from '../../components/LiveBadge';
import ProgressBar from '../../components/ProgressBar';
import ChartTip from '../../components/ChartTip';
import { I } from '../../components/icons';

// ── Stage configs ──────────────────────────────────────────────────────────────

const T_STAGES = [
  { key: 'Submitted',               label: 'Submitted',    color: C.accent  },
  { key: 'Pending Review',          label: 'HOD Review',   color: '#a78bfa' },
  { key: 'Pending Director Review', label: 'Director',     color: C.yellow  },
  { key: 'Pending Dean Review',     label: 'Dean',         color: C.green   },
  { key: 'Pending VC Review',       label: 'VC Queue',     color: '#f472b6' },
  { key: 'Reviewed',                label: 'Approved',     color: '#22d3ee' },
];

const NT_STAGES = [
  { key: 'Pending RO Review',          label: 'RO Queue',     color: C.accent  },
  { key: 'Pending Registrar Review',   label: 'Reg. Queue',   color: '#e879f9' },
  { key: 'Reporting Officer Reviewed', label: 'RO Reviewed',  color: '#a78bfa' },
  { key: 'Registrar Reviewed',         label: 'Registrar',    color: C.yellow  },
  { key: 'VC Approved',                label: 'VC Approved',  color: '#22d3ee' },
];

const CISR_STAGES = [
  { key: 'Submitted',                  label: 'Submitted',    color: C.accent  },
  { key: 'Pending Center Head Review', label: 'Center Head',  color: '#e879f9' },
  { key: 'Pending VC Review',          label: 'VC Queue',     color: '#f472b6' },
  { key: 'Reviewed',                   label: 'Approved',     color: '#22d3ee' },
];

const ROLE_COLORS = {
  faculty:            C.accent,
  hod:                '#a78bfa',
  director:           C.yellow,
  dean:               C.green,
  registrar:          '#22d3ee',
  vc:                 '#f472b6',
  non_teaching_staff: C.orange,
  reporting_officer:  '#fb923c',
};

// ── Helpers ────────────────────────────────────────────────────────────────────

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

function fmtRole(r) {
  return r.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

// ── Sub-components ─────────────────────────────────────────────────────────────

const KPI = memo(function KPI({ label, value, sub, color, icon: Icon, delay = 0 }) {
  return (
    <div className="glass glass-glow stat-card card-shimmer card-appear" style={{
      padding: '18px 20px', borderRadius: 12, position: 'relative', overflow: 'hidden',
      border: '1px solid rgba(255,255,255,.06)',
      animationDelay: `${delay}ms`,
    }}>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2,
        background: `linear-gradient(90deg,transparent,${color}80,transparent)` }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 10, color: C.muted, fontWeight: 700, letterSpacing: .7,
            textTransform: 'uppercase', marginBottom: 8 }}>{label}</div>
          <div className="stat-enter" style={{ fontSize: 28, fontWeight: 800, color: C.text, lineHeight: 1,
            letterSpacing: -1, fontFamily: "'JetBrains Mono',monospace",
            animationDelay: `${delay + 80}ms` }}>{value}</div>
          {sub && <div style={{ fontSize: 11, color, marginTop: 6, fontWeight: 500 }}>{sub}</div>}
        </div>
        <div style={{ padding: 10, borderRadius: 10,
          background: `${color}14`, border: `1px solid ${color}25`,
          transition: 'transform .2s ease, box-shadow .2s ease' }}>
          <Icon size={17} stroke={color} />
        </div>
      </div>
    </div>
  );
});

const PipelineList = memo(function PipelineList({ pipeline, stages }) {
  const total = Object.values(pipeline).reduce((s, n) => s + (n ?? 0), 0);
  if (total === 0) return (
    <div style={{ textAlign: 'center', padding: '28px 0', color: C.muted, fontSize: 13 }}>
      No submissions yet
    </div>
  );
  return stages.map(({ key, label, color }) => {
    const n   = pipeline[key] ?? 0;
    const pct = total ? n / total : 0;
    return (
      <div key={key} style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: color, flexShrink: 0 }} />
            <span style={{ fontSize: 12, color: C.subtle, fontWeight: 500 }}>{label}</span>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: C.text,
              fontFamily: "'JetBrains Mono',monospace" }}>{n}</span>
            <span style={{ fontSize: 10, color: C.muted, minWidth: 30, textAlign: 'right' }}>
              {Math.round(pct * 100)}%
            </span>
          </div>
        </div>
        <ProgressBar value={pct * 100} color={color} />
      </div>
    );
  });
});

const InsightChip = memo(function InsightChip({ icon: Icon, label, value, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '8px 12px',
      borderRadius: 8, background: `${color}0d`, border: `1px solid ${color}22` }}>
      <Icon size={13} stroke={color} />
      <span style={{ fontSize: 11, color: C.muted }}>{label}</span>
      <span style={{ fontSize: 12, fontWeight: 700, color,
        fontFamily: "'JetBrains Mono',monospace", marginLeft: 'auto' }}>{value}</span>
    </div>
  );
});

// ── Role Distribution Card ─────────────────────────────────────────────────────

function RoleDistributionCard({ roleData, selectedSchool }) {
  const [activeIdx, setActiveIdx] = useState(null);
  const total = roleData.reduce((s, r) => s + r.value, 0);
  const active = activeIdx !== null ? roleData[activeIdx] : null;

  const activeShape = (props) => {
    const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill } = props;
    return (
      <Sector cx={cx} cy={cy}
        innerRadius={innerRadius - 3} outerRadius={outerRadius + 7}
        startAngle={startAngle} endAngle={endAngle}
        fill={fill}
      />
    );
  };

  return (
    <Card
      title="Role Distribution"
      sub={selectedSchool ? 'University-wide (role data not school-specific)' : 'Faculty breakdown by role'}
      delay={140}
      info="Donut shows how many registered users belong to each role. Hover a slice or row to highlight. Admin accounts excluded.">

      {selectedSchool && (
        <div style={{
          marginBottom: 12, padding: '8px 12px', borderRadius: 7, fontSize: 11,
          color: C.muted, background: 'rgba(255,255,255,.03)',
          border: '1px solid rgba(255,255,255,.07)',
        }}>
          Role breakdown is available university-wide only.
        </div>
      )}

      {roleData.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '28px 0', color: C.muted, fontSize: 13 }}>
          No role data
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, alignItems: 'flex-start' }}>

          {/* Donut with dynamic center */}
          <div style={{ position: 'relative' }}>
            <ResponsiveContainer width="100%" height={185}>
              <PieChart>
                <Pie
                  data={roleData}
                  cx="50%" cy="50%"
                  innerRadius={48} outerRadius={70}
                  dataKey="value"
                  strokeWidth={0}
                  paddingAngle={2}
                  activeIndex={activeIdx ?? undefined}
                  activeShape={activeShape}
                  onMouseEnter={(_, i) => setActiveIdx(i)}
                  onMouseLeave={() => setActiveIdx(null)}
                >
                  {roleData.map((r, i) => (
                    <Cell
                      key={r.name}
                      fill={r.color}
                      opacity={activeIdx !== null && activeIdx !== i ? 0.35 : 1}
                    />
                  ))}
                </Pie>
                <Tooltip content={<ChartTip />} />
              </PieChart>
            </ResponsiveContainer>

            {/* Center overlay — shows active role or total */}
            <div style={{
              position: 'absolute', top: '50%', left: '50%',
              transform: 'translate(-50%, -50%)',
              textAlign: 'center', pointerEvents: 'none',
            }}>
              <div style={{
                fontFamily: "'JetBrains Mono',monospace",
                fontSize: active ? 20 : 22,
                fontWeight: 800, lineHeight: 1,
                color: active ? active.color : C.text,
                transition: 'color .15s ease',
              }}>
                {active ? active.value : total}
              </div>
              <div style={{ fontSize: 9, color: C.muted, marginTop: 3, letterSpacing: .4 }}>
                {active
                  ? `${Math.round(active.value / total * 100)}%`
                  : 'registered'}
              </div>
            </div>
          </div>

          {/* Enhanced legend */}
          <div style={{ paddingTop: 4 }}>
            {roleData.map((r, i) => {
              const pct = total ? Math.round(r.value / total * 100) : 0;
              const isActive = activeIdx === i;
              const isDimmed = activeIdx !== null && !isActive;
              return (
                <div
                  key={r.name}
                  onMouseEnter={() => setActiveIdx(i)}
                  onMouseLeave={() => setActiveIdx(null)}
                  style={{
                    padding: '5px 7px', borderRadius: 7, marginBottom: 3,
                    cursor: 'default',
                    background: isActive ? `${r.color}12` : 'transparent',
                    border: `1px solid ${isActive ? `${r.color}35` : 'transparent'}`,
                    opacity: isDimmed ? 0.4 : 1,
                    transition: 'all .15s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 }}>
                    <div style={{
                      width: 9, height: 9, borderRadius: 3, flexShrink: 0,
                      background: r.color,
                      boxShadow: isActive ? `0 0 6px ${r.color}80` : 'none',
                    }} />
                    <span style={{
                      fontSize: 11, flex: 1,
                      color: isActive ? C.text : C.subtle,
                      fontWeight: isActive ? 600 : 400,
                    }}>
                      {r.name}
                    </span>
                    <span style={{
                      fontSize: 11, fontWeight: 700, color: r.color,
                      fontFamily: "'JetBrains Mono',monospace",
                    }}>
                      {r.value}
                    </span>
                    <span style={{
                      fontSize: 10, color: C.muted, minWidth: 26, textAlign: 'right',
                      fontFamily: "'JetBrains Mono',monospace",
                    }}>
                      {pct}%
                    </span>
                  </div>
                  <div style={{ height: 3, borderRadius: 2, background: 'rgba(255,255,255,.06)' }}>
                    <div style={{
                      height: '100%', borderRadius: 2,
                      width: `${pct}%`,
                      background: r.color,
                      transition: 'width .4s ease, opacity .15s ease',
                      opacity: isActive ? 1 : 0.6,
                    }} />
                  </div>
                </div>
              );
            })}
          </div>

        </div>
      )}
    </Card>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function OverviewPage() {
  const [year,           setYear]           = useState('');
  const [selectedSchool, setSelectedSchool] = useState('');
  const [downloading,    setDownloading]    = useState(null);
  const [downloadErr,    setDownloadErr]    = useState(null);

  const { data: raw, loading: statsLoading, error, lastUpdated } = useFetch(
    () => api.stats.get(year || undefined),
    [year],
    { interval: AUTO_REFRESH_INTERVAL },
  );

  const { data: rawUsers, loading: usersLoading } = useFetch(
    () => api.users.list(),
    [],
    { interval: AUTO_REFRESH_INTERVAL },
  );

  const { data: rawSubs, loading: subsLoading } = useFetch(
    () => raw?.academic_year
      ? api.submissions.list({ academic_year: raw.academic_year }).catch(() => null)
      : Promise.resolve(null),
    [raw?.academic_year],
    { interval: AUTO_REFRESH_INTERVAL },
  );

  const loading = statsLoading || usersLoading || subsLoading;

  const [roleFilter, setRoleFilter]     = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [search, setSearch]             = useState('');

  // ── Memoized normalization — only re-runs when raw data changes ─────────────
  const stats = useMemo(() => normalizeStats(raw), [raw]);
  const { bySchool, bySchoolSub, pipeline, nonTeachingPipeline, byRole } = stats;

  const allUsers = useMemo(() => normalizeUsers(rawUsers ?? []), [rawUsers]);

  const subStatusMap = useMemo(() => {
    const map = {};
    if (Array.isArray(rawSubs)) rawSubs.forEach(s => { if (s.email) map[s.email] = s.status; });
    return map;
  }, [rawSubs]);

  const subSubmittedAtMap = useMemo(() => {
    const map = {};
    if (Array.isArray(rawSubs)) rawSubs.forEach(s => { if (s.email) map[s.email] = s.submitted_at; });
    return map;
  }, [rawSubs]);

  const TEACHING_ROLES = useMemo(() => new Set(['faculty', 'hod', 'director', 'dean', 'center_head']), []);
  const ROLE_LABELS = useMemo(() => ({
    faculty: 'Faculty', hod: 'HOD', director: 'Director',
    dean: 'Dean', vc: 'VC', registrar: 'Registrar', center_head: 'Center Head',
  }), []);

  const STATUS_CFG = useMemo(() => ({
    'Reviewed':                { color: C.green,   label: 'Reviewed'          },
    'Pending VC Review':       { color: '#a78bfa', label: 'VC Review'         },
    'Pending Dean Review':     { color: C.accent,  label: 'Dean Review'       },
    'Pending Director Review': { color: C.yellow,  label: 'Director Review'   },
    'Pending Review':          { color: C.orange,  label: 'HOD Review'        },
    'Submitted':               { color: C.orange,  label: 'HOD Review'        },
  }), []);

  const mergedUsers = useMemo(() => {
    return allUsers
      .filter(u => TEACHING_ROLES.has(u.role))
      .map(u => ({
        ...u,
        declStatus: subStatusMap[u.email] ?? null,
        submittedAt: subSubmittedAtMap[u.email] ?? null,
      }))
      .sort((a, b) => {
        const order = { 'Reviewed': 0, 'Pending VC Review': 1, 'Pending Dean Review': 2,
          'Pending Director Review': 3, 'Pending Review': 4, 'Submitted': 4 };
        const oa = a.declStatus ? (order[a.declStatus] ?? 5) : 6;
        const ob = b.declStatus ? (order[b.declStatus] ?? 5) : 6;
        return oa - ob || (a.name || '').localeCompare(b.name || '');
      });
  }, [allUsers, subStatusMap, subSubmittedAtMap, TEACHING_ROLES]);

  const filteredUsers = useMemo(() => mergedUsers.filter(u => {
    if (selectedSchool && selectedSchool !== '__nt__' && u.school !== selectedSchool) return false;
    if (roleFilter !== 'all' && u.role !== roleFilter) return false;
    if (statusFilter === 'not_submitted' && u.declStatus) return false;
    if (statusFilter !== 'all' && statusFilter !== 'not_submitted' && u.declStatus !== statusFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (u.name || '').toLowerCase().includes(q) || (u.email || '').toLowerCase().includes(q);
    }
    return true;
  }), [mergedUsers, selectedSchool, roleFilter, statusFilter, search]);

  const progressStats = useMemo(() => ({
    reviewed:      mergedUsers.filter(u => (selectedSchool && selectedSchool !== '__nt__' ? u.school === selectedSchool : true) && u.declStatus === 'Reviewed').length,
    inProgress:    mergedUsers.filter(u => (selectedSchool && selectedSchool !== '__nt__' ? u.school === selectedSchool : true) && u.declStatus && u.declStatus !== 'Reviewed').length,
    notSubmitted:  mergedUsers.filter(u => (selectedSchool && selectedSchool !== '__nt__' ? u.school === selectedSchool : true) && !u.declStatus).length,
  }), [mergedUsers, selectedSchool]);

  const NT_KEY = '__nt__';

  // ── All school-filtered derived values in one memo ──────────────────────────
  const derived = useMemo(() => {
    const isNT     = selectedSchool === NT_KEY;
    const isSchool = !!(selectedSchool && !isNT);
    const schoolRow = isSchool ? bySchool.find(s => s.name === selectedSchool) : null;

    const ntRegistered = (byRole?.non_teaching_staff ?? 0)
                       + (byRole?.reporting_officer ?? 0)
                       + (byRole?.registrar ?? 0);
    const ntSubmitted  = Object.values(nonTeachingPipeline).reduce((s, n) => s + (n ?? 0), 0);

    const filtPipeline = isNT ? nonTeachingPipeline
      : isSchool ? (bySchoolSub?.[selectedSchool] ?? {})
      : pipeline;

    const filtTotal = isNT ? ntRegistered : schoolRow ? schoolRow.total : stats.total;
    const filtSub   = isNT ? ntSubmitted  : schoolRow ? schoolRow.sub   : stats.submitted;
    const filtPend  = isNT ? (ntRegistered - ntSubmitted) : schoolRow ? schoolRow.pend : stats.pending;
    const filtRate  = filtTotal ? Math.round(filtSub / filtTotal * 100) : 0;
    const filtTTotal = Object.values(filtPipeline).reduce((s, n) => s + (n ?? 0), 0);

    const filtApproved = isNT ? (nonTeachingPipeline['VC Approved'] ?? 0)
      : isSchool ? (filtPipeline['Reviewed'] ?? 0)
      : (pipeline['Reviewed'] ?? 0) + (nonTeachingPipeline['VC Approved'] ?? 0);

    const activeStages    = isNT ? NT_STAGES
      : selectedSchool === 'CISR' ? CISR_STAGES
      : T_STAGES;
    const pipelineBarData = activeStages.map(({ key, label, color }) => ({
      status: label, count: filtPipeline[key] ?? 0, color,
    }));
    const cycleDonut = [
      { name: 'Submitted', value: filtSub,  color: C.green },
      { name: 'Pending',   value: filtPend, color: C.red   },
    ];

    return {
      isNT, isSchool, filtPipeline, filtTotal, filtSub, filtPend, filtRate,
      filtTTotal, ntTotal: ntSubmitted, filtApproved, activeStages,
      pipelineBarData, cycleDonut, ntRegistered,
    };
  }, [stats, selectedSchool, bySchool, bySchoolSub, pipeline, nonTeachingPipeline, byRole]);

  const {
    isNT, isSchool, filtPipeline, filtTotal, filtSub, filtPend, filtRate,
    filtTTotal, ntTotal, filtApproved, activeStages, pipelineBarData, cycleDonut,
    ntRegistered,
  } = derived;

  // ── School performance — sort only when school data or selection changes ─────
  const sortedSchools = useMemo(() =>
    [...bySchool].sort((a, b) => {
      if (selectedSchool) {
        if (a.name === selectedSchool) return -1;
        if (b.name === selectedSchool) return 1;
      }
      return (b.total ? b.sub / b.total : 0) - (a.total ? a.sub / a.total : 0);
    }),
    [bySchool, selectedSchool]
  );

  const [topSchool, bottomSchool, schoolRank] = useMemo(() => {
    const s = [...bySchool].sort((a, b) =>
      (b.total ? b.sub / b.total : 0) - (a.total ? a.sub / a.total : 0)
    );
    const rank = selectedSchool ? s.findIndex(r => r.name === selectedSchool) + 1 : 0;
    return [s[0], s[s.length - 1], rank];
  }, [bySchool, selectedSchool]);

  const roleData = useMemo(() =>
    Object.entries(byRole ?? {})
      .filter(([role]) => !['admin', 'super_admin'].includes(role))
      .map(([role, count]) => ({ name: fmtRole(role), value: count, color: ROLE_COLORS[role] ?? C.muted }))
      .filter(r => r.value > 0)
      .sort((a, b) => b.value - a.value),
    [byRole]
  );

  const handleExport = async (type) => {
    setDownloading(type); setDownloadErr(null);
    const params = year ? { academic_year: year } : {};
    try {
      const blob = await api.export[type](params);
      triggerDownload(blob, `${type}-${year || 'latest'}.csv`);
    } catch (e) {
      setDownloadErr(e.message);
    } finally {
      setDownloading(null);
    }
  };

  const schoolFullName = isNT ? 'Non-Teaching Staff'
                       : isSchool ? (SCHOOL_MAP[selectedSchool] ?? selectedSchool)
                       : null;

  return (
    <div className="page-enter">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
        <PageHead
          title="Overview"
          sub={selectedSchool
            ? isNT
              ? 'Showing data for Non-Teaching Staff'
              : `Showing data for ${selectedSchool} · ${schoolFullName}`
            : 'Real-time snapshot · submission pipeline · school analytics'}
          action={<LiveBadge lastUpdated={lastUpdated} />}
        />
        <select value={year} onChange={e => setYear(e.target.value)}
          style={{ ...inp, width: 'auto', minWidth: 140, cursor: 'pointer', fontSize: 12, marginTop: 4 }}>
          <option value="">Latest cycle</option>
          {(stats.availableYears ?? []).map(y => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>

      {/* ── School selector ─────────────────────────────────────────────────── */}
      <div style={{ marginBottom: 16 }}>

        {/* Dropdown — full school names */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: C.muted,
            textTransform: 'uppercase', letterSpacing: .6, whiteSpace: 'nowrap' }}>
            Filter by School
          </span>

          <select
            value={selectedSchool}
            onChange={e => setSelectedSchool(e.target.value)}
            style={{
              ...inp, width: 'auto', flex: 1, maxWidth: 420,
              cursor: 'pointer', fontSize: 12,
              color: selectedSchool ? C.accent : C.subtle,
              borderColor: selectedSchool ? `${C.accent}55` : undefined,
              background: selectedSchool ? `${C.accent}08` : undefined,
            }}>
            <option value="">All Schools</option>
            {SCHOOLS.map(s => {
              const sRow = bySchool.find(r => r.name === s.code);
              const pct  = sRow && sRow.total ? Math.round(sRow.sub / sRow.total * 100) : null;
              return (
                <option key={s.code} value={s.code}>
                  {s.code} — {s.full}{pct !== null ? `  (${pct}%)` : ''}
                </option>
              );
            })}
            <option disabled>──────────────</option>
            <option value={NT_KEY}>
              Non-Teaching Staff{ntRegistered ? `  (${ntRegistered} registered)` : ''}
            </option>
          </select>
          {selectedSchool && (
            <button className="act-btn" onClick={() => setSelectedSchool('')} style={{
              padding: '6px 12px', borderRadius: 7, fontSize: 12, fontWeight: 600,
              cursor: 'pointer', whiteSpace: 'nowrap',
              border: '1px solid rgba(248,113,113,.25)',
              background: 'rgba(248,113,113,.08)',
              color: C.red,
            }}>
              Clear ×
            </button>
          )}
        </div>

      </div>

      {loading && <Loading />}
      {error   && <ApiError message={error} />}

      {!loading && !error && (
        <>
          {/* ── KPI row ─────────────────────────────────────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
            <KPI label={isNT ? 'Non-Teaching Staff' : isSchool ? `${selectedSchool} Faculty` : 'Total Faculty'}
              value={filtTotal}    sub={isNT ? 'Registered staff' : isSchool ? schoolFullName : 'Registered'}
              color={C.accent}   icon={I.users}  delay={0} />
            <KPI label="Submitted"
              value={filtSub}    sub={`${filtRate}% completion`}
              color={C.green}    icon={I.check}  delay={60} />
            <KPI label="Pending"
              value={filtPend}   sub="Yet to submit"
              color={C.red}      icon={I.clock}  delay={120} />
            <KPI label="Fully Approved"
              value={filtApproved}
              sub={isNT ? 'VC approved' : isSchool ? 'Teaching only' : 'Teaching + Non-Teaching'}
              delay={180}
              color='#22d3ee'    icon={I.shield} />
          </div>

          {/* ── Insights / School context ───────────────────────────────────── */}
          {!selectedSchool && !isNT && bySchool.length > 0 && (
            <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
              <InsightChip icon={I.star}  label="Top school"      color={C.green}
                value={topSchool ? `${topSchool.name} · ${Math.round(topSchool.sub / (topSchool.total || 1) * 100)}%` : '—'} />
              <InsightChip icon={I.clock} label="Needs attention" color={C.red}
                value={bottomSchool ? `${bottomSchool.name} · ${Math.round(bottomSchool.sub / (bottomSchool.total || 1) * 100)}%` : '—'} />
              <InsightChip icon={I.chart} label="Teaching pipeline"    color={C.accent} value={`${filtTTotal} in-progress`} />
              {ntTotal > 0 && (
                <InsightChip icon={I.doc} label="Non-teaching pipeline" color={C.yellow} value={`${ntTotal} in-progress`} />
              )}
            </div>
          )}

          {/* NT insight chips */}
          {isNT && (
            <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
              <InsightChip icon={I.star}  label="Completion rate" color={C.green}  value={`${filtRate}%`} />
              <InsightChip icon={I.chart} label="In pipeline"     color={C.accent} value={`${filtTTotal} forms`} />
              <InsightChip icon={I.check} label="VC Approved"     color='#22d3ee'  value={`${filtApproved}`} />
              <InsightChip icon={I.clock} label="Pending"         color={C.red}    value={`${filtPend} remaining`} />
            </div>
          )}

          {/* School context banner */}
          {isSchool && (() => {
            const rateCol = filtRate >= 75 ? C.green : filtRate >= 40 ? C.yellow : C.red;
            const stats2x2 = [
              { label: 'Submitted',   value: filtSub,      color: C.green   },
              { label: 'Pending',     value: filtPend,     color: C.red     },
              { label: 'In Pipeline', value: filtTTotal,   color: C.accent  },
              { label: 'Approved',    value: filtApproved, color: '#22d3ee' },
            ];
            return (
              <div style={{
                marginBottom: 16, borderRadius: 12, overflow: 'hidden',
                background: 'var(--c-card)',
                border: `1px solid ${C.accent}28`,
                boxShadow: `0 0 28px ${C.accent}08`,
              }}>
                {/* Accent top bar */}
                <div style={{ height: 3, background: `linear-gradient(90deg,${C.accent},${C.accent}50,transparent)` }} />

                <div style={{ padding: '16px 20px' }}>
                  {/* Top row: school identity + rank + rate */}
                  <div style={{ display: 'flex', gap: 20, alignItems: 'center', flexWrap: 'wrap', marginBottom: 14 }}>

                    {/* School code + name */}
                    <div style={{ minWidth: 0 }}>
                      <div style={{
                        fontFamily: "'JetBrains Mono',monospace", fontSize: 26, fontWeight: 900,
                        color: C.accent, letterSpacing: -1, lineHeight: 1,
                      }}>
                        {selectedSchool}
                      </div>
                      <div style={{ fontSize: 12, color: C.muted, marginTop: 4 }}>{schoolFullName}</div>
                    </div>

                    <div style={{ width: 1, height: 36, background: 'var(--c-divider)', flexShrink: 0 }} />

                    {/* Rank */}
                    <div style={{ textAlign: 'center' }}>
                      <div style={{
                        fontFamily: "'JetBrains Mono',monospace", fontSize: 22, fontWeight: 800,
                        color: schoolRank === 1 ? C.green : C.text, lineHeight: 1,
                      }}>
                        #{schoolRank}
                      </div>
                      <div style={{ fontSize: 10, color: C.muted, marginTop: 3 }}>
                        of {bySchool.length} schools
                      </div>
                    </div>

                    <div style={{ width: 1, height: 36, background: 'var(--c-divider)', flexShrink: 0 }} />

                    {/* Completion rate */}
                    <div style={{ textAlign: 'center' }}>
                      <div style={{
                        fontFamily: "'JetBrains Mono',monospace", fontSize: 22, fontWeight: 800,
                        color: rateCol, lineHeight: 1,
                      }}>
                        {filtRate}%
                      </div>
                      <div style={{ fontSize: 10, color: C.muted, marginTop: 3 }}>completion</div>
                    </div>

                    <div style={{ width: 1, height: 36, background: 'var(--c-divider)', flexShrink: 0 }} />

                    {/* Submitted fraction */}
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ lineHeight: 1, fontFamily: "'JetBrains Mono',monospace" }}>
                        <span style={{ fontSize: 22, fontWeight: 800, color: C.green }}>{filtSub}</span>
                        <span style={{ fontSize: 14, color: C.muted }}> / </span>
                        <span style={{ fontSize: 18, fontWeight: 700, color: C.text }}>{filtTotal}</span>
                      </div>
                      <div style={{ fontSize: 10, color: C.muted, marginTop: 3 }}>submitted</div>
                    </div>

                    {/* Progress bar — fills remaining space */}
                    <div style={{ flex: 1, minWidth: 100 }}>
                      <div style={{ height: 8, borderRadius: 4, background: 'rgba(255,255,255,.06)' }}>
                        <div style={{
                          height: '100%', borderRadius: 4,
                          width: `${filtRate}%`,
                          background: `linear-gradient(90deg,${rateCol},${rateCol}80)`,
                          transition: 'width .6s ease',
                        }} />
                      </div>
                    </div>
                  </div>

                  {/* Bottom 4-stat row */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8 }}>
                    {stats2x2.map(s => (
                      <div key={s.label} style={{
                        padding: '9px 12px', borderRadius: 8,
                        background: `${s.color}08`, border: `1px solid ${s.color}1a`,
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      }}>
                        <span style={{ fontSize: 11, color: C.muted }}>{s.label}</span>
                        <span style={{
                          fontSize: 16, fontWeight: 800, color: s.color,
                          fontFamily: "'JetBrains Mono',monospace",
                        }}>
                          {s.value}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })()}

          {/* ── Bar chart + Donut ───────────────────────────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 14, marginBottom: 14 }}>

            {/* Vertical bar chart — submission stages */}
            <Card
              title="Submission Pipeline"
              sub={isNT ? 'Non-Teaching — Count per review stage'
                 : isSchool ? `${selectedSchool} — Count per review stage`
                 : 'Count per review stage (teaching)'}
              delay={0}
              info="Each bar shows how many appraisal forms are currently sitting at that review stage.">
              {filtTTotal === 0 ? (
                <div style={{ height: 210, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: C.muted, fontSize: 13 }}>No submissions yet</div>
              ) : (
                <ResponsiveContainer width="100%" height={210}>
                  <BarChart data={pipelineBarData} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.04)" />
                    <XAxis dataKey="status" tick={{ fill: C.muted, fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTip />} />
                    <Bar dataKey="count" name="Submissions" radius={[4, 4, 0, 0]}>
                      {pipelineBarData.map((entry) => (
                        <Cell key={entry.status} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>

            {/* Donut — cycle split */}
            <Card
              title="Cycle Split"
              sub={isNT ? 'Non-Teaching — Current year'
                 : isSchool ? `${selectedSchool} — Current year`
                 : 'Current year'}
              delay={60}
              info="Donut shows the ratio of submitted forms (green) to not-yet-submitted / pending faculty (red) for the selected academic year. Hover a segment for exact counts.">
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
                <div style={{ position: 'relative', width: '100%' }}>
                  <ResponsiveContainer width="100%" height={155}>
                    <PieChart>
                      <Pie data={cycleDonut} cx="50%" cy="50%" innerRadius={46} outerRadius={66}
                        strokeWidth={0} dataKey="value">
                        {cycleDonut.map((e) => <Cell key={e.name} fill={e.color} />)}
                      </Pie>
                      <Tooltip content={<ChartTip />} />
                    </PieChart>
                  </ResponsiveContainer>
                  {/* Centered rate label inside donut */}
                  <div style={{
                    position: 'absolute', top: '50%', left: '50%',
                    transform: 'translate(-50%, -50%)',
                    textAlign: 'center', pointerEvents: 'none',
                  }}>
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 18, fontWeight: 800,
                      color: filtRate >= 75 ? C.green : filtRate >= 40 ? C.yellow : C.red, lineHeight: 1 }}>
                      {filtRate}%
                    </div>
                    <div style={{ fontSize: 9, color: C.muted, marginTop: 2, letterSpacing: .4 }}>done</div>
                  </div>
                </div>

                {/* Legend */}
                <div style={{ display: 'flex', gap: 16 }}>
                  {cycleDonut.map(p => (
                    <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: p.color }} />
                      <span style={{ color: C.subtle }}>{p.name}</span>
                      <span style={{ color: C.text, fontWeight: 700,
                        fontFamily: "'JetBrains Mono',monospace" }}>{p.value}</span>
                    </div>
                  ))}
                </div>

                {/* Progress bar */}
                <div style={{ width: '100%', marginTop: 4 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                    <span style={{ fontSize: 10, color: C.muted }}>Completion</span>
                    <span style={{ fontSize: 10, color: C.muted, fontFamily: "'JetBrains Mono',monospace" }}>
                      {filtSub} / {filtTotal}
                    </span>
                  </div>
                  <div style={{ height: 6, borderRadius: 4, background: 'rgba(255,255,255,.06)', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%', borderRadius: 4,
                      width: `${filtRate}%`,
                      background: filtRate >= 75
                        ? `linear-gradient(90deg, ${C.green}, #10b981)`
                        : filtRate >= 40
                        ? `linear-gradient(90deg, ${C.yellow}, #f59e0b)`
                        : `linear-gradient(90deg, ${C.red}, #ef4444)`,
                      transition: 'width .6s ease',
                    }} />
                  </div>
                </div>

                {/* Approved callout */}
                {filtApproved > 0 && (
                  <div style={{
                    width: '100%', marginTop: 2, padding: '8px 12px', borderRadius: 8,
                    background: 'rgba(52,211,153,.07)', border: '1px solid rgba(52,211,153,.18)',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  }}>
                    <span style={{ fontSize: 11, color: C.muted }}>Fully Approved</span>
                    <span style={{ fontSize: 14, fontWeight: 800, color: C.green,
                      fontFamily: "'JetBrains Mono',monospace" }}>
                      {filtApproved}
                    </span>
                  </div>
                )}
              </div>
            </Card>
          </div>

          {/* ── Progress-bar pipelines ───────────────────────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
            <Card
              title={isNT ? 'Non-Teaching Pipeline' : 'Teaching Pipeline'}
              sub={isNT ? 'RO → Registrar → VC review stages'
                 : isSchool ? `${selectedSchool} — Forms by review stage`
                 : 'Forms by review stage'}
              delay={80}
              info="Progress bars break down appraisal forms by their current review stage.">
              <PipelineList pipeline={filtPipeline} stages={activeStages} />
            </Card>
            {!isNT && (
              <Card
                title="Non-Teaching Pipeline"
                sub={isSchool ? 'University-wide (no school breakdown)' : 'Staff forms by review stage'}
                delay={100}
                info="Tracks non-teaching staff forms from Reporting Officer review through Registrar to final VC approval.">
                {isSchool && (
                  <div style={{
                    marginBottom: 12, padding: '8px 12px', borderRadius: 7, fontSize: 11,
                    color: C.yellow, background: 'rgba(251,191,36,.07)',
                    border: '1px solid rgba(251,191,36,.18)',
                  }}>
                    Non-teaching staff are not assigned to a school. Showing university-wide data.
                  </div>
                )}
                <PipelineList pipeline={nonTeachingPipeline} stages={NT_STAGES} />
              </Card>
            )}
          </div>

          {/* ── School performance ──────────────────────────────────────────── */}
          {bySchool.length > 0 && !isNT && (
            <Card title="School Performance"
              sub={selectedSchool ? `${selectedSchool} highlighted — all schools compared` : 'Submitted vs pending — all schools'}
              delay={120} style={{ marginBottom: 14 }}
              info="Each horizontal bar is one school — blue segment = submitted forms, red segment = still pending. The right table ranks all schools by completion percentage for quick comparison.">
              <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: 24 }}>

                {/* Stacked horizontal bar chart */}
                <ResponsiveContainer width="100%" height={bySchool.length * 44 + 20}>
                  <BarChart layout="vertical" data={sortedSchools}
                    margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.04)" horizontal={false} />
                    <XAxis type="number" tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="name" width={58}
                      tick={{ fill: C.subtle, fontSize: 11, fontFamily: "'JetBrains Mono',monospace" }}
                      axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTip />} />
                    <Bar dataKey="sub"  name="Submitted" radius={[0, 0, 0, 0]} stackId="a">
                      {sortedSchools.map((s) => (
                        <Cell key={s.name}
                          fill={s.name === selectedSchool ? C.accent : `${C.accent}60`}
                          opacity={selectedSchool && s.name !== selectedSchool ? 0.45 : 1}
                        />
                      ))}
                    </Bar>
                    <Bar dataKey="pend" name="Pending" radius={[0, 4, 4, 0]} stackId="a">
                      {sortedSchools.map((s) => (
                        <Cell key={s.name}
                          fill="rgba(248,113,113,.25)"
                          opacity={selectedSchool && s.name !== selectedSchool ? 0.45 : 1}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>

                {/* Completion rate table */}
                <div>
                  <div style={{ fontSize: 10, fontWeight: 700, color: C.muted, letterSpacing: .7,
                    textTransform: 'uppercase', marginBottom: 10, paddingBottom: 6,
                    borderBottom: '1px solid rgba(255,255,255,.05)' }}>
                    Completion Rate
                  </div>
                  {sortedSchools.map((s, i) => {
                    const pct = s.total ? s.sub / s.total : 0;
                    const { badge } = rateColor(pct);
                    const isSelected = s.name === selectedSchool;
                    return (
                      <div key={s.name}
                        style={{
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                          padding: '7px 8px', borderRadius: 6,
                          background: isSelected ? `${C.accent}0e` : 'transparent',
                          border: `1px solid ${isSelected ? `${C.accent}30` : 'transparent'}`,
                          marginBottom: 2,
                        }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 10, color: C.muted, fontFamily: "'JetBrains Mono',monospace",
                            minWidth: 14, textAlign: 'right' }}>#{i + 1}</span>
                          <span style={{ fontSize: 12,
                            color: isSelected ? C.accent : C.subtle,
                            fontFamily: "'JetBrains Mono',monospace",
                            fontWeight: isSelected ? 700 : 400 }}>{s.name}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                          <span style={{ fontSize: 10, color: C.muted,
                            fontFamily: "'JetBrains Mono',monospace" }}>{s.sub}/{s.total}</span>
                          <Badge color={badge}>{Math.round(pct * 100)}%</Badge>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </Card>
          )}

          {/* ── Role distribution + Export ───────────────────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>

            <RoleDistributionCard roleData={roleData} selectedSchool={selectedSchool} />

            {/* Export reports */}
            <Card title="Export Reports" sub="Download data as CSV" delay={140}>
              {[
                { key: 'submissions', label: 'Submission Report',
                  desc: 'All declarations with current review stage', icon: I.doc  },
                { key: 'faculty',     label: 'Faculty Export',
                  desc: 'Faculty list with school, role and status',  icon: I.users },
              ].map((e, i) => (
                <div key={e.key} style={{ display: 'flex', justifyContent: 'space-between',
                  alignItems: 'center', padding: '13px 0',
                  borderBottom: i === 0 ? '1px solid var(--c-divider)' : 'none' }}>
                  <div style={{ display: 'flex', gap: 11, alignItems: 'center' }}>
                    <div style={{ width: 34, height: 34, borderRadius: 9, flexShrink: 0,
                      background: 'var(--c-soft-bg)', border: '1px solid var(--c-divider)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <e.icon size={15} stroke={C.muted} />
                    </div>
                    <div>
                      <div style={{ fontSize: 13, color: C.text, fontWeight: 600 }}>{e.label}</div>
                      <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>{e.desc}</div>
                    </div>
                  </div>
                  <button className="act-btn" disabled={downloading === e.key}
                    onClick={() => handleExport(e.key)}
                    style={{ ...smBtn, display: 'flex', alignItems: 'center', gap: 5,
                      opacity: downloading === e.key ? .5 : 1 }}>
                    <I.dl size={12} />
                    {downloading === e.key ? '…' : 'CSV'}
                  </button>
                </div>
              ))}

              {downloadErr && (
                <div style={{ marginTop: 10, fontSize: 12, color: C.red }}>{downloadErr}</div>
              )}

              {/* ── Pipeline breakdown ── */}
              <div style={{ marginTop: 16, borderTop: '1px solid var(--c-divider)', paddingTop: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: .6, textTransform: 'uppercase', color: C.muted }}>
                    Submission CSV preview{year ? ` · ${year}` : ''}
                  </span>
                  <span style={{ fontSize: 10, color: C.muted, fontFamily: "'JetBrains Mono',monospace" }}>
                    {filtTTotal} rows
                  </span>
                </div>

                {filtTTotal === 0 ? (
                  <div style={{ textAlign: 'center', padding: '16px 0', fontSize: 12, color: C.muted }}>
                    No submissions in pipeline
                  </div>
                ) : (() => {
                  const maxCount = Math.max(1, ...pipelineBarData.map(s => s.count));
                  return pipelineBarData.filter(s => s.count > 0).map(s => (
                    <div key={s.status} style={{ marginBottom: 7 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                        <span style={{ fontSize: 11, color: C.subtle }}>{s.status}</span>
                        <span style={{ fontSize: 11, fontWeight: 700, color: s.color,
                          fontFamily: "'JetBrains Mono',monospace" }}>{s.count}</span>
                      </div>
                      <div style={{ height: 5, borderRadius: 3, background: 'rgba(255,255,255,.06)' }}>
                        <div style={{
                          height: '100%', borderRadius: 3,
                          width: `${Math.round(s.count / maxCount * 100)}%`,
                          background: s.color,
                          transition: 'width .5s ease',
                        }} />
                      </div>
                    </div>
                  ));
                })()}

                {/* Faculty export row count */}
                <div style={{
                  marginTop: 12, padding: '8px 12px', borderRadius: 8,
                  background: 'rgba(59,130,246,.06)', border: '1px solid rgba(59,130,246,.15)',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}>
                  <span style={{ fontSize: 11, color: C.muted }}>Faculty CSV rows</span>
                  <span style={{ fontSize: 13, fontWeight: 800, color: '#3b82f6',
                    fontFamily: "'JetBrains Mono',monospace" }}>
                    {stats.total}
                  </span>
                </div>
              </div>

            </Card>

          </div>

          {/* Detailed Faculty Progress lookup directory */}
          <Card title="Faculty Submission Progress" sub="Real-time individual progress and submission timestamps" delay={160}>
            <div>
              {/* Filter controls row */}
              <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
                <input value={search} onChange={e => setSearch(e.target.value)}
                  placeholder="Search name or email…"
                  style={{
                    background: 'rgba(255,255,255,.05)', border: '1px solid rgba(255,255,255,.1)',
                    borderRadius: 7, padding: '6px 11px', color: C.text, fontSize: 12,
                    outline: 'none', width: 220,
                  }}
                />

                <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
                  {[
                    { label: 'Reviewed',      color: C.green,  count: progressStats.reviewed     },
                    { label: 'In Progress',   color: C.yellow, count: progressStats.inProgress   },
                    { label: 'Not Submitted', color: C.red,    count: progressStats.notSubmitted },
                  ].map(s => (
                    <div key={s.label} style={{
                      display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px',
                      borderRadius: 7, background: `${s.color}0d`, border: `1px solid ${s.color}20`,
                    }}>
                      <div style={{ width: 6, height: 6, borderRadius: '50%', background: s.color }} />
                      <span style={{ fontSize: 10, color: C.muted }}>{s.label}</span>
                      <span style={{ fontSize: 13, fontWeight: 800, color: s.color, fontFamily: "'JetBrains Mono',monospace" }}>{s.count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Role + status filter buttons / select */}
              <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
                {['all', 'faculty', 'hod', 'director', 'dean', 'center_head'].map(r => {
                  const cnt = r === 'all' ? mergedUsers.length : mergedUsers.filter(u => u.role === r).length;
                  const active = roleFilter === r;
                  return (
                    <button key={r} className="act-btn" onClick={() => setRoleFilter(r)} style={{
                      padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: active ? 700 : 500,
                      cursor: 'pointer',
                      background: active ? `${C.accent}15` : 'transparent',
                      border: `1px solid ${active ? C.accent : 'rgba(255,255,255,.08)'}`,
                      color: active ? C.accent : C.muted,
                    }}>
                      {r === 'all' ? 'All Roles' : (ROLE_LABELS[r] ?? r)}
                      <span style={{ opacity: .55, marginLeft: 4 }}>({cnt})</span>
                    </button>
                  );
                })}

                <div style={{ width: 1, height: 14, background: 'rgba(255,255,255,.1)', flexShrink: 0 }} />

                <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{
                  background: 'rgba(255,255,255,.05)', border: '1px solid rgba(255,255,255,.12)',
                  borderRadius: 6, padding: '4px 8px', color: C.text, fontSize: 11, cursor: 'pointer',
                }}>
                  {[
                    { k: 'all',                       label: 'All Statuses'     },
                    { k: 'Reviewed',                  label: 'Reviewed'         },
                    { k: 'Pending VC Review',         label: 'VC Review'        },
                    { k: 'Pending Dean Review',       label: 'Dean Review'      },
                    { k: 'Pending Director Review',   label: 'Director Review'  },
                    { k: 'Submitted',                 label: 'HOD Review'       },
                    { k: 'not_submitted',             label: 'Not Submitted'    },
                  ].map(f => <option key={f.k} value={f.k}>{f.label}</option>)}
                </select>
              </div>

              {/* Table */}
              {filteredUsers.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '30px 0', color: C.muted, fontSize: 12 }}>
                  No records match your filters.
                </div>
              ) : (
                <div style={{
                  borderRadius: 10, border: '1px solid rgba(255,255,255,.06)',
                  background: 'rgba(255,255,255,.015)', overflow: 'hidden',
                }}>
                  {/* Table header */}
                  <div style={{
                    display: 'grid', gridTemplateColumns: '1fr 100px 100px 170px 130px',
                    padding: '8px 14px', borderBottom: '1px solid rgba(255,255,255,.06)',
                    background: 'rgba(255,255,255,.03)',
                  }}>
                    {['Name / Email', 'Role', 'School', 'Status', 'Submitted At'].map(h => (
                      <span key={h} style={{ fontSize: 10, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: .5 }}>{h}</span>
                    ))}
                  </div>

                  {filteredUsers.map((u, i) => {
                    const scfg = u.declStatus ? (STATUS_CFG[u.declStatus] ?? { color: C.muted, label: u.declStatus }) : null;
                    const fmtShort = iso => new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
                    return (
                      <div key={u.email} style={{
                        display: 'grid', gridTemplateColumns: '1fr 100px 100px 170px 130px',
                        padding: '9px 14px', alignItems: 'center',
                        borderBottom: i === filteredUsers.length - 1 ? 'none' : '1px solid rgba(255,255,255,.04)',
                      }}>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: C.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {u.name}
                          </div>
                          <div style={{ fontSize: 10, color: C.muted, fontFamily: "'JetBrains Mono',monospace", overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {u.email}
                          </div>
                        </div>
                        <div>
                          <span style={{
                            fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 5,
                            background: 'rgba(99,102,241,.12)', color: C.alt,
                          }}>
                            {ROLE_LABELS[u.role] ?? u.role}
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: C.muted }}>{u.school}</div>
                        <div>
                          {scfg
                            ? <span style={{
                                fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 5,
                                background: `${scfg.color}18`, border: `1px solid ${scfg.color}30`, color: scfg.color,
                              }}>{scfg.label}</span>
                            : <span style={{ fontSize: 10, color: C.muted }}>Not Submitted</span>
                          }
                        </div>
                        <div style={{ fontSize: 10, color: C.muted, fontFamily: "'JetBrains Mono',monospace" }}>
                          {u.submittedAt ? fmtShort(u.submittedAt) : '—'}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
