import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { C } from '../../constants/colors';
import { api } from '../../api/client';
import { logAction } from '../../utils/activityLog';
import { inp, lbl, pBtn, oBtn } from '../../constants/styleTokens';
import { ENGG_SCHOOLS, NON_ENGG_SCHOOLS, SOEMR_DEPTS } from '../../constants/schools';
import Card from '../../components/Card';
import Modal from '../../components/Modal';
import PageHead from '../../components/PageHead';
import { I } from '../../components/icons';
import WorkflowTimeline from '../../components/workflow/WorkflowTimeline';
import { useWorkflowTemplate } from '../../hooks/useWorkflow';

const ENGG_ROLES = [
  { value: 'faculty',  label: 'Faculty',             color: C.accent,  icon: I.users,  flow: 'HOD/Director → Dean (Eng) → VC'          },
  { value: 'hod',      label: 'HOD',                 color: '#a78bfa', icon: I.school, flow: 'Director (SoEMR) → Dean (Eng) → VC', soEmrOnly: true },
  { value: 'director', label: 'Director',            color: C.yellow,  icon: I.star,   flow: 'Dean (Engineering) → VC'                  },
  { value: 'dean',     label: 'Dean of Engineering', color: C.green,   icon: I.shield, flow: 'VC only'                                  },
];
const NON_ENGG_ROLES = [
  { value: 'faculty',  label: 'Faculty',                 color: C.accent, icon: I.users,  flow: 'Director → Dean (Non-Eng) → VC' },
  { value: 'director', label: 'Director',                color: C.yellow, icon: I.star,   flow: 'Dean (Non-Engineering) → VC'    },
  { value: 'dean',     label: 'Dean of Non-Engineering', color: C.green,  icon: I.shield, flow: 'VC only'                        },
];
const CISR_ROLES = [
  { value: 'faculty',     label: 'Faculty',     color: C.accent,  icon: I.users,  flow: 'Center Head → VC' },
  { value: 'center_head', label: 'Center Head', color: '#a78bfa', icon: I.shield, flow: 'VC only'          },
];
const NT_ROLES = [
  { value: 'non_teaching_staff', label: 'Staff',             color: C.accent,  icon: I.users, desc: 'Submits appraisal form · routed through assigned workflow template'    },
  { value: 'reporting_officer',  label: 'Reporting Officer', color: '#a78bfa', icon: I.doc,   desc: 'Reviews & scores NT staff appraisals routed to them'                   },
  { value: 'registrar',          label: 'Registrar',         color: C.yellow,  icon: I.star,  desc: 'Final institutional sign-off on non-teaching appraisals'               },
];

const STEPS = [
  { label: 'Classification', sub: 'Staff type & academic track'   },
  { label: 'Role & School',  sub: 'Position, school & department' },
  { label: 'Account',        sub: 'Login credentials'             },
  { label: 'Profile',        sub: 'Professional details'          },
];

const EMPTY = {
  full_name: '', email: '', password: 'demo123',
  school: '', department: '', appraisal_role: '',
  designation: '', phone: '', qualification: '', teaching_experience: '',
  workflow_template_id: '',
  reporting_officer_email: '',
  registrar_email: '',
};

// ── Appraisal flow computation ─────────────────────────────────────────────────

function computeFlow(staffType, track, role, school, dept, reportsDirectly = false) {
  if (!staffType || !role) return [];
  const n = (label, sub, sees, hides) => ({ label, sub, sees, hides });

  // Non-teaching and system flows are not computed here.
  if (staffType === 'non_teaching' || staffType === 'system') return [];

  if (track === 'cisr') {
    if (role === 'faculty') return [
      n('Faculty (CISR)', 'Fills and submits form', null, null),
      n('Center Head', 'Reviews & scores', 'Faculty self-score', null),
      n('VC', 'Final review & scores', 'Faculty + Center Head scores', null),
    ];
    if (role === 'center_head') return [
      n('Center Head (CISR)', 'Fills and submits form', null, null),
      n('VC', 'Reviews & scores', 'Center Head self-score', null),
    ];
    return [];
  }

  const isEng = track === 'engineering';
  const dean  = isEng ? 'Dean (Engineering)' : 'Dean (Non-Engineering)';
  const sc    = school || '—';

  if (role === 'faculty') {
    if (school === 'SoEMR') {
      const hod = dept ? `HOD — ${dept}` : 'HOD (select dept below)';
      return [
        n('Faculty (SoEMR)', 'Fills and submits form', null, null),
        n(hod, 'Reviews & scores', 'Faculty self-score', null),
        n('Director (SoEMR)', 'Reviews & scores', 'Faculty self-score only', 'HOD score hidden'),
        n(dean, 'Reviews & scores', 'Faculty self-score only', 'HOD + Director scores hidden'),
        n('VC', 'Final review & scores', 'All 4 scores: Faculty + HOD + Director + Dean', null),
      ];
    }
    return [
      n(`Faculty (${sc})`, 'Fills and submits form', null, null),
      n(`Director (${sc})`, 'Reviews & scores', 'Faculty self-score', null),
      isEng
        ? n(dean, 'Reviews & scores', 'Faculty self-score only', 'Director score hidden')
        : n(dean, 'Reviews & scores', 'Faculty + Director scores', null),
      n('VC', 'Final review & scores', 'All scores: Faculty + Director + Dean', null),
    ];
  }
  if (role === 'hod') {
    const hod = dept ? `HOD — ${dept}` : 'HOD (select dept below)';
    return [
      n(hod, 'Fills and submits form', null, null),
      n('Director (SoEMR)', 'Reviews & scores', 'HOD self-score', null),
      n(dean, 'Reviews & scores', 'HOD self-score only', 'Director score hidden'),
      n('VC', 'Final review & scores', 'HOD + Director + Dean scores', null),
    ];
  }
  if (role === 'director') return [
    n(`Director (${sc})`, 'Fills and submits form', null, null),
    n(dean, 'Reviews & scores', 'Director self-score', null),
    n('VC', 'Final review & scores', 'Director + Dean scores', null),
  ];
  if (role === 'dean') return [
    n(dean, 'Fills and submits form', null, null),
    n('VC', 'Reviews & scores', 'Dean self-score', null),
  ];
  return [];
}

// ── NT workflow helpers ────────────────────────────────────────────────────────

function resolveTemplateForToggles(templates, ntDirectVC, ntHasFirstReviewer, ntFirstReviewerType, ntRegRequired) {
  if (!templates.length) return null;
  const hasRO  = s => s.designation?.toLowerCase().includes('reporting officer');
  const hasDH  = s => s.designation?.toLowerCase().includes('head') || s.designation?.toLowerCase().includes('dept');
  const hasReg = s => s.designation?.toLowerCase().includes('registrar');
  const steps  = t => t.steps ?? [];
  if (ntDirectVC) {
    return templates.find(t => !steps(t).some(hasRO) && !steps(t).some(hasDH) && !steps(t).some(hasReg)) ?? null;
  }
  if (!ntHasFirstReviewer) {
    return templates.find(t => !steps(t).some(hasRO) && !steps(t).some(hasDH) && steps(t).some(hasReg)) ?? null;
  }
  const firstIs = ntFirstReviewerType === 'ro' ? hasRO : hasDH;
  return ntRegRequired
    ? templates.find(t => steps(t).some(firstIs) && steps(t).some(hasReg)) ?? null
    : templates.find(t => steps(t).some(firstIs) && !steps(t).some(hasReg)) ?? null;
}

function buildChainNodes(ntDirectVC, ntHasFirstReviewer, ntFirstReviewerType, ntRegRequired) {
  if (ntDirectVC) return ['Staff', 'VC'];
  if (!ntHasFirstReviewer) return ['Staff', 'Registrar', 'VC'];
  const first = ntFirstReviewerType === 'ro' ? 'Reporting Officer' : 'Dept Head';
  return ntRegRequired ? ['Staff', first, 'Registrar', 'VC'] : ['Staff', first, 'VC'];
}

function buildChainLabel(ntDirectVC, ntHasFirstReviewer, ntFirstReviewerType, ntRegRequired) {
  if (ntDirectVC) return 'Direct → VC';
  if (!ntHasFirstReviewer) return 'Registrar → VC';
  const first = ntFirstReviewerType === 'ro' ? 'RO' : 'Dept Head';
  return ntRegRequired ? `${first} → Registrar → VC` : `${first} → VC`;
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function Stepper({ current, steps: stepList = STEPS }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 28 }}>
      {stepList.map((s, i) => {
        const done   = i < current;
        const active = i === current;
        const col    = done ? C.green : active ? C.accent : 'rgba(255,255,255,.2)';
        const isLast = i === STEPS.length - 1;
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'flex-start', flex: isLast ? 'none' : 1 }}>
            {/* Circle + label */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, flexShrink: 0 }}>
              <div style={{
                width: 28, height: 28, borderRadius: '50%',
                border: `2px solid ${col}`,
                background: done ? C.green : active ? `${C.accent}1a` : 'transparent',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 700, color: done ? '#fff' : col,
                transition: 'all .25s', flexShrink: 0,
              }}>
                {done ? '✓' : i + 1}
              </div>
              <span style={{
                fontSize: 9, fontWeight: 700, letterSpacing: .5, textTransform: 'uppercase',
                color: col, whiteSpace: 'nowrap',
              }}>
                {s.label}
              </span>
            </div>
            {/* Connecting line — positioned at circle vertical center (14px from top) */}
            {!isLast && (
              <div style={{
                flex: 1, height: 1.5, marginTop: 13, marginLeft: 6, marginRight: 6,
                background: done ? C.green : 'rgba(255,255,255,.07)',
                transition: 'background .3s',
              }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// Large choice card (Teaching / Non-Teaching / tracks)
function ChoiceCard({ label, sub, icon: Icon, color, active, onClick }) {
  return (
    <button type="button" onClick={onClick} className="act-btn" style={{
      padding: '14px 16px', borderRadius: 10, textAlign: 'left', cursor: 'pointer', width: '100%',
      border: `1.5px solid ${active ? color : 'rgba(255,255,255,.07)'}`,
      background: active ? `${color}12` : 'rgba(255,255,255,.02)',
      position: 'relative',
    }}>
      {Icon && (
        <div style={{ color: active ? color : C.muted, marginBottom: 8 }}>
          <Icon size={18} />
        </div>
      )}
      <div style={{ fontWeight: 700, fontSize: 13, color: active ? color : C.text, marginBottom: sub ? 3 : 0 }}>
        {label}
      </div>
      {sub && <div style={{ fontSize: 10, color: C.muted, lineHeight: 1.45 }}>{sub}</div>}
      {active && (
        <div style={{ position: 'absolute', top: 10, right: 10, width: 7, height: 7, borderRadius: '50%', background: color }} />
      )}
    </button>
  );
}

// Compact track card (3 columns)
function TrackCard({ label, sub, icon: Icon, color, active, onClick }) {
  return (
    <button type="button" onClick={onClick} className="act-btn" style={{
      padding: '12px 12px', borderRadius: 10, textAlign: 'left', cursor: 'pointer', width: '100%',
      border: `1.5px solid ${active ? color : 'rgba(255,255,255,.07)'}`,
      background: active ? `${color}12` : 'rgba(255,255,255,.02)',
      position: 'relative',
    }}>
      {Icon && (
        <div style={{ color: active ? color : C.muted, marginBottom: 6 }}>
          <Icon size={15} />
        </div>
      )}
      <div style={{ fontWeight: 700, fontSize: 12, color: active ? color : C.text, marginBottom: sub ? 2 : 0 }}>
        {label}
      </div>
      {sub && <div style={{ fontSize: 10, color: C.muted, lineHeight: 1.4 }}>{sub}</div>}
      {active && (
        <div style={{ position: 'absolute', top: 8, right: 8, width: 6, height: 6, borderRadius: '50%', background: color }} />
      )}
    </button>
  );
}

// Journey flow panel
function FlowPreview({ nodes }) {
  if (!nodes.length) {
    return (
      <div style={{ fontSize: 11, color: C.muted, textAlign: 'center', padding: '12px 0', lineHeight: 1.7 }}>
        Select a role to see<br />the appraisal journey
      </div>
    );
  }
  const COLS = [C.accent, '#a78bfa', C.yellow, C.green, C.orange];
  return (
    <div>
      {nodes.map((node, i) => {
        const col    = COLS[i] ?? C.muted;
        const isLast = i === nodes.length - 1;
        return (
          <div key={i} style={{ display: 'flex', gap: 10 }}>
            {/* Timeline column */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 10, flexShrink: 0 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: col, flexShrink: 0, marginTop: 2 }} />
              {!isLast && (
                <div style={{ width: 1.5, flex: 1, background: 'rgba(255,255,255,.07)', marginTop: 4, minHeight: 16 }} />
              )}
            </div>
            {/* Content */}
            <div style={{ paddingBottom: isLast ? 0 : 14, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 11, color: col }}>{node.label}</div>
              <div style={{ fontSize: 10, color: C.muted, marginTop: 1 }}>{node.sub}</div>
              {node.sees && (
                <div style={{ marginTop: 3, fontSize: 9, fontWeight: 600, color: C.green }}>
                  ✓ {node.sees}
                </div>
              )}
              {node.hides && (
                <div style={{ marginTop: 1, fontSize: 9, fontWeight: 600, color: C.red }}>
                  ✕ {node.hides}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Section heading
function SL({ children }) {
  return (
    <div style={{
      fontSize: 10, fontWeight: 700, letterSpacing: .8, textTransform: 'uppercase',
      color: C.muted, marginBottom: 12, paddingBottom: 8,
      borderBottom: '1px solid rgba(255,255,255,.05)',
    }}>
      {children}
    </div>
  );
}

// Labelled field
function Field({ label, req, children }) {
  return (
    <div>
      <label style={lbl}>{label}{req && ' *'}</label>
      {children}
    </div>
  );
}

// Info banner
function InfoBox({ color, children }) {
  const rgb = color === 'green' ? '52,211,153' : color === 'purple' ? '167,139,250' : '251,191,36';
  return (
    <div style={{
      marginBottom: 16, padding: '10px 14px', borderRadius: 8, fontSize: 11, lineHeight: 1.55,
      color: color === 'green' ? C.green : color === 'purple' ? '#a78bfa' : C.yellow,
      background: `rgba(${rgb},.06)`,
      border: `1px solid rgba(${rgb},.18)`,
    }}>
      {children}
    </div>
  );
}

// Reporting structure toggle (non-teaching staff only)
// ── CSV import helpers ─────────────────────────────────────────────────────────

const TEMPLATE_HEADERS = [
  'full_name', 'email', 'password', 'appraisal_role',
  'school', 'department', 'designation', 'phone', 'qualification', 'teaching_experience',
];

// school is optional for all; department is optional except when school === 'SoEMR'
const REQUIRED_FIELDS = ['email', 'password', 'full_name', 'appraisal_role'];

const VALID_ROLES = [
  'faculty','hod','director','dean','vc','registrar',
  'non_teaching_staff','reporting_officer','center_head','section_head','staff',
  'admin','hr',
];

function parseCSV(text) {
  const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim().split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0].split(',').map(h => h.trim().toLowerCase().replace(/\s+/g, '_'));
  return lines.slice(1).filter(l => l.trim()).map(line => {
    // handle quoted fields
    const cols = [];
    let cur = '', inQ = false;
    for (const ch of line + ',') {
      if (ch === '"') { inQ = !inQ; }
      else if (ch === ',' && !inQ) { cols.push(cur.trim()); cur = ''; }
      else cur += ch;
    }
    const row = {};
    headers.forEach((h, i) => { row[h] = cols[i] ?? ''; });
    return row;
  });
}

function downloadTemplate() {
  // One teaching example (SoCSEA — department optional for non-SoEMR)
  // One non-teaching example (school + department both optional)
  const sample = [
    'Dr. Priya Sharma,priya.sharma@dypatil.edu,Pass@123,faculty,SoCSEA,,Assistant Professor,9876543201,Ph.D Computer Science,8 Years',
    'Mr. Ravi Shinde,ravi.shinde@dypatil.edu,Pass@123,non_teaching_staff,,,Lab Assistant,9876543202,B.Sc,',
  ];
  const csv = [TEMPLATE_HEADERS.join(','), ...sample].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'faculty_import_template.csv'; a.click();
  URL.revokeObjectURL(url);
}

// ── Import Modal ──────────────────────────────────────────────────────────────

const IMPORT_STEPS = ['Upload', 'Preview', 'Importing', 'Done'];
const PHASE_INDEX  = { upload: 0, preview: 1, importing: 2, done: 3 };

function ImportModal({ onClose }) {
  const [phase,    setPhase]    = useState('upload');
  const [rows,     setRows]     = useState([]);
  const [fileName, setFileName] = useState('');
  const [parseErr, setParseErr] = useState(null);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [results,  setResults]  = useState([]);
  const [dragging, setDragging] = useState(false);

  const handleFile = (file) => {
    if (!file) return;
    if (!file.name.endsWith('.csv')) { setParseErr('Only .csv files are supported.'); return; }
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const parsed = parseCSV(e.target.result);
        if (!parsed.length) { setParseErr('No data rows found — check the file has at least one row below the header.'); return; }
        setRows(parsed);
        setFileName(file.name);
        setParseErr(null);
        setPhase('preview');
      } catch {
        setParseErr('Could not parse the file. Make sure it is a valid CSV.');
      }
    };
    reader.readAsText(file);
  };

  const handleDrop = (e) => {
    e.preventDefault(); setDragging(false);
    handleFile(e.dataTransfer.files[0]);
  };

  const rowIsValid = r =>
    REQUIRED_FIELDS.every(f => r[f]?.trim()) &&
    (r.school?.trim() !== 'SoEMR' || r.department?.trim()); // SoEMR requires department
  const validRows   = rows.filter(rowIsValid);
  const skippedRows = rows.filter(r => !rowIsValid(r));

  const handleImport = async () => {
    setPhase('importing');
    setProgress({ done: 0, total: validRows.length });
    const res = [];
    for (const row of validRows) {
      const payload = {
        full_name:           row.full_name,
        email:               row.email,
        password:            row.password,
        appraisal_role:      row.appraisal_role,
        school:              row.school,
        department:          row.department,
        designation:         row.designation         || undefined,
        phone:               row.phone               || undefined,
        qualification:       row.qualification       || undefined,
        teaching_experience: row.teaching_experience || undefined,
      };
      try {
        await api.users.create(payload);
        res.push({ email: row.email, name: row.full_name, ok: true });
        logAction('user_created', 'User Created (Import)', `${row.full_name || row.email} (${row.appraisal_role})`, { name: row.full_name, email: row.email, role: row.appraisal_role });
      } catch (e) {
        res.push({ email: row.email, name: row.full_name, ok: false, err: e.message });
      }
      setProgress(p => ({ ...p, done: p.done + 1 }));
    }
    setResults(res);
    setPhase('done');
  };

  const successCount = results.filter(r => r.ok).length;
  const failCount    = results.filter(r => !r.ok).length;
  const pct          = progress.total ? Math.round(progress.done / progress.total * 100) : 0;

  /* ── Shared styles ── */
  const cancelBtn = {
    padding: '9px 18px', background: 'transparent', color: C.muted,
    border: '1px solid var(--c-btn-border)', borderRadius: 8,
    cursor: 'pointer', fontSize: 13, fontWeight: 600,
  };

  return createPortal(
    <>
      {/* Backdrop */}
      <div onClick={phase === 'importing' ? undefined : onClose} style={{
        position: 'fixed', inset: 0, zIndex: 900,
        background: 'rgba(0,0,0,.6)', backdropFilter: 'blur(6px)',
      }} />

      {/* Centering wrapper — owns transform:translate so animation can't override it */}
      <div style={{
        position: 'fixed', top: '50%', left: '50%', zIndex: 901,
        transform: 'translate(-50%, -50%)',
        width: 680, maxWidth: 'calc(100vw - 32px)',
      }}>

      {/* Modal shell — owns animation (scaleIn uses transform:scale, separate element) */}
      <div style={{
        maxHeight: 'calc(100vh - 48px)',
        background: 'var(--c-surf)', borderRadius: 16,
        border: '1px solid var(--c-border)',
        boxShadow: '0 32px 80px rgba(0,0,0,.6)',
        display: 'flex', flexDirection: 'column',
        animation: 'scaleIn .22s cubic-bezier(.22,1,.36,1) both',
      }}>

        {/* ── Header ── */}
        <div style={{
          padding: '20px 24px 0', flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 40, height: 40, borderRadius: 10, flexShrink: 0,
                background: `${C.accent}18`, border: `1px solid ${C.accent}30`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <I.dl size={18} style={{ color: C.accent }} />
              </div>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: C.text, lineHeight: 1.2 }}>
                  Import Faculty List
                </div>
                <div style={{ fontSize: 11, color: C.muted, marginTop: 3 }}>
                  Bulk-create accounts from a CSV file
                </div>
              </div>
            </div>
            {phase !== 'importing' && (
              <button className="act-btn" onClick={onClose} style={{
                width: 32, height: 32, borderRadius: 8, border: '1px solid var(--c-border)',
                background: 'var(--c-soft-bg)', cursor: 'pointer', color: C.muted,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 17, lineHeight: 1, flexShrink: 0,
              }}>×</button>
            )}
          </div>

          {/* Step indicator */}
          <div style={{
            display: 'flex', alignItems: 'center',
            borderBottom: '1px solid var(--c-divider)', paddingBottom: 0,
          }}>
            {IMPORT_STEPS.map((label, i) => {
              const cur  = PHASE_INDEX[phase];
              const done = i < cur;
              const active = i === cur;
              return (
                <div key={label} style={{ display: 'flex', alignItems: 'center', flex: i < IMPORT_STEPS.length - 1 ? 1 : 'none' }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 7, paddingBottom: 12,
                    borderBottom: `2px solid ${active ? C.accent : done ? C.green : 'transparent'}`,
                    marginBottom: -1,
                  }}>
                    <div style={{
                      width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 10, fontWeight: 800,
                      background: done ? C.green : active ? C.accent : 'var(--c-soft-bg)',
                      color: (done || active) ? '#fff' : C.muted,
                      border: `1.5px solid ${done ? C.green : active ? C.accent : 'var(--c-border)'}`,
                    }}>
                      {done ? '✓' : i + 1}
                    </div>
                    <span style={{
                      fontSize: 11, fontWeight: active ? 700 : 500,
                      color: active ? C.text : done ? C.green : C.muted,
                      whiteSpace: 'nowrap',
                    }}>{label}</span>
                  </div>
                  {i < IMPORT_STEPS.length - 1 && (
                    <div style={{
                      flex: 1, height: 1, margin: '0 10px', marginBottom: 12,
                      background: done ? `${C.green}40` : 'var(--c-divider)',
                    }} />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Body ── */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '22px 24px' }}>

          {/* ══ UPLOAD ══ */}
          {phase === 'upload' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

              {/* Drop zone */}
              <div
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                style={{
                  border: `2px dashed ${dragging ? C.accent : parseErr ? C.red : 'var(--c-border)'}`,
                  borderRadius: 12, padding: '32px 20px', textAlign: 'center',
                  background: dragging ? `${C.accent}08` : parseErr ? 'rgba(248,113,113,.04)' : 'var(--c-soft-bg)',
                  transition: 'all .18s',
                }}>
                {/* Upload icon */}
                <div style={{
                  width: 52, height: 52, borderRadius: '50%', margin: '0 auto 14px',
                  background: `${C.accent}12`, border: `1px solid ${C.accent}25`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <I.dl size={22} style={{ color: C.accent }} />
                </div>
                <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 5 }}>
                  {dragging ? 'Release to upload' : 'Drop your CSV file here'}
                </div>
                <div style={{ fontSize: 12, color: C.muted, marginBottom: 18 }}>
                  Supports .csv format only
                </div>
                <label style={{ cursor: 'pointer', display: 'inline-block' }}>
                  <input type="file" accept=".csv" style={{ display: 'none' }}
                    onChange={e => handleFile(e.target.files[0])} />
                  <span className="act-btn" style={{ ...pBtn, display: 'inline-flex', cursor: 'pointer' }}>
                    Browse File
                  </span>
                </label>
                {parseErr && (
                  <div style={{ marginTop: 14, fontSize: 12, color: C.red, fontWeight: 500 }}>
                    ⚠ {parseErr}
                  </div>
                )}
              </div>

              {/* CSV spec */}
              <div style={{ borderRadius: 12, border: '1px solid var(--c-border)', overflow: 'hidden' }}>
                {/* Section: Required */}
                <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--c-divider)' }}>
                  <div style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: .8, textTransform: 'uppercase',
                    color: C.accent, marginBottom: 10,
                  }}>
                    Required columns
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px' }}>
                    {REQUIRED_FIELDS.map(h => (
                      <div key={h} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                        <div style={{
                          width: 5, height: 5, borderRadius: '50%',
                          background: C.accent, flexShrink: 0,
                        }} />
                        <code style={{
                          fontSize: 11.5, fontFamily: "'JetBrains Mono',monospace",
                          color: C.text, fontWeight: 600,
                        }}>{h}</code>
                      </div>
                    ))}
                  </div>
                </div>
                {/* Section: Conditional */}
                <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--c-divider)', background: 'rgba(251,191,36,.04)' }}>
                  <div style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: .8, textTransform: 'uppercase',
                    color: C.yellow, marginBottom: 8,
                  }}>
                    Conditional
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                    <div style={{ width: 5, height: 5, borderRadius: '50%', background: C.yellow, flexShrink: 0 }} />
                    <code style={{ fontSize: 11.5, fontFamily: "'JetBrains Mono',monospace", color: C.text, fontWeight: 600 }}>department</code>
                    <span style={{ fontSize: 10, color: C.muted }}>— required when <code style={{ fontFamily: "'JetBrains Mono',monospace", color: C.yellow }}>school = SoEMR</code></span>
                  </div>
                </div>
                {/* Section: Optional */}
                <div style={{ padding: '12px 16px', background: 'var(--c-soft-bg)' }}>
                  <div style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: .8, textTransform: 'uppercase',
                    color: C.muted, marginBottom: 8,
                  }}>
                    Optional columns
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px 10px' }}>
                    {TEMPLATE_HEADERS.filter(h => !REQUIRED_FIELDS.includes(h) && h !== 'department').map(h => (
                      <code key={h} style={{
                        fontSize: 11, fontFamily: "'JetBrains Mono',monospace", color: C.muted,
                      }}>{h}</code>
                    ))}
                  </div>
                </div>
                {/* Section: Roles */}
                <div style={{ padding: '12px 16px', borderTop: '1px solid var(--c-divider)' }}>
                  <div style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: .8, textTransform: 'uppercase',
                    color: C.muted, marginBottom: 7,
                  }}>
                    Valid appraisal_role values
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                    {VALID_ROLES.map(r => (
                      <span key={r} style={{
                        padding: '2px 8px', borderRadius: 20, fontSize: 10,
                        fontFamily: "'JetBrains Mono',monospace",
                        background: 'var(--c-card)', border: '1px solid var(--c-border)',
                        color: C.subtle,
                      }}>{r}</span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Template download */}
              <button className="act-btn" onClick={downloadTemplate} style={{
                padding: '11px 16px', borderRadius: 10, fontSize: 12, fontWeight: 600,
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                border: '1px solid var(--c-btn-border)', background: 'var(--c-soft-bg)', color: C.subtle,
              }}>
                <I.dl size={13} />
                Download CSV Template with sample rows
              </button>
            </div>
          )}

          {/* ══ PREVIEW ══ */}
          {phase === 'preview' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

              {/* Stats bar */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
                {[
                  { label: 'Total Rows',   val: rows.length,         col: C.accent, bg: `${C.accent}0d` },
                  { label: 'Will Import',  val: validRows.length,    col: C.green,  bg: `${C.green}0d`  },
                  { label: 'Will Skip',    val: skippedRows.length,  col: skippedRows.length ? C.red : C.muted,
                    bg: skippedRows.length ? 'rgba(248,113,113,.07)' : 'var(--c-soft-bg)' },
                ].map(s => (
                  <div key={s.label} style={{
                    padding: '12px 14px', borderRadius: 10, textAlign: 'center',
                    background: s.bg,
                    border: `1px solid ${s.col}22`,
                  }}>
                    <div style={{
                      fontSize: 22, fontWeight: 800, color: s.col,
                      fontFamily: "'JetBrains Mono',monospace", lineHeight: 1,
                    }}>{s.val}</div>
                    <div style={{ fontSize: 10, color: C.muted, marginTop: 4, fontWeight: 600,
                      letterSpacing: .4, textTransform: 'uppercase' }}>{s.label}</div>
                  </div>
                ))}
              </div>

              {/* File info pill */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 9, padding: '9px 14px',
                borderRadius: 8, background: 'var(--c-soft-bg)', border: '1px solid var(--c-border)',
              }}>
                <div style={{ fontSize: 14 }}>📄</div>
                <span style={{
                  fontSize: 12, color: C.subtle, flex: 1,
                  fontFamily: "'JetBrains Mono',monospace", overflow: 'hidden',
                  textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>{fileName}</span>
                <button className="act-btn" onClick={() => { setRows([]); setPhase('upload'); }} style={{
                  fontSize: 11, color: C.accent, background: 'transparent', border: 'none',
                  cursor: 'pointer', fontWeight: 600, flexShrink: 0, padding: '2px 0',
                }}>
                  Change file
                </button>
              </div>

              {/* Preview table */}
              <div style={{ borderRadius: 10, border: '1px solid var(--c-border)', overflow: 'hidden' }}>
                <div style={{
                  overflowX: 'auto', maxHeight: 260, overflowY: 'auto',
                }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                    <thead style={{ position: 'sticky', top: 0, zIndex: 2 }}>
                      <tr style={{ background: 'var(--c-soft-bg)' }}>
                        {['#', 'Full Name', 'Email', 'Role', 'School', 'Department', 'Status'].map(h => (
                          <th key={h} style={{
                            padding: '9px 10px', textAlign: 'left', fontWeight: 700,
                            color: C.muted, borderBottom: '1px solid var(--c-border)',
                            whiteSpace: 'nowrap', fontSize: 10, letterSpacing: .4,
                            textTransform: 'uppercase',
                          }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r, i) => {
                        const isOk = rowIsValid(r);
                        // highlight only fields whose absence actually invalidates the row
                        const miss = f => {
                          if (!r[f]?.trim()) {
                            if (f === 'department') return r.school?.trim() === 'SoEMR';
                            return REQUIRED_FIELDS.includes(f);
                          }
                          return false;
                        };
                        return (
                          <tr key={i} className="tr-row" style={{
                            borderBottom: '1px solid var(--c-row-border)',
                            background: isOk ? 'transparent' : 'rgba(248,113,113,.035)',
                          }}>
                            <td style={{ padding: '8px 10px', color: C.muted, fontSize: 10 }}>{i + 1}</td>
                            <td style={{ padding: '8px 10px', fontWeight: 600,
                              color: miss('full_name') ? C.red : C.text, maxWidth: 120,
                              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {r.full_name || <span style={{ fontWeight: 400 }}>missing</span>}
                            </td>
                            <td style={{ padding: '8px 10px', color: miss('email') ? C.red : C.accent,
                              fontFamily: "'JetBrains Mono',monospace", fontSize: 10,
                              maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {r.email || 'missing'}
                            </td>
                            <td style={{ padding: '8px 10px' }}>
                              <span style={{
                                padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 600,
                                background: r.appraisal_role ? `${C.accent}12` : 'rgba(248,113,113,.12)',
                                color: r.appraisal_role ? C.accent : C.red,
                                whiteSpace: 'nowrap',
                              }}>
                                {r.appraisal_role || 'missing'}
                              </span>
                            </td>
                            <td style={{ padding: '8px 10px', fontSize: 10,
                              fontFamily: "'JetBrains Mono',monospace",
                              color: miss('school') ? C.red : C.subtle }}>
                              {r.school || 'missing'}
                            </td>
                            <td style={{ padding: '8px 10px', fontSize: 10,
                              color: miss('department') ? C.red : C.muted }}>
                              {r.department || 'missing'}
                            </td>
                            <td style={{ padding: '8px 10px' }}>
                              {isOk
                                ? <span style={{ fontSize: 10, color: C.green, fontWeight: 600 }}>✓ ready</span>
                                : <span style={{ fontSize: 10, color: C.red,  fontWeight: 600 }}>⚠ skip</span>
                              }
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {skippedRows.length > 0 && (
                <div style={{
                  padding: '10px 14px', borderRadius: 8, fontSize: 11, lineHeight: 1.6,
                  color: '#fb923c', background: 'rgba(251,146,60,.08)',
                  border: '1px solid rgba(251,146,60,.2)',
                }}>
                  <strong>{skippedRows.length} row{skippedRows.length > 1 ? 's' : ''}</strong> will be skipped because they are missing one or more required fields.
                  Fix the CSV and re-upload, or proceed to import only the {validRows.length} valid rows.
                </div>
              )}
            </div>
          )}

          {/* ══ IMPORTING ══ */}
          {phase === 'importing' && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '24px 0 16px' }}>
              {/* Animated ring */}
              <div style={{
                width: 80, height: 80, borderRadius: '50%', marginBottom: 22,
                background: `conic-gradient(${C.accent} ${pct * 3.6}deg, var(--c-track) 0deg)`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                position: 'relative',
              }}>
                <div style={{
                  width: 60, height: 60, borderRadius: '50%',
                  background: 'var(--c-surf)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 14, fontWeight: 800, color: C.accent,
                  fontFamily: "'JetBrains Mono',monospace",
                }}>
                  {pct}%
                </div>
              </div>

              <div style={{ fontSize: 16, fontWeight: 700, color: C.text, marginBottom: 6 }}>
                Importing accounts…
              </div>
              <div style={{ fontSize: 12, color: C.muted, marginBottom: 24 }}>
                {progress.done} of {progress.total} records processed
              </div>

              {/* Progress bar */}
              <div style={{ width: '100%', maxWidth: 360, height: 6, borderRadius: 6,
                background: 'var(--c-track)', overflow: 'hidden' }}>
                <div className="progress-fill" style={{
                  height: '100%', borderRadius: 6,
                  background: `linear-gradient(90deg, ${C.accent}, #818cf8)`,
                  width: `${pct}%`,
                }} />
              </div>

              <div style={{ marginTop: 20, fontSize: 11, color: C.muted }}>
                Please wait — do not close this window
              </div>
            </div>
          )}

          {/* ══ DONE ══ */}
          {phase === 'done' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

              {/* Banner */}
              <div style={{
                padding: '18px 20px', borderRadius: 12, textAlign: 'center',
                background: failCount === 0 ? `${C.green}0d` : 'rgba(251,146,60,.07)',
                border: `1px solid ${failCount === 0 ? `${C.green}25` : 'rgba(251,146,60,.2)'}`,
              }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>
                  {failCount === 0 ? '🎉' : '⚠️'}
                </div>
                <div style={{ fontSize: 15, fontWeight: 700, color: C.text, marginBottom: 4 }}>
                  {failCount === 0
                    ? `All ${successCount} accounts created successfully`
                    : `${successCount} created, ${failCount} failed`}
                </div>
                <div style={{ fontSize: 11, color: C.muted }}>
                  {failCount === 0
                    ? 'Faculty members can now log in with the credentials from the CSV.'
                    : 'Failed rows are listed below. Fix the errors and re-import those rows.'}
                </div>
              </div>

              {/* Summary pills */}
              <div style={{ display: 'grid', gridTemplateColumns: failCount > 0 ? '1fr 1fr' : '1fr', gap: 10 }}>
                <div style={{ padding: '14px 16px', borderRadius: 10, textAlign: 'center',
                  background: `${C.green}0d`, border: `1px solid ${C.green}22` }}>
                  <div style={{ fontSize: 28, fontWeight: 800, color: C.green,
                    fontFamily: "'JetBrains Mono',monospace" }}>{successCount}</div>
                  <div style={{ fontSize: 10, color: C.muted, marginTop: 4, fontWeight: 600,
                    letterSpacing: .5, textTransform: 'uppercase' }}>Accounts Created</div>
                </div>
                {failCount > 0 && (
                  <div style={{ padding: '14px 16px', borderRadius: 10, textAlign: 'center',
                    background: 'rgba(248,113,113,.07)', border: '1px solid rgba(248,113,113,.2)' }}>
                    <div style={{ fontSize: 28, fontWeight: 800, color: C.red,
                      fontFamily: "'JetBrains Mono',monospace" }}>{failCount}</div>
                    <div style={{ fontSize: 10, color: C.muted, marginTop: 4, fontWeight: 600,
                      letterSpacing: .5, textTransform: 'uppercase' }}>Failed</div>
                  </div>
                )}
              </div>

              {/* Per-row results */}
              <div style={{ borderRadius: 10, border: '1px solid var(--c-border)', overflow: 'hidden' }}>
                <div style={{
                  padding: '9px 14px', borderBottom: '1px solid var(--c-divider)',
                  background: 'var(--c-soft-bg)', fontSize: 10, fontWeight: 700,
                  color: C.muted, letterSpacing: .5, textTransform: 'uppercase',
                }}>
                  Import Log
                </div>
                <div style={{ maxHeight: 220, overflowY: 'auto' }}>
                  {results.map((r, i) => (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'center', gap: 10, padding: '9px 14px',
                      borderBottom: i < results.length - 1 ? '1px solid var(--c-row-border)' : 'none',
                      background: r.ok ? 'transparent' : 'rgba(248,113,113,.04)',
                    }}>
                      <div style={{
                        width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
                        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10,
                        background: r.ok ? `${C.green}15` : 'rgba(248,113,113,.15)',
                        color: r.ok ? C.green : C.red,
                        fontWeight: 800,
                      }}>
                        {r.ok ? '✓' : '✕'}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: C.text,
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {r.name || r.email}
                        </div>
                        <div style={{ fontSize: 10, color: C.muted, fontFamily: "'JetBrains Mono',monospace",
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {r.email}
                        </div>
                      </div>
                      {!r.ok && (
                        <div style={{ fontSize: 10, color: C.red, maxWidth: 180, textAlign: 'right',
                          lineHeight: 1.4, flexShrink: 0 }}>{r.err}</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── Footer ── */}
        <div style={{
          padding: '14px 24px', borderTop: '1px solid var(--c-divider)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          flexShrink: 0, background: 'var(--c-soft-bg)', borderRadius: '0 0 16px 16px',
        }}>
          {/* Left hint */}
          <div style={{ fontSize: 11, color: C.muted }}>
            {phase === 'upload'   && 'Upload a .csv file to continue'}
            {phase === 'preview'  && `${validRows.length} of ${rows.length} rows will be imported`}
            {phase === 'importing'&& `Processing… ${progress.done} / ${progress.total}`}
            {phase === 'done'     && `Import complete · ${new Date().toLocaleTimeString()}`}
          </div>

          {/* Right actions */}
          <div style={{ display: 'flex', gap: 8 }}>
            {phase === 'upload' && (
              <button className="act-btn" onClick={onClose} style={cancelBtn}>Cancel</button>
            )}
            {phase === 'preview' && (
              <>
                <button className="act-btn" onClick={onClose} style={cancelBtn}>Cancel</button>
                <button className="act-btn" style={pBtn}
                  onClick={handleImport} disabled={validRows.length === 0}>
                  Import {validRows.length} Record{validRows.length !== 1 ? 's' : ''} →
                </button>
              </>
            )}
            {phase === 'done' && (
              <button className="act-btn" style={pBtn} onClick={onClose}>
                Done
              </button>
            )}
          </div>
        </div>
      </div>
      </div>
    </>,
    document.body
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function AddFacultyPage() {
  const navigate = useNavigate();

  const [step,        setStep]        = useState(0);
  const [staffType,   setStaffType]   = useState('');   // 'teaching' | 'non_teaching'
  const [track,       setTrack]       = useState('');   // 'engineering' | 'non_engineering' | 'cisr'
  const [form,        setForm]        = useState(EMPTY);
  const [saving,      setSaving]      = useState(false);
  const [err,         setErr]         = useState(null);
  const [success,     setSuccess]     = useState(null);
  const [receipt,     setReceipt]     = useState(null);
  const [importModal, setImportModal] = useState(false);
  const [ntDirectVC,          setNtDirectVC]          = useState(false);
  const [ntHasFirstReviewer,  setNtHasFirstReviewer]  = useState(false);
  const [ntFirstReviewerType, setNtFirstReviewerType] = useState('ro'); // 'ro' | 'depthead'
  const [ntRegRequired,       setNtRegRequired]       = useState(true);
  const [templates,        setTemplates]        = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [ros,              setRos]              = useState([]);
  const [registrarsList,   setRegistrarsList]   = useState([]);

  useEffect(() => {
    if (staffType !== 'non_teaching') return;
    setTemplatesLoading(true);
    Promise.all([
      api.workflowTemplates.list(),
      api.users.reportingOfficers(),
      api.users.registrars(),
    ])
      .then(([tmpl, roData, regData]) => {
        setTemplates(Array.isArray(tmpl)    ? tmpl    : []);
        setRos(      Array.isArray(roData)  ? roData  : []);
        setRegistrarsList(Array.isArray(regData) ? regData : []);
      })
      .catch(() => {})
      .finally(() => setTemplatesLoading(false));
  }, [staffType]);

  // Sync workflow_template_id whenever NT toggles or templates change
  useEffect(() => {
    if (!isNonTeaching || role !== 'non_teaching_staff' || !templates.length) return;
    const tpl = resolveTemplateForToggles(templates, ntDirectVC, ntHasFirstReviewer, ntFirstReviewerType, ntRegRequired);
    setForm(p => ({ ...p, workflow_template_id: tpl?.id ?? '' }));
  }, [ntDirectVC, ntHasFirstReviewer, ntFirstReviewerType, ntRegRequired, templates]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = k => e => setForm(p => ({ ...p, [k]: e.target.value }));

  // Derived flags
  const isTeaching    = staffType === 'teaching';
  const isNonTeaching = staffType === 'non_teaching';
  const isEngineering = track === 'engineering';
  const isNonEng      = track === 'non_engineering';
  const isCISR        = track === 'cisr';
  const role          = form.appraisal_role;
  const school        = form.school;
  const dept          = form.department;

  const availRoles = isCISR       ? CISR_ROLES
    : isNonTeaching               ? NT_ROLES
    : isEngineering               ? ENGG_ROLES
    : isNonEng                    ? NON_ENGG_ROLES
    : (staffType === 'system'
        ? [
            { value: 'vc',    label: 'Vice Chancellor', color: C.accent,  icon: I.users,  flow: 'All schools final approval' },
            { value: 'admin', label: 'Admin',           color: '#a78bfa', icon: I.shield, flow: 'Full system configuration' },
            { value: 'hr',    label: 'HR / Personnel',  color: C.yellow,  icon: I.list,   flow: 'Export & track all data' },
          ]
        : []);

  // Role grid: 3-col for exactly 3 items, 2-col for 2 or 4
  const roleGridCols = availRoles.length === 3 ? 'repeat(3, 1fr)' : 'repeat(2, 1fr)';

  const groupSchools    = isEngineering ? ENGG_SCHOOLS : NON_ENGG_SCHOOLS;
  const showSchoolPicker = (isEngineering || isNonEng) && !!role && role !== 'dean' && role !== 'hod';
  const schoolLocked     = role === 'hod'; // auto-locked to SoEMR
  const showDeptFixed    = (role === 'faculty' || role === 'hod') && school === 'SoEMR';
  const showDeptText     = role === 'faculty' && !!school && school !== 'SoEMR' && (isEngineering || isNonEng);

  const flowNodes = computeFlow(staffType, track, role, school, dept);

  // Dynamic NT workflow — fetched from API, falls back gracefully if unavailable
  const { steps: ntWorkflowSteps, loading: ntWorkflowLoading } = useWorkflowTemplate(
    isNonTeaching ? role : null,
  );

  const selectedTemplate = templates.find(t => String(t.id) === String(form.workflow_template_id));

  // No templates configured in the DB at all
  const noTemplatesAtAll = isNonTeaching
    && role === 'non_teaching_staff'
    && !templatesLoading
    && templates.length === 0;

  // Templates exist but none match the selected toggle combination
  const noTemplateMatch = isNonTeaching
    && role === 'non_teaching_staff'
    && !templatesLoading
    && templates.length > 0
    && !form.workflow_template_id;

  // For NT staff: always derive preview from toggle states so the right panel
  // reflects exactly what the admin has configured, regardless of whether a
  // matching template exists in the DB.
  // For other NT roles (RO, Registrar): use the API-resolved template steps.
  const displayNtSteps = (isNonTeaching && role === 'non_teaching_staff')
    ? buildChainNodes(ntDirectVC, ntHasFirstReviewer, ntFirstReviewerType, ntRegRequired)
        .filter(n => n !== 'Staff')
        .map((designation, i) => ({ stepNo: i + 1, designation, status: 'WAITING' }))
    : (selectedTemplate?.steps
        ? selectedTemplate.steps.map(s => ({ stepNo: s.step_no, designation: s.designation, status: 'WAITING' }))
        : ntWorkflowSteps);

  // ── Print receipt ────────────────────────────────────────────────────────────

  const handlePrint = (r) => {
    const rows = [
      ['Full Name',    r.name],
      ['Email',        r.email],
      ['Role',         r.role],
      ['Staff Type',   r.staffType],
      r.school             && ['School',      r.school],
      r.department         && ['Department',  r.department],
      r.designation        && ['Designation', r.designation],
      r.phone              && ['Phone',       r.phone],
      r.qualification      && ['Qualification', r.qualification],
      r.teachingExperience && ['Experience',  r.teachingExperience],
    ].filter(Boolean);

    const w = window.open('', '_blank', 'width=640,height=860');
    w.document.write(`<!DOCTYPE html><html><head>
      <title>Account Receipt — ${r.name}</title>
      <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:48px 40px;color:#111;background:#fff}
        .hdr{display:flex;align-items:center;gap:14px;margin-bottom:28px;padding-bottom:20px;border-bottom:2px solid #e5e7eb}
        .logo{width:44px;height:44px;background:#f0fdf4;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0}
        h1{font-size:17px;font-weight:700}
        .sub{font-size:12px;color:#6b7280;margin-top:3px}
        .badge{display:inline-block;padding:3px 10px;border-radius:20px;background:#f0fdf4;color:#15803d;font-size:11px;font-weight:700;border:1px solid #bbf7d0}
        table{width:100%;border-collapse:collapse;margin-bottom:20px}
        tr{border-bottom:1px solid #f3f4f6}
        td{padding:10px 4px;font-size:13px;vertical-align:top}
        td:first-child{color:#6b7280;width:150px;font-weight:500}
        td:last-child{font-weight:600;color:#111}
        .warn{padding:12px 14px;background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;font-size:12px;color:#92400e;line-height:1.6}
        .footer{margin-top:28px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;text-align:center}
        @media print{@page{margin:20mm}}
      </style>
    </head><body>
      <div class="hdr">
        <div class="logo">🎓</div>
        <div><h1>DYP Faculty Appraisal System</h1><div class="sub">New Account Receipt &middot; ${r.createdAt}</div></div>
        <div style="margin-left:auto"><span class="badge">✓ Active</span></div>
      </div>
      <table>${rows.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join('')}</table>
      <div class="warn">⚠&nbsp; Password is <strong>not included</strong> in this receipt. Communicate login credentials to the user separately through a secure channel.</div>
      <div class="footer">Generated by DYP Faculty Appraisal Admin Panel &middot; ${r.createdAt}</div>
    </body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 400);
  };

  // ── Handlers ────────────────────────────────────────────────────────────────

  const handleStaffType = (type) => {
    setStaffType(type);
    setTrack('');
    setErr(null);
    setNtDirectVC(false);
    setNtHasFirstReviewer(false);
    setNtFirstReviewerType('ro');
    setNtRegRequired(true);
    setForm(p => ({ ...p, appraisal_role: '', school: '', department: '', workflow_template_id: '', reporting_officer_email: '', registrar_email: '' }));
  };
  const handleTrack = (t) => {
    setTrack(t);
    setErr(null);
    // CISR has only one school — auto-assign it immediately
    setForm(p => ({ ...p, appraisal_role: '', school: t === 'cisr' ? 'CISR' : '', department: '' }));
  };
  const handleSchool = (code) => {
    setForm(p => ({
      ...p,
      school: code,
      department: '',
      // If switching away from SoEMR and role was HOD, revert to faculty
      appraisal_role: p.appraisal_role === 'hod' && code !== 'SoEMR' ? 'faculty' : p.appraisal_role,
    }));
  };
  const handleRole = (val) => {
    const update = { appraisal_role: val, department: '', workflow_template_id: '', reporting_officer_email: '', registrar_email: '' };
    if (val === 'hod')  update.school = 'SoEMR';
    if (val === 'dean') update.school = track;
    setForm(p => ({ ...p, ...update }));
    // Reset NT toggles when role changes
    if (isNonTeaching) {
      setNtDirectVC(false);
      setNtHasFirstReviewer(false);
      setNtFirstReviewerType('ro');
      setNtRegRequired(true);
    }
  };

  // ── Validation ───────────────────────────────────────────────────────────────

  const validate = () => {
    if (step === 0) {
      if (!staffType) return 'Please select Teaching or Non-Teaching.';
      if (isTeaching && !track) return 'Please select an academic track.';
      if (isNonTeaching && !role) return 'Please select a Non-Teaching role.';
    }
    if (step === 1) {
      if (!role) return 'Please select a role.';
      if ((isEngineering || isNonEng) && role !== 'dean' && role !== 'hod' && !school)
        return 'Please select a school.';
      if (role === 'hod' && !dept)
        return 'Please select a department for this HOD position.';
      if (role === 'faculty' && school === 'SoEMR' && !dept)
        return 'SoEMR faculty must be assigned to a department.';
      if (isNonTeaching && role === 'non_teaching_staff') {
        if (!ntDirectVC) {
          if (ntHasFirstReviewer && !form.reporting_officer_email)
            return ntFirstReviewerType === 'ro'
              ? 'Please assign a Reporting Officer for this staff member.'
              : 'Please assign a Department Head for this staff member.';
          if ((!ntHasFirstReviewer || ntRegRequired) && !form.registrar_email)
            return 'Please assign a Registrar for this staff member.';
        }
      }
    }
    if (step === 2) {
      if (!form.full_name.trim()) return 'Full name is required.';
      if (!form.email.trim())     return 'Email address is required.';
      if (!form.password.trim())  return 'Password is required.';
    }
    return null;
  };

  const handleNext = async () => {
    const msg = validate();
    if (msg) { setErr(msg); return; }
    setErr(null);
    if (step < 3) { setStep(s => s + 1); return; }

    // Final step — save
    setSaving(true); setSuccess(null);
    try {
      // Build clean payload — strip empty strings to null, set reports_to_registrar
      const isNtStaff = isNonTeaching && role === 'non_teaching_staff';
      const createPayload = isNtStaff
        ? {
            ...form,
            reports_to_registrar: !ntDirectVC && !ntHasFirstReviewer,
            reporting_officer_email: (!ntDirectVC && ntHasFirstReviewer)
              ? (form.reporting_officer_email || null)
              : null,
            registrar_email: (!ntDirectVC && (!ntHasFirstReviewer || ntRegRequired))
              ? (form.registrar_email || null)
              : null,
          }
        : {
            ...form,
            reporting_officer_email: form.reporting_officer_email || null,
            registrar_email:         form.registrar_email         || null,
          };
      await api.users.create(createPayload);
      logAction('user_created', 'User Created', `${form.full_name || form.email} (${form.appraisal_role})`, { name: form.full_name, email: form.email, role: form.appraisal_role });
      if (staffType === 'non_teaching' && form.workflow_template_id) {
        await api.workflowTemplates.assign({
          template_id: form.workflow_template_id,
          staff_email: form.email,
        });
      }
      const snap = {
        name:               form.full_name || form.email,
        email:              form.email,
        role:               roleMeta?.label ?? role,
        staffType:          staffType === 'teaching' ? 'Teaching' : (staffType === 'system' ? 'System Role' : 'Non-Teaching'),
        school:             school             || null,
        department:         dept               || null,
        designation:        form.designation   || null,
        phone:              form.phone         || null,
        qualification:      form.qualification || null,
        teachingExperience: form.teaching_experience || null,
        template:           (isNonTeaching && role === 'non_teaching_staff')
                              ? buildChainLabel(ntDirectVC, ntHasFirstReviewer, ntFirstReviewerType, ntRegRequired)
                              : (selectedTemplate?.name || null),
        reportingOfficer:   form.reporting_officer_email ? (ros.find(r => r.email === form.reporting_officer_email)?.full_name || form.reporting_officer_email) : null,
        registrar:          form.registrar_email ? (registrarsList.find(r => r.email === form.registrar_email)?.full_name || form.registrar_email) : null,
        createdAt: new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }),
      };
      setReceipt(snap);
      setSuccess(form.email);
      setForm(EMPTY);
      setStaffType('');
      setTrack('');
      setStep(0);
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  // ── Step renderers ───────────────────────────────────────────────────────────

  const g2 = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 };

  const stepClassify = () => {
    const profile = api.getProfile();
    const isSuperAdmin = profile?.appraisal_role === 'super_admin';
    const gridCols = isSuperAdmin ? 'repeat(3, 1fr)' : 'repeat(2, 1fr)';

    return (
      <div>
        <SL>Staff Category</SL>
        <div style={{ display: 'grid', gridTemplateColumns: gridCols, gap: 12, marginBottom: 22 }}>
          <ChoiceCard
            label="Teaching Staff"
            sub="Faculty · HOD · Director · Dean"
            icon={I.users} color={C.accent}
            active={staffType === 'teaching'}
            onClick={() => handleStaffType('teaching')}
          />
          <ChoiceCard
            label="Non-Teaching Staff"
            sub="Staff · Reporting Officer · Registrar"
            icon={I.doc} color="#a78bfa"
            active={staffType === 'non_teaching'}
            onClick={() => handleStaffType('non_teaching')}
          />
          {isSuperAdmin && (
            <ChoiceCard
              label="System Roles"
              sub="VC · Admins · HR / Personnel"
              icon={I.shield} color={C.green}
              active={staffType === 'system'}
              onClick={() => handleStaffType('system')}
            />
          )}
        </div>

        {isTeaching && (
          <div style={{ animation: 'fadeUp .2s cubic-bezier(.22,1,.36,1) both' }}>
            <SL>Academic Track</SL>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
              <TrackCard
                label="Engineering"
                sub="SoCSEA · SoBB · SoCE · SoEMR"
                icon={I.bldg} color={C.yellow}
                active={track === 'engineering'}
                onClick={() => handleTrack('engineering')}
              />
              <TrackCard
                label="Non-Engineering"
                sub="SoCM · SoMCS · SoHSS · SoD · SoAA"
                icon={I.school} color={C.green}
                active={track === 'non_engineering'}
                onClick={() => handleTrack('non_engineering')}
              />
              <TrackCard
                label="CISR"
                sub="Center for Interdisciplinary Studies & Research"
                icon={I.layers} color={C.orange}
                active={track === 'cisr'}
                onClick={() => handleTrack('cisr')}
              />
            </div>
          </div>
        )}

        {isNonTeaching && (
          <div style={{ animation: 'fadeUp .2s cubic-bezier(.22,1,.36,1) both' }}>
            <SL>Select Role</SL>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
              {NT_ROLES.map(r => {
                const RIcon  = r.icon;
                const active = role === r.value;
                return (
                  <button
                    key={r.value}
                    type="button"
                    onClick={() => handleRole(r.value)}
                    className="act-btn"
                    style={{
                      padding: '16px 14px', borderRadius: 12, textAlign: 'left',
                      cursor: 'pointer', position: 'relative',
                      border: `1.5px solid ${active ? r.color : 'rgba(255,255,255,.07)'}`,
                      background: active ? `${r.color}12` : 'rgba(255,255,255,.02)',
                      transition: 'border-color .15s, background .15s',
                    }}
                  >
                    <div style={{
                      width: 36, height: 36, borderRadius: 9, marginBottom: 10, flexShrink: 0,
                      background: active ? `${r.color}20` : 'rgba(255,255,255,.04)',
                      border: `1px solid ${active ? `${r.color}35` : 'rgba(255,255,255,.07)'}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: active ? r.color : C.muted,
                    }}>
                      <RIcon size={16} />
                    </div>
                    <div style={{ fontWeight: 700, fontSize: 13, color: active ? r.color : C.text, marginBottom: 5 }}>
                      {r.label}
                    </div>
                    <div style={{ fontSize: 10, color: C.muted, lineHeight: 1.5 }}>
                      {r.desc}
                    </div>
                    {active && (
                      <div style={{ position: 'absolute', top: 10, right: 10, width: 7, height: 7, borderRadius: '50%', background: r.color }} />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {staffType === 'system' && (
          <div style={{ animation: 'fadeUp .2s cubic-bezier(.22,1,.36,1) both' }}>
            <SL>Select Role</SL>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
              {availRoles.map(r => {
                const RIcon  = r.icon;
                const active = role === r.value;
                return (
                  <button
                    key={r.value}
                    type="button"
                    onClick={() => handleRole(r.value)}
                    className="act-btn"
                    style={{
                      padding: '16px 14px', borderRadius: 12, textAlign: 'left',
                      cursor: 'pointer', position: 'relative',
                      border: `1.5px solid ${active ? r.color : 'rgba(255,255,255,.07)'}`,
                      background: active ? `${r.color}12` : 'rgba(255,255,255,.02)',
                      transition: 'border-color .15s, background .15s',
                    }}
                  >
                    <div style={{
                      width: 36, height: 36, borderRadius: 9, marginBottom: 10, flexShrink: 0,
                      background: active ? `${r.color}20` : 'rgba(255,255,255,.04)',
                      border: `1px solid ${active ? `${r.color}35` : 'rgba(255,255,255,.07)'}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: active ? r.color : C.muted,
                    }}>
                      <RIcon size={16} />
                    </div>
                    <div style={{ fontWeight: 700, fontSize: 13, color: active ? r.color : C.text, marginBottom: 5 }}>
                      {r.label}
                    </div>
                    <div style={{ fontSize: 10, color: C.muted, lineHeight: 1.5 }}>
                      {r.flow}
                    </div>
                    {active && (
                      <div style={{ position: 'absolute', top: 10, right: 10, width: 7, height: 7, borderRadius: '50%', background: r.color }} />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    );
  };

  const stepRoleSchool = () => {
    if (staffType === 'system') {
      const sysRole = availRoles.find(r => r.value === role);
      const SysIcon = sysRole?.icon;
      return (
        <div>
          <SL>System Role Profile</SL>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '13px 15px', borderRadius: 12,
            background: 'rgba(255,255,255,.02)', border: '1px solid rgba(255,255,255,.07)',
            marginBottom: 16
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 9,
              background: `${sysRole?.color || C.muted}20`, border: `1px solid ${sysRole?.color || C.muted}35`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: sysRole?.color || C.muted,
              flexShrink: 0
            }}>
              {SysIcon ? <SysIcon size={16} /> : <I.shield size={16} />}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 12, color: sysRole?.color || C.text }}>{sysRole?.label || role}</div>
              <div style={{ fontSize: 10, color: C.muted }}>{sysRole?.flow}</div>
            </div>
            <button type="button" onClick={() => { setErr(null); setStep(0); }}
              style={{ fontSize: 11, color: C.muted, background: 'transparent', border: '1px solid rgba(255,255,255,.08)', borderRadius: 7, padding: '4px 9px', cursor: 'pointer' }}>
              Change
            </button>
          </div>
          <InfoBox color="green">
            This is a system-wide administrative role. No workflow template, approval chain, school, or department configuration is required.
          </InfoBox>
        </div>
      );
    }

    // ── Non-Teaching: dynamic toggle-based workflow builder ──────────────────────
    if (isNonTeaching) {
      const ntRole = NT_ROLES.find(r => r.value === role);
      const NTIcon = ntRole?.icon;
      const isStaff = role === 'non_teaching_staff';

      const chainNodes = isStaff
        ? buildChainNodes(ntDirectVC, ntHasFirstReviewer, ntFirstReviewerType, ntRegRequired)
        : [];

      const nodeColorMap = {
        'Staff': C.accent,
        'Reporting Officer': '#fb923c',
        'Dept Head': '#fb923c',
        'Registrar': '#22d3ee',
        'VC': '#f472b6',
      };

      const ToggleRow = ({ label, sub, checked, onChange, color, children }) => (
        <div style={{
          padding: '13px 15px', borderRadius: 10,
          background: checked ? `${color}07` : 'rgba(255,255,255,.02)',
          border: `1.5px solid ${checked ? `${color}30` : 'rgba(255,255,255,.08)'}`,
          transition: 'all .2s',
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 12, color: checked ? color : C.text }}>{label}</div>
              {sub && <div style={{ fontSize: 10, color: C.muted, marginTop: 2, lineHeight: 1.5 }}>{sub}</div>}
            </div>
            <button
              type="button"
              onClick={() => onChange(!checked)}
              style={{
                flexShrink: 0, padding: '5px 14px', borderRadius: 20,
                border: `1.5px solid ${checked ? color : 'rgba(255,255,255,.12)'}`,
                background: checked ? `${color}18` : 'rgba(255,255,255,.04)',
                cursor: 'pointer', fontSize: 11, fontWeight: 800,
                color: checked ? color : C.muted,
                transition: 'all .2s',
              }}
            >
              {checked ? 'ON' : 'OFF'}
            </button>
          </div>
          {checked && children && (
            <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid rgba(255,255,255,.06)' }}>
              {children}
            </div>
          )}
        </div>
      );

      const PersonPicker = ({ label, color, value, onChange, options }) => (
        <div style={{
          borderRadius: 10, overflow: 'hidden',
          border: `1.5px solid ${value ? `${color}40` : 'rgba(255,255,255,.09)'}`,
          background: value ? `${color}07` : 'rgba(255,255,255,.02)',
          transition: 'border-color .2s, background .2s',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 9,
            padding: '9px 13px', borderBottom: '1px solid rgba(255,255,255,.06)',
            background: 'rgba(255,255,255,.015)',
          }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', flexShrink: 0, background: value ? color : 'rgba(255,255,255,.2)' }} />
            <span style={{ fontWeight: 700, fontSize: 12, color: value ? color : C.subtle }}>{label}</span>
            {value && <span style={{ marginLeft: 'auto', fontSize: 10, color, fontWeight: 700 }}>✓ Assigned</span>}
          </div>
          <div style={{ padding: '10px 13px' }}>
            {options.length === 0
              ? <div style={{ fontSize: 11, color: C.red, padding: '7px 11px', borderRadius: 7, background: 'rgba(248,113,113,.07)', border: '1px solid rgba(248,113,113,.2)' }}>
                  No {label}s found — add one in User List first.
                </div>
              : <select className="ifield" style={{ ...inp, margin: 0 }} value={value} onChange={onChange}>
                  <option value="">— Select {label} —</option>
                  {options.map(o => (
                    <option key={o.email} value={o.email}>
                      {o.full_name || o.email}{o.department ? ` · ${o.department}` : ''}
                    </option>
                  ))}
                </select>
            }
          </div>
        </div>
      );

      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>

          {/* Role bar */}
          {ntRole && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 11, padding: '11px 13px', borderRadius: 9,
              background: `${ntRole.color}0c`, border: `1px solid ${ntRole.color}22`,
            }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, flexShrink: 0, background: `${ntRole.color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: ntRole.color }}>
                <NTIcon size={14} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, fontSize: 12, color: ntRole.color }}>{ntRole.label}</div>
                <div style={{ fontSize: 10, color: C.muted }}>{ntRole.desc}</div>
              </div>
              <button type="button" onClick={() => { setErr(null); setStep(0); }}
                style={{ fontSize: 11, color: C.muted, background: 'transparent', border: '1px solid rgba(255,255,255,.08)', borderRadius: 7, padding: '4px 9px', cursor: 'pointer' }}>
                Change
              </button>
            </div>
          )}

          {/* Reviewer roles — no workflow config needed */}
          {!isStaff && (
            <InfoBox color="purple">
              This role acts as a reviewer in the NT appraisal workflow. No approval chain setup is needed for reviewer accounts.
            </InfoBox>
          )}

          {/* Workflow builder — staff only */}
          {isStaff && (
            <>
              {/* Toggle chain builder */}
              <div>
                <SL>Configure Approval Chain</SL>
                {templatesLoading
                  ? <div style={{ fontSize: 11, color: C.muted, padding: 12, borderRadius: 8, background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.06)' }}>Loading templates…</div>
                  : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>

                      {/* Toggle 1: Direct to VC */}
                      <ToggleRow
                        label="Skip all reviewers — send directly to VC"
                        sub="Staff's appraisal bypasses RO and Registrar and goes straight to the VC"
                        checked={ntDirectVC}
                        onChange={v => {
                          setNtDirectVC(v);
                          if (v) {
                            setNtHasFirstReviewer(false);
                            setForm(p => ({ ...p, reporting_officer_email: '', registrar_email: '' }));
                          }
                        }}
                        color="#f472b6"
                      />

                      {/* Toggle 2: First-level reviewer (hidden when directVC) */}
                      {!ntDirectVC && (
                        <ToggleRow
                          label="Include a first-level reviewer"
                          sub="A Reporting Officer or Department Head reviews the appraisal before escalation"
                          checked={ntHasFirstReviewer}
                          onChange={v => {
                            setNtHasFirstReviewer(v);
                            if (!v) setForm(p => ({ ...p, reporting_officer_email: '' }));
                          }}
                          color="#fb923c"
                        >
                          {/* Reviewer type choice: RO vs Dept Head */}
                          <div style={{ display: 'flex', gap: 8 }}>
                            {[
                              { val: 'ro',       label: 'Reporting Officer', sub: 'Standard first-level review'    },
                              { val: 'depthead', label: 'Department Head',   sub: 'Head of department reviews first' },
                            ].map(opt => (
                              <button
                                type="button" key={opt.val}
                                onClick={() => setNtFirstReviewerType(opt.val)}
                                style={{
                                  flex: 1, padding: '9px 10px', borderRadius: 9, cursor: 'pointer', textAlign: 'left',
                                  border: `1.5px solid ${ntFirstReviewerType === opt.val ? '#fb923c' : 'rgba(255,255,255,.09)'}`,
                                  background: ntFirstReviewerType === opt.val ? 'rgba(251,146,60,.1)' : 'rgba(255,255,255,.03)',
                                  transition: 'all .15s',
                                }}
                              >
                                <div style={{ fontWeight: 700, fontSize: 11, color: ntFirstReviewerType === opt.val ? '#fb923c' : C.text, marginBottom: 2 }}>
                                  {opt.label}
                                </div>
                                <div style={{ fontSize: 9, color: C.muted }}>{opt.sub}</div>
                              </button>
                            ))}
                          </div>
                        </ToggleRow>
                      )}

                      {/* Toggle 3: Include Registrar (shown only when has first reviewer) */}
                      {!ntDirectVC && ntHasFirstReviewer && (
                        <ToggleRow
                          label="Include Registrar after first reviewer"
                          sub="Registrar reviews and approves before the final VC sign-off"
                          checked={ntRegRequired}
                          onChange={v => {
                            setNtRegRequired(v);
                            if (!v) setForm(p => ({ ...p, registrar_email: '' }));
                          }}
                          color="#22d3ee"
                        />
                      )}
                    </div>
                  )
                }
              </div>

              {/* No templates exist at all */}
              {noTemplatesAtAll && (
                <div style={{
                  padding: '10px 14px', borderRadius: 8, fontSize: 11, lineHeight: 1.6,
                  color: C.red, background: 'rgba(248,113,113,.07)',
                  border: '1px solid rgba(248,113,113,.22)',
                }}>
                  <strong>No workflow templates found.</strong> You must create at least one template before adding NT staff.{' '}
                  <button type="button" onClick={() => navigate('/workflow/templates')}
                    style={{ color: C.red, fontWeight: 700, background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline', fontSize: 11 }}>
                    Create templates →
                  </button>
                </div>
              )}

              {/* No-template warning */}
              {noTemplateMatch && (
                <div style={{
                  padding: '10px 14px', borderRadius: 8, fontSize: 11, lineHeight: 1.6,
                  color: C.yellow, background: 'rgba(251,191,36,.07)',
                  border: '1px solid rgba(251,191,36,.22)',
                }}>
                  <strong>No matching template found</strong> for
                  &ldquo;{buildChainLabel(ntDirectVC, ntHasFirstReviewer, ntFirstReviewerType, ntRegRequired)}&rdquo;.
                  The default template will be used at appraisal time, which may not match this chain.
                  Set up the correct template in{' '}
                  <button type="button" onClick={() => navigate('/workflow/templates')}
                    style={{ color: C.yellow, fontWeight: 700, background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline', fontSize: 11 }}>
                    Workflow Templates
                  </button>{' '}first.
                </div>
              )}

              {/* Chain preview */}
              <div>
                <SL>Approval Chain Preview</SL>
                <div style={{
                  display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 0,
                  padding: '12px 14px', borderRadius: 10,
                  background: 'rgba(255,255,255,.02)', border: '1px solid rgba(255,255,255,.06)',
                }}>
                  {chainNodes.map((node, i) => (
                    <div key={node + i} style={{ display: 'flex', alignItems: 'center' }}>
                      <div style={{
                        padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                        background: `${nodeColorMap[node] ?? C.accent}14`,
                        border: `1.5px solid ${nodeColorMap[node] ?? C.accent}30`,
                        color: nodeColorMap[node] ?? C.accent,
                      }}>
                        {node}
                      </div>
                      {i < chainNodes.length - 1 && (
                        <span style={{ padding: '0 6px', color: 'rgba(255,255,255,.2)', fontSize: 15 }}>→</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Assign reviewers */}
              <div>
                <SL>Assign Reviewers</SL>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

                  {/* First reviewer picker (RO or DeptHead) */}
                  {!ntDirectVC && ntHasFirstReviewer && (
                    <PersonPicker
                      label={ntFirstReviewerType === 'ro' ? 'Reporting Officer' : 'Department Head'}
                      color="#fb923c"
                      value={form.reporting_officer_email}
                      onChange={set('reporting_officer_email')}
                      options={ros}
                    />
                  )}

                  {/* Registrar picker — shown when no first reviewer (base chain) OR ntRegRequired is ON */}
                  {!ntDirectVC && (!ntHasFirstReviewer || ntRegRequired) && (
                    <PersonPicker
                      label="Registrar"
                      color="#22d3ee"
                      value={form.registrar_email}
                      onChange={set('registrar_email')}
                      options={registrarsList}
                    />
                  )}

                  {/* VC — always auto-assigned */}
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 9,
                    padding: '10px 13px', borderRadius: 10,
                    background: 'rgba(244,114,182,.04)', border: '1px solid rgba(244,114,182,.12)',
                  }}>
                    <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#f472b6', flexShrink: 0 }} />
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 12, color: '#f472b6' }}>VC</div>
                      <div style={{ fontSize: 10, color: C.muted, marginTop: 1 }}>
                        Auto-assigned — VC reviews all NT appraisals at the final step
                      </div>
                    </div>
                    <div style={{ marginLeft: 'auto', fontSize: 10, color: '#f472b6', background: 'rgba(244,114,182,.1)', border: '1px solid rgba(244,114,182,.2)', borderRadius: 20, padding: '2px 8px', fontWeight: 700, flexShrink: 0 }}>
                      Auto ✓
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      );
    }

    // ── Teaching / CISR: role cards + school/dept ──
    return (
    <div>
      {/* ── Role cards ── */}
      <SL>Role</SL>
      <div style={{ display: 'grid', gridTemplateColumns: roleGridCols, gap: 10, marginBottom: 20 }}>
        {availRoles.map(r => {
          const RIcon  = r.icon;
          const active = role === r.value;
          return (
            <button
              key={r.value}
              type="button"
              onClick={() => handleRole(r.value)}
              className="act-btn"
              style={{
                padding: '12px 13px', borderRadius: 10, textAlign: 'left', cursor: 'pointer',
                border: `1.5px solid ${active ? r.color : 'rgba(255,255,255,.07)'}`,
                background: active ? `${r.color}12` : 'rgba(255,255,255,.02)',
                position: 'relative',
              }}
            >
              <div style={{ color: active ? r.color : C.muted, marginBottom: 7 }}>
                <RIcon size={17} />
              </div>
              <div style={{ fontWeight: 700, fontSize: 12, color: active ? r.color : C.text, marginBottom: 3 }}>
                {r.label}
              </div>
              <div style={{ fontSize: 10, color: C.muted, lineHeight: 1.4 }}>
                Flow: {r.flow}
              </div>
              {r.soEmrOnly && (
                <div style={{ marginTop: 3, fontSize: 9, color: '#a78bfa', fontWeight: 600 }}>
                  SoEMR only
                </div>
              )}
              {active && (
                <div style={{ position: 'absolute', top: 9, right: 9, width: 7, height: 7, borderRadius: '50%', background: r.color }} />
              )}
            </button>
          );
        })}
      </div>

      {/* ── Contextual notes ── */}
      {role === 'dean' && (isEngineering || isNonEng) && (
        <InfoBox color="green">
          {isEngineering
            ? 'Dean of Engineering oversees all 4 engineering schools (SoCSEA, SoBB, SoCE, SoEMR). No specific school or department is required.'
            : 'Dean of Non-Engineering oversees all 5 non-engineering schools (SoCM, SoMCS, SoHSS, SoD, SoAA). No specific school or department is required.'}
        </InfoBox>
      )}
      {role === 'hod' && (
        <InfoBox color="purple">
          HOD exists only within SoEMR. The school is auto-assigned — just select the department below.
        </InfoBox>
      )}

      {/* ── School picker — dropdown (non-Dean, non-HOD) ── */}
      {showSchoolPicker && (
        <div style={{ marginBottom: 18 }}>
          <SL>{isEngineering ? 'Engineering School' : 'Non-Engineering School'}</SL>
          <select
            className="ifield"
            value={school}
            onChange={e => handleSchool(e.target.value)}
            style={inp}
          >
            <option value="">— Select School —</option>
            {groupSchools.map(s => (
              <option key={s.code} value={s.code}>
                {s.full} ({s.code})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* ── HOD: SoEMR locked display ── */}
      {schoolLocked && (
        <div style={{ marginBottom: 18 }}>
          <SL>School (auto-assigned)</SL>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 14px', borderRadius: 9,
            background: 'rgba(167,139,250,.07)', border: '1.5px solid rgba(167,139,250,.22)',
          }}>
            <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 13, fontWeight: 700, color: '#a78bfa' }}>
              SoEMR
            </span>
            <span style={{ fontSize: 12, color: C.subtle }}>
              School of Engineering, Management & Research
            </span>
          </div>
        </div>
      )}

      {/* ── CISR: locked school display ── */}
      {isCISR && !!role && (
        <div style={{ marginBottom: 18 }}>
          <SL>School (auto-assigned)</SL>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 14px', borderRadius: 9,
            background: 'rgba(251,146,60,.07)', border: '1.5px solid rgba(251,146,60,.22)',
          }}>
            <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 13, fontWeight: 700, color: C.orange }}>
              CISR
            </span>
            <span style={{ fontSize: 12, color: C.subtle }}>
              Center for Interdisciplinary Studies & Research
            </span>
          </div>
        </div>
      )}

      {/* ── Department — SoEMR dropdown ── */}
      {showDeptFixed && (
        <div>
          <SL>Department</SL>
          <select
            className="ifield"
            value={dept}
            onChange={e => setForm(p => ({ ...p, department: e.target.value }))}
            style={inp}
          >
            <option value="">— Select Department —</option>
            {SOEMR_DEPTS.map(d => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>
      )}

      {/* ── Department — free text for other schools ── */}
      {showDeptText && (
        <div>
          <label style={{ ...lbl, marginBottom: 5 }}>
            Department <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0, fontSize: 10 }}>(optional)</span>
          </label>
          <input
            className="ifield"
            type="text"
            value={dept}
            onChange={e => setForm(p => ({ ...p, department: e.target.value }))}
            placeholder="e.g. Computer Science"
            style={inp}
          />
        </div>
      )}
    </div>
    );
  };

  const stepAccount = () => (
    <div>
      <SL>Login Credentials</SL>
      <div style={{ marginBottom: 14 }}>
        <Field label="Full Name" req>
          <input className="ifield" type="text" value={form.full_name}
            onChange={set('full_name')} placeholder="Dr. First Last" style={inp} />
        </Field>
      </div>
      <div style={{ ...g2, marginBottom: 16 }}>
        <Field label="Email Address" req>
          <input className="ifield" type="email" value={form.email}
            onChange={set('email')} placeholder="staff@dypiu.edu" style={inp} />
        </Field>
        <Field label="Password" req>
          <input className="ifield" type="text" value={form.password}
            onChange={set('password')} placeholder="Temporary password" style={inp} />
          <div style={{ fontSize: 10, color: C.muted, marginTop: 5 }}>
            Default temporary password is <span style={{ fontFamily: "'JetBrains Mono',monospace", color: C.yellow }}>demo123</span> — the user should change it on first login.
          </div>
        </Field>
      </div>
      <div style={{
        padding: '10px 14px', borderRadius: 8, fontSize: 11, color: C.muted, lineHeight: 1.6,
        background: 'rgba(255,255,255,.025)', border: '1px solid rgba(255,255,255,.06)',
      }}>
        Account is created immediately. Staff can log in right away — email verification is skipped for admin-created accounts.
      </div>
    </div>
  );

  const stepProfile = () => (
    <div>
      <SL>Professional Details</SL>
      <div style={{ ...g2, marginBottom: 14 }}>
        <Field label="Designation">
          <input className="ifield" type="text" value={form.designation}
            onChange={set('designation')} placeholder="e.g. Assistant Professor" style={inp} />
        </Field>
        <Field label="Phone">
          <input className="ifield" type="text" value={form.phone}
            onChange={set('phone')} placeholder="+91 XXXXX XXXXX" style={inp} />
        </Field>
      </div>
      <div style={{ ...g2 }}>
        <Field label="Qualification">
          <input className="ifield" type="text" value={form.qualification}
            onChange={set('qualification')} placeholder="e.g. Ph.D" style={inp} />
        </Field>
        <Field label="Teaching Experience">
          <input className="ifield" type="text" value={form.teaching_experience}
            onChange={set('teaching_experience')} placeholder="e.g. 8 years" style={inp} />
        </Field>
      </div>
      <div style={{ marginTop: 14, fontSize: 11, color: C.muted }}>
        All fields on this step are optional and can be edited later from the Faculty List page.
      </div>
    </div>
  );

  const RENDERERS = [stepClassify, stepRoleSchool, stepAccount, stepProfile];

  // ── Summary rows ─────────────────────────────────────────────────────────────

  const roleMeta    = availRoles.find(r => r.value === role);
  const summaryRows = [
    { k: 'Category', v: staffType === 'teaching' ? 'Teaching' : staffType === 'non_teaching' ? 'Non-Teaching' : null },
    { k: 'Track',    v: track === 'engineering' ? 'Engineering' : track === 'non_engineering' ? 'Non-Engineering' : track === 'cisr' ? 'CISR' : null },
    { k: 'Role',     v: roleMeta?.label ?? null },
    { k: 'School',   v: school || null },
    { k: 'Dept',     v: dept   || null },
    { k: 'Name',     v: form.full_name || null },
    { k: 'Email',    v: form.email     || null },
    { k: 'Approval Path', v: isNonTeaching && role === 'non_teaching_staff' ? buildChainLabel(ntDirectVC, ntHasFirstReviewer, ntFirstReviewerType, ntRegRequired) : null },
    { k: 'Rep. Officer',  v: form.reporting_officer_email ? (ros.find(r => r.email === form.reporting_officer_email)?.full_name || form.reporting_officer_email) : null },
    { k: 'Registrar',     v: form.registrar_email ? (registrarsList.find(r => r.email === form.registrar_email)?.full_name || form.registrar_email) : null },
  ].filter(r => r.v);

  // ── Render ────────────────────────────────────────────────────────────────────

  // ── Receipt modal ─────────────────────────────────────────────────────────────

  const receiptFields = receipt ? [
    { k: 'Full Name',  v: receipt.name        },
    { k: 'Email',      v: receipt.email       },
    { k: 'Role',       v: receipt.role        },
    { k: 'Staff Type', v: receipt.staffType   },
    receipt.school             && { k: 'School',      v: receipt.school             },
    receipt.department         && { k: 'Department',  v: receipt.department         },
    receipt.designation        && { k: 'Designation', v: receipt.designation        },
    receipt.phone              && { k: 'Phone',       v: receipt.phone              },
    receipt.qualification      && { k: 'Qualification', v: receipt.qualification    },
    receipt.teachingExperience && { k: 'Experience',  v: receipt.teachingExperience },
    receipt.template           && { k: 'Template',          v: receipt.template           },
    receipt.reportingOfficer   && { k: 'Reporting Officer', v: receipt.reportingOfficer   },
    receipt.registrar          && { k: 'Registrar',         v: receipt.registrar          },
  ].filter(Boolean) : [];

  return (
    <div className="page-enter" style={{ overflow: 'hidden' }}>

      {/* ── Import modal ──────────────────────────────────────────── */}
      {importModal && <ImportModal onClose={() => setImportModal(false)} />}

      {/* ── Receipt modal ─────────────────────────────────────────── */}
      {receipt && (
        <Modal maxWidth={480} onClose={() => setReceipt(null)}>
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
            <div style={{ width: 44, height: 44, borderRadius: '50%', flexShrink: 0,
              background: 'rgba(52,211,153,.15)', border: '1px solid rgba(52,211,153,.25)',
              display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <I.check size={20} stroke={C.green} />
            </div>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: C.text }}>Account Created</div>
              <div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>{receipt.createdAt}</div>
            </div>
          </div>

          {/* Detail rows */}
          <div style={{ marginBottom: 16 }}>
            {receiptFields.map((row, i) => (
              <div key={row.k} style={{
                display: 'flex', gap: 12, padding: '8px 0',
                borderBottom: i < receiptFields.length - 1 ? '1px solid rgba(255,255,255,.05)' : 'none',
              }}>
                <span style={{ fontSize: 12, color: C.muted, width: 110, flexShrink: 0 }}>{row.k}</span>
                <span style={{ fontSize: 12, color: C.text, fontWeight: 600, flex: 1,
                  wordBreak: 'break-all',
                  fontFamily: row.k === 'Email' ? "'JetBrains Mono',monospace" : 'inherit' }}>
                  {row.v}
                </span>
              </div>
            ))}
          </div>

          {/* Password notice */}
          <div style={{ marginBottom: 20, padding: '10px 12px', borderRadius: 8, fontSize: 11,
            lineHeight: 1.6, color: C.yellow,
            background: 'rgba(251,191,36,.07)', border: '1px solid rgba(251,191,36,.18)' }}>
            Password is <strong>not included</strong> in this receipt. Share login credentials with the user separately through a secure channel.
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="act-btn" style={{ ...pBtn, display: 'flex', alignItems: 'center', gap: 6 }}
              onClick={() => handlePrint(receipt)}>
              <I.dl size={13} /> Print Receipt
            </button>
            <button className="act-btn" style={oBtn} onClick={() => setReceipt(null)}>
              Add Another
            </button>
            <button className="act-btn"
              style={{ padding: '9px 14px', background: 'transparent', color: C.muted,
                border: '1px solid var(--c-btn-border)', borderRadius: 8, cursor: 'pointer',
                fontSize: 13, fontWeight: 600 }}
              onClick={() => navigate('/faculty')}>
              View User List
            </button>
          </div>
        </Modal>
      )}

      <PageHead
        title="Add User"
        sub="The appraisal routing is determined automatically from the role assigned here"
        action={
          <button
            className="act-btn"
            style={oBtn}
            onClick={() => setImportModal(true)}
          >
            <I.dl size={13} style={{ marginRight: 5 }} /> Import Faculty List
          </button>
        }
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 300px', gap: 16, alignItems: 'start' }}>

        {/* ── Main form card ── */}
        <Card delay={0}>
          <Stepper current={step} steps={isNonTeaching
            ? [
                { label: 'Classification', sub: 'Staff type & role'      },
                { label: 'Workflow',       sub: 'Approval template'       },
                { label: 'Account',        sub: 'Login credentials'       },
                { label: 'Profile',        sub: 'Professional details'    },
              ]
            : STEPS}
          />

          {/* Step heading */}
          <div style={{ marginBottom: 22 }}>
            <div style={{ fontSize: 17, fontWeight: 700, color: C.text }}>
              {step === 1 && isNonTeaching ? 'Workflow Setup' : STEPS[step].label}
            </div>
            <div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>
              {step === 1 && isNonTeaching ? 'Assign an approval template for this staff member' : STEPS[step].sub}
            </div>
          </div>

          {/* Animated step content */}
          <div key={step} style={{ animation: 'fadeUp .2s cubic-bezier(.22,1,.36,1) both' }}>
            {RENDERERS[step]()}
          </div>

          {/* Error */}
          {err && (
            <div style={{
              marginTop: 16, padding: '10px 14px', borderRadius: 8, fontSize: 13,
              color: C.red, background: 'rgba(248,113,113,.08)', border: '1px solid rgba(248,113,113,.2)',
            }}>
              {err}
            </div>
          )}

          {/* Success */}
          {success && (
            <div style={{
              marginTop: 16, padding: '12px 14px', borderRadius: 8, fontSize: 13,
              color: C.green, background: 'rgba(52,211,153,.08)', border: '1px solid rgba(52,211,153,.2)',
            }}>
              ✓ Account created for <strong>{success}</strong>. Form has been reset — you can add another.
            </div>
          )}

          {/* Navigation */}
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            marginTop: 24, paddingTop: 18, borderTop: '1px solid rgba(255,255,255,.05)',
          }}>
            <div>
              {step > 0 && (
                <button
                  className="act-btn"
                  style={oBtn}
                  onClick={() => { setErr(null); setStep(s => s - 1); }}
                >
                  ← Back
                </button>
              )}
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                className="act-btn"
                style={{ ...oBtn, fontSize: 12 }}
                onClick={() => navigate('/faculty')}
              >
                Cancel
              </button>
              <button
                className="act-btn"
                style={pBtn}
                onClick={handleNext}
                disabled={saving}
              >
                {saving ? 'Creating…' : step === 3 ? 'Create Account' : 'Continue →'}
              </button>
            </div>
          </div>
        </Card>

        {/* ── Right panel ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* Summary */}
          <Card title="Summary" delay={60}>
            {summaryRows.length === 0 ? (
              <div style={{ fontSize: 11, color: C.muted, textAlign: 'center', padding: '8px 0' }}>
                Selections will appear here
              </div>
            ) : (
              summaryRows.map((r, i) => (
                <div
                  key={r.k}
                  style={{
                    display: 'flex', justifyContent: 'space-between', gap: 8,
                    padding: '6px 0',
                    borderBottom: i < summaryRows.length - 1 ? '1px solid rgba(255,255,255,.04)' : 'none',
                  }}
                >
                  <span style={{ fontSize: 11, color: C.muted, flexShrink: 0 }}>{r.k}</span>
                  <span style={{ fontSize: 11, color: C.subtle, textAlign: 'right', wordBreak: 'break-all' }}>{r.v}</span>
                </div>
              ))
            )}
          </Card>

          {/* Appraisal Journey */}
          <Card
            title="Appraisal Journey"
            sub={isNonTeaching
              ? role === 'non_teaching_staff'
                ? `Chain: ${buildChainLabel(ntDirectVC, ntHasFirstReviewer, ntFirstReviewerType, ntRegRequired)}`
                : selectedTemplate
                  ? `Template: ${selectedTemplate.name}`
                  : 'Approval chain — default workflow'
              : 'Score visibility at each stage'}
            delay={100}
          >
            {isNonTeaching
              ? <>
                  <WorkflowTimeline
                    steps={displayNtSteps}
                    loading={ntWorkflowLoading && !selectedTemplate}
                    showStaff
                  />
                  <div style={{ display: 'flex', gap: 10, marginTop: 10, paddingTop: 10, borderTop: '1px solid rgba(255,255,255,.05)' }}>
                    <button type="button" onClick={() => navigate('/workflow/templates')}
                      style={{ fontSize: 10, color: C.accent, background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600, padding: 0 }}>
                      Manage Templates →
                    </button>
                    <span style={{ fontSize: 10, color: 'rgba(255,255,255,.15)' }}>|</span>
                    <button type="button" onClick={() => navigate('/workflow/designations')}
                      style={{ fontSize: 10, color: C.accent, background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600, padding: 0 }}>
                      Manage Designations →
                    </button>
                  </div>
                </>
              : <FlowPreview nodes={flowNodes} />
            }
          </Card>

        </div>
      </div>
    </div>
  );
}
