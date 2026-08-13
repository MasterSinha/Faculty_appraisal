import { useSandbox } from './SandboxContext';
import { useState, useEffect } from 'react';

// ─── Helpers ───────────────────────────────────────────────────────────────────
const clamp = (val, min, max) => {
  if (val === '' || isNaN(Number(val))) return val;
  let n = Number(val);
  if (min !== undefined && n < Number(min)) n = Number(min);
  if (max !== undefined && n > Number(max)) n = Number(max);
  return n.toString();
};

function evaluateFormula(expr, row) {
  if (!expr) return '';
  try {
    const body = Object.keys(row).reduce(
      (e, k) => e.replace(new RegExp(`\\b${k}\\b`, 'g'), Number(row[k]) || 0), expr
    );
    // eslint-disable-next-line no-new-func
    return new Function(`return (${body})`)() ?? 0;
  } catch { return '#ERR'; }
}

// ─── Workflow progress bar ─────────────────────────────────────────────────────
function WorkflowBar({ currentStep, completedSteps }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: 28 }}>
      {WORKFLOW.map((stage, i) => {
        const done = completedSteps.includes(stage.role);
        const active = i === currentStep;
        const future = i > currentStep;
        return (
          <div key={stage.role} style={{ display: 'flex', alignItems: 'center', flex: i < WORKFLOW.length - 1 ? 1 : 0 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5 }}>
              <div style={{
                width: 36, height: 36, borderRadius: '50%', display: 'flex', alignItems: 'center',
                justifyContent: 'center', fontWeight: 800, fontSize: 11,
                background: done ? stage.color : active ? stage.color : '#e5e7eb',
                color: done || active ? '#fff' : '#9ca3af',
                boxShadow: active ? `0 0 0 4px ${stage.border}` : 'none',
                transition: 'all 0.2s ease',
                border: `2px solid ${done || active ? stage.color : '#d1d5db'}`
              }}>
                {done ? '✓' : stage.short}
              </div>
              <span style={{
                fontSize: 10.5, fontWeight: active ? 700 : 500, whiteSpace: 'nowrap',
                color: done ? stage.color : active ? stage.color : '#9ca3af'
              }}>
                {stage.label}
              </span>
            </div>
            {i < WORKFLOW.length - 1 && (
              <div style={{
                flex: 1, height: 2, margin: '0 4px', marginBottom: 18,
                background: completedSteps.includes(WORKFLOW[i + 1]?.role) || done
                  ? `linear-gradient(90deg, ${stage.color}, ${WORKFLOW[i + 1].color})`
                  : '#e5e7eb',
                transition: 'all 0.3s ease'
              }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Read-only field display ───────────────────────────────────────────────────
function ReadOnlyField({ field, value, tableRows }) {
  const stageInfo = WORKFLOW.find(s => s.role === field.role) || WORKFLOW[0];
  if (field.type === 'table') {
    const cols = field.columns || [];
    const rows = tableRows || [];
    return (
      <div style={{ overflowX: 'auto', borderRadius: 8, border: '1px solid #e5e7eb', background: '#fafafa' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
          <thead>
            <tr style={{ background: '#f3f4f6' }}>
              {cols.map((col, ci) => (
                <th key={ci} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: '#6b7280', fontSize: 12 }}>
                  {col.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={cols.length} style={{ padding: '12px', color: '#9ca3af', fontSize: 12, textAlign: 'center' }}>No data entered</td></tr>
            ) : rows.map((row, ri) => (
              <tr key={ri} style={{ borderBottom: '1px solid #f1f5f9' }}>
                {cols.map((col, ci) => {
                  const pv = col.prefilled && col.prefilledValues ? (col.prefilledValues[ri] ?? '') : null;
                  const cv = col.prefilled ? pv : (col.type === 'formula' ? evaluateFormula(col.formulaExpr, row) : (row[col.name] ?? ''));
                  return (
                    <td key={ci} style={{ padding: '8px 12px', color: '#374151' }}>
                      {col.type === 'checkbox' ? (cv === 'true' || cv === true ? '☑ Yes' : '☐ No') : String(cv)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  const displayVal = value !== undefined && value !== '' ? String(value) : <span style={{ color: '#9ca3af', fontStyle: 'italic' }}>Not filled</span>;
  return (
    <div style={{ padding: '10px 14px', background: '#f9fafb', borderRadius: 8, border: '1px solid #e5e7eb', fontSize: 13.5, color: '#374151', minHeight: 40 }}>
      {field.type === 'checkbox' ? (value ? '☑ Yes' : '☐ No') : displayVal}
    </div>
  );
}

// ─── Editable table ────────────────────────────────────────────────────────────
function EditableTable({ field, rows, setRows }) {
  const cols = field.columns || [];
  const canAdd = field.allowAddRows !== false;
  const canDel = field.allowDeleteRows !== false;

  const addRow = () => {
    const row = {};
    cols.forEach(c => {
      row[c.name] = c.prefilled && c.prefilledValues ? (c.prefilledValues[rows.length] ?? '') : (c.type === 'checkbox' ? 'false' : '');
    });
    setRows([...rows, row]);
  };

  const updateCell = (ri, name, val) => setRows(rows.map((r, i) => i === ri ? { ...r, [name]: val } : r));
  const delRow = (ri) => setRows(rows.filter((_, i) => i !== ri));

  const hasAgg = cols.some(c => c.aggregate && c.aggregate !== 'none');
  const calcAgg = (col) => {
    const nums = rows.map(r => Number(r[col.name]) || 0);
    if (!nums.length) return '';
    switch (col.aggregate) {
      case 'sum': return nums.reduce((a, b) => a + b, 0);
      case 'avg': return (nums.reduce((a, b) => a + b, 0) / nums.length).toFixed(2);
      case 'max': return Math.max(...nums);
      case 'min': return Math.min(...nums);
      default: return '';
    }
  };

  return (
    <div style={{ overflowX: 'auto', borderRadius: 10, border: '1px solid #e5e7eb', background: '#fff' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e5e7eb' }}>
            {cols.map((col, ci) => (
              <th key={ci} style={{
                padding: '10px 14px', textAlign: 'left', fontWeight: 700, color: '#374151', fontSize: 12.5,
                whiteSpace: 'normal', wordBreak: 'break-word', verticalAlign: 'top',
                width: col.width || undefined, minWidth: col.width || 80,
                borderRight: ci < cols.length - 1 ? '1px solid #e5e7eb' : 'none'
              }}>
                {col.name}
                {col.prefilled && <span style={{ marginLeft: 4, fontSize: 10, color: '#9ca3af', fontWeight: 500 }}>(fixed)</span>}
                {col.maxMarks && <div style={{ fontSize: 10, color: '#6b7280', fontWeight: 500, marginTop: 2 }}>Max: {col.maxMarks}</div>}
              </th>
            ))}
            {canDel && <th style={{ width: 36, padding: '10px 6px' }} />}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} style={{ borderBottom: '1px solid #f1f5f9' }}>
              {cols.map((col, ci) => {
                const pv = col.prefilled && col.prefilledValues ? (col.prefilledValues[ri] ?? '') : null;
                const cv = col.prefilled ? pv : (col.type === 'formula' ? evaluateFormula(col.formulaExpr, row) : (row[col.name] ?? ''));
                return (
                  <td key={ci} style={{ padding: '8px 12px', borderRight: ci < cols.length - 1 ? '1px solid #f1f5f9' : 'none', verticalAlign: 'middle' }}>
                    {col.prefilled || col.type === 'formula' ? (
                      <span style={{ color: col.prefilled ? '#6b7280' : '#111827', fontSize: 13 }}>{String(cv)}</span>
                    ) : col.type === 'dropdown' ? (
                      <select value={cv} onChange={e => updateCell(ri, col.name, e.target.value)}
                        style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13, background: '#fff', color: '#111827' }}>
                        <option value="">Select...</option>
                        {(Array.isArray(col.options) ? col.options : (col.options || '').split(',').map(o => o.trim()).filter(Boolean)).map(o => (
                          <option key={o} value={o}>{o}</option>
                        ))}
                      </select>
                    ) : col.type === 'checkbox' ? (
                      <input type="checkbox" checked={cv === 'true' || cv === true}
                        onChange={e => updateCell(ri, col.name, e.target.checked)}
                        style={{ width: 16, height: 16, cursor: 'pointer' }} />
                    ) : col.type === 'number' ? (
                      <input type="number" value={cv}
                        onChange={e => updateCell(ri, col.name, clamp(e.target.value, col.minVal, col.maxMarks))}
                        placeholder={`${col.minVal ?? 0}–${col.maxMarks ?? '∞'}`}
                        style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13, color: '#111827' }} />
                    ) : (
                      <input type="text" value={cv}
                        onChange={e => updateCell(ri, col.name, e.target.value)}
                        style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13, color: '#111827' }} />
                    )}
                  </td>
                );
              })}
              {canDel && (
                <td style={{ padding: '8px 6px', textAlign: 'center' }}>
                  <button onClick={() => delRow(ri)}
                    style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: 15 }} title="Remove row">✕</button>
                </td>
              )}
            </tr>
          ))}
          {canAdd && (
            <tr>
              <td colSpan={cols.length + (canDel ? 1 : 0)} style={{ padding: '8px 12px' }}>
                <button onClick={addRow} style={{ padding: '5px 14px', borderRadius: 6, border: '1px dashed #93c5fd', background: '#eff6ff', color: '#1d4ed8', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
                  ➕ Add Row
                </button>
              </td>
            </tr>
          )}
          {hasAgg && (
            <tr style={{ background: '#f0fdf4', borderTop: '2px solid #bbf7d0' }}>
              {cols.map((col, ci) => (
                <td key={ci} style={{ padding: '8px 12px', fontWeight: 700, color: '#15803d', fontSize: 12 }}>
                  {col.aggregate && col.aggregate !== 'none' ? `${col.aggregate.toUpperCase()}: ${calcAgg(col)}` : null}
                </td>
              ))}
              {canDel && <td />}
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// ─── Single field card ─────────────────────────────────────────────────────────
function FieldCard({ field, value, setValue, tableRows, setTableRows, readOnly, ownerInfo }) {
  const badge = readOnly
    ? { label: `Filled by ${ownerInfo?.label || field.role}`, color: ownerInfo?.color || '#6b7280', bg: ownerInfo?.bg || '#f3f4f6', border: ownerInfo?.border || '#e5e7eb' }
    : { label: 'Your field', color: ownerInfo?.color || '#1d4ed8', bg: ownerInfo?.bg || '#eff6ff', border: ownerInfo?.border || '#bfdbfe' };

  return (
    <div style={{
      background: '#fff', borderRadius: 12, border: `1px solid ${readOnly ? '#f1f5f9' : '#e5e7eb'}`,
      padding: '20px 24px', marginBottom: 16,
      boxShadow: readOnly ? 'none' : '0 1px 6px rgba(0,0,0,0.06)',
      opacity: readOnly ? 0.85 : 1
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <label style={{ fontWeight: 700, fontSize: 14.5, color: readOnly ? '#6b7280' : '#111827', lineHeight: 1.4 }}>
            {field.label}
            {field.required && !readOnly && <span style={{ color: '#ef4444', marginLeft: 4 }}>*</span>}
          </label>
          {field.description && (
            <p style={{ margin: '5px 0 0', fontSize: 12.5, color: '#6b7280', whiteSpace: 'pre-wrap', lineHeight: 1.55 }}>
              💡 {field.description}
            </p>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
          <span style={{ fontSize: 10, color: badge.color, background: badge.bg, border: `1px solid ${badge.border}`, padding: '2px 9px', borderRadius: 20, fontWeight: 700, whiteSpace: 'nowrap' }}>
            {badge.label}
          </span>
          {readOnly && (
            <span style={{ fontSize: 10, color: '#9ca3af', fontStyle: 'italic' }}>read-only</span>
          )}
        </div>
      </div>

      {readOnly ? (
        <ReadOnlyField field={field} value={value} tableRows={tableRows} />
      ) : field.type === 'table' ? (
        <EditableTable field={field} rows={tableRows || []} setRows={setTableRows} />
      ) : field.type === 'textarea' ? (
        <textarea value={value || ''} onChange={e => setValue(e.target.value)} rows={4} placeholder={`Enter ${field.label.toLowerCase()}...`}
          style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13.5, color: '#111827', resize: 'vertical', boxSizing: 'border-box', fontFamily: 'inherit' }} />
      ) : field.type === 'number' ? (
        <div>
          <input type="number" value={value || ''} onChange={e => setValue(clamp(e.target.value, field.minVal, field.rowMaxMarks))}
            placeholder={`Score range: ${field.minVal ?? 0} – ${field.rowMaxMarks ?? '∞'}`}
            style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13.5, color: '#111827', boxSizing: 'border-box' }} />
          {field.rowMaxMarks && <div style={{ fontSize: 11.5, color: '#6b7280', marginTop: 4 }}>Score range: {field.minVal ?? 0} – {field.rowMaxMarks}</div>}
        </div>
      ) : field.type === 'dropdown' ? (
        <select value={value || ''} onChange={e => setValue(e.target.value)}
          style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13.5, color: '#111827', background: '#fff' }}>
          <option value="">Select an option...</option>
          {(Array.isArray(field.options) ? field.options : (field.options || '').split(',').map(o => o.trim()).filter(Boolean)).map(o => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
      ) : field.type === 'checkbox' ? (
        <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', fontSize: 14 }}>
          <input type="checkbox" checked={value === true} onChange={e => setValue(e.target.checked)}
            style={{ width: 18, height: 18, cursor: 'pointer' }} />
          <span style={{ color: '#374151' }}>{field.label}</span>
        </label>
      ) : (
        <input type="text" value={value || ''} onChange={e => setValue(e.target.value)} placeholder={`Enter ${field.label.toLowerCase()}...`}
          style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13.5, color: '#111827', boxSizing: 'border-box' }} />
      )}
    </div>
  );
}

// ─── Main Demo ─────────────────────────────────────────────────────────────────
export default function SampleDemoTab() {
  const { currentFields, schoolDescriptions, selectedSchool, sandboxRoles } = useSandbox();

  // Build workflow from dynamic roles sorted by level
  const WORKFLOW = [...sandboxRoles].sort((a, b) => a.level - b.level).map(r => ({
    role: r.key,
    label: r.name,
    short: r.name.slice(0, 2).toUpperCase(),
    color: r.color,
    bg: `${r.color}12`,
    border: `${r.color}40`
  }));

  const [currentStep, setCurrentStep] = useState(0);           // index into WORKFLOW
  const [completedSteps, setCompletedSteps] = useState([]);     // roles already submitted
  const [fieldValues, setFieldValues] = useState({});           // { fieldId: value }
  const [tableDatas, setTableDatas] = useState({});             // { fieldId: rows[] }
  const [activePart, setActivePart] = useState(null);
  const [reviewNote, setReviewNote] = useState('');
  const [reviewNotes, setReviewNotes] = useState({});           // { role: note }
  const [finalApproved, setFinalApproved] = useState(false);

  const currentStage = WORKFLOW[currentStep];
  const guidelines = schoolDescriptions[selectedSchool];

  // Collect all parts
  const allParts = Array.from(new Set(currentFields.map(f => f.part || 'Part A'))).sort();

  useEffect(() => {
    if (!activePart && allParts.length > 0) setActivePart(allParts[0]);
  }, [allParts.join(',')]);

  // Seed table default rows when switching stages
  useEffect(() => {
    const next = { ...tableDatas };
    currentFields.forEach(f => {
      if (f.type !== 'table' || next[f.id]) return;
      const n = f.defaultRowCount || 0;
      next[f.id] = Array.from({ length: n }, (_, ri) => {
        const row = {};
        (f.columns || []).forEach(c => {
          row[c.name] = c.prefilled && c.prefilledValues ? (c.prefilledValues[ri] ?? '') : (c.type === 'checkbox' ? 'false' : '');
        });
        return row;
      });
    });
    setTableDatas(next);
  }, [currentFields]);

  const setVal = (id, val) => setFieldValues(prev => ({ ...prev, [id]: val }));
  const setTableRows = (id, rows) => setTableDatas(prev => ({ ...prev, [id]: rows }));

  // Which fields are visible in current part
  const fieldsInPart = currentFields.filter(f => f.part === activePart || allParts.length === 0);

  // Fields owned by roles already done (previous roles) — shown read-only above
  const prevRoles = completedSteps;
  const prevFields = fieldsInPart.filter(f => prevRoles.includes(f.role));
  // Fields owned by current role — editable
  const myFields = fieldsInPart.filter(f => f.role === currentStage.role);
  // Future fields — hidden

  const handleAdvance = () => {
    const notes = { ...reviewNotes, [currentStage.role]: reviewNote };
    setReviewNotes(notes);
    setReviewNote('');
    setCompletedSteps(prev => [...prev, currentStage.role]);
    if (currentStep < WORKFLOW.length - 1) {
      setCurrentStep(s => s + 1);
    } else {
      setFinalApproved(true);
    }
  };

  const handleReset = () => {
    setCurrentStep(0);
    setCompletedSteps([]);
    setFieldValues({});
    setTableDatas({});
    setReviewNotes({});
    setReviewNote('');
    setFinalApproved(false);
  };

  // ── Final approved screen ──
  if (finalApproved) {
    return (
      <div style={{ minHeight: '100vh', background: '#f8fafc', fontFamily: "'Inter', system-ui, sans-serif", display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 32 }}>
        <div style={{ textAlign: 'center', maxWidth: 500 }}>
          <div style={{ fontSize: 64, marginBottom: 16 }}>🎉</div>
          <h2 style={{ fontSize: 26, fontWeight: 800, color: '#111827', margin: '0 0 10px' }}>Form Fully Approved</h2>
          <p style={{ color: '#6b7280', fontSize: 15, lineHeight: 1.7, marginBottom: 28 }}>
            The appraisal form has successfully passed through all <strong>{WORKFLOW.length} stages</strong> of the approval workflow. In production, this data would be stored and a final PDF would be generated.
          </p>
          <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', padding: '20px 24px', marginBottom: 28, textAlign: 'left' }}>
            <div style={{ fontWeight: 700, fontSize: 13, color: '#374151', marginBottom: 12 }}>Reviewer Notes Summary</div>
            {WORKFLOW.map(s => reviewNotes[s.role] ? (
              <div key={s.role} style={{ marginBottom: 10 }}>
                <span style={{ fontWeight: 700, color: s.color, fontSize: 12 }}>{s.label}: </span>
                <span style={{ color: '#374151', fontSize: 12 }}>{reviewNotes[s.role]}</span>
              </div>
            ) : null)}
            {Object.values(reviewNotes).every(n => !n) && (
              <div style={{ color: '#9ca3af', fontSize: 12, fontStyle: 'italic' }}>No notes were added.</div>
            )}
          </div>
          <button onClick={handleReset}
            style={{ padding: '12px 32px', borderRadius: 8, background: '#1d4ed8', color: '#fff', border: 'none', fontWeight: 700, fontSize: 14, cursor: 'pointer' }}>
            ↺ Reset & Try Again
          </button>
        </div>
      </div>
    );
  }

  const isLastStage = currentStep === WORKFLOW.length - 1;
  const isFacultyStage = currentStage.role === 'faculty';
  const actionLabel = isFacultyStage ? 'Submit Form' : isLastStage ? 'Final Approve' : `Approve & Pass to ${WORKFLOW[currentStep + 1]?.label}`;

  return (
    <div style={{ minHeight: '100vh', background: '#f1f5f9', fontFamily: "'Inter', system-ui, sans-serif" }}>
      {/* Header */}
      <div style={{ background: `linear-gradient(135deg, ${currentStage.color}dd 0%, ${currentStage.color} 100%)`, padding: '24px 0' }}>
        <div style={{ maxWidth: 900, margin: '0 auto', padding: '0 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
            <div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.7)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 5 }}>
                Sample Demo · {selectedSchool}
              </div>
              <h1 style={{ margin: 0, fontSize: 21, fontWeight: 800, color: '#fff' }}>
                Faculty Self-Appraisal Form
              </h1>
              <p style={{ margin: '4px 0 0', fontSize: 13, color: 'rgba(255,255,255,0.75)' }}>
                Currently viewing as: <strong style={{ color: '#fff' }}>{currentStage.label}</strong>
              </p>
            </div>
            <button onClick={handleReset}
              style={{ padding: '8px 18px', borderRadius: 8, background: 'rgba(255,255,255,0.15)', border: '1px solid rgba(255,255,255,0.3)', color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
              ↺ Reset Demo
            </button>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 900, margin: '0 auto', padding: '28px 24px' }}>
        {/* Workflow progress bar */}
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', padding: '20px 24px', marginBottom: 24 }}>
          <div style={{ fontWeight: 700, fontSize: 12.5, color: '#6b7280', marginBottom: 16, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Approval Workflow Progress
          </div>
          <WorkflowBar currentStep={currentStep} completedSteps={completedSteps} />
        </div>

        {/* Guidelines (faculty only) */}
        {guidelines && isFacultyStage && (
          <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10, padding: '14px 18px', marginBottom: 22, display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <span style={{ fontSize: 18, flexShrink: 0, marginTop: 1 }}>ℹ️</span>
            <div>
              <div style={{ fontWeight: 700, color: '#1d4ed8', fontSize: 13, marginBottom: 4 }}>Form Guidelines</div>
              <div style={{ color: '#1e40af', fontSize: 13, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{guidelines}</div>
            </div>
          </div>
        )}

        {/* Part tabs */}
        {allParts.length > 1 && (
          <div style={{ display: 'flex', gap: 4, marginBottom: 24, borderBottom: '2px solid #e5e7eb' }}>
            {allParts.map(p => (
              <button key={p} onClick={() => setActivePart(p)}
                style={{ padding: '10px 22px', border: 'none', cursor: 'pointer', fontWeight: 700, fontSize: 13, background: 'transparent', letterSpacing: 0.3, color: activePart === p ? currentStage.color : '#6b7280', borderBottom: `3px solid ${activePart === p ? currentStage.color : 'transparent'}`, marginBottom: -2, transition: 'all 0.15s ease' }}>
                {p}
              </button>
            ))}
          </div>
        )}

        {/* Previous-role fields (read-only) */}
        {prevFields.length > 0 && (
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 11.5, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 12 }}>
              Previously Filled Sections (read-only)
            </div>
            {prevFields.map(field => {
              const ownerInfo = WORKFLOW.find(s => s.role === field.role);
              return (
                <FieldCard
                  key={field.id}
                  field={field}
                  value={fieldValues[field.id]}
                  tableRows={tableDatas[field.id]}
                  readOnly={true}
                  ownerInfo={ownerInfo}
                />
              );
            })}
          </div>
        )}

        {/* Current role editable fields */}
        {myFields.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#9ca3af', padding: '60px 0', fontSize: 14, background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb' }}>
            No fields assigned to the <strong>{currentStage.label}</strong> role in this section.
          </div>
        ) : (
          <div>
            {prevFields.length > 0 && (
              <div style={{ fontSize: 11.5, fontWeight: 700, color: currentStage.color, textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 12 }}>
                {currentStage.label} Section — Your Fields
              </div>
            )}
            {myFields.map(field => (
              <FieldCard
                key={field.id}
                field={field}
                value={fieldValues[field.id]}
                setValue={val => setVal(field.id, val)}
                tableRows={tableDatas[field.id] || []}
                setTableRows={rows => setTableRows(field.id, rows)}
                readOnly={false}
                ownerInfo={currentStage}
              />
            ))}
          </div>
        )}

        {/* Reviewer note (for non-faculty stages) */}
        {!isFacultyStage && (
          <div style={{ background: '#fff', borderRadius: 12, border: `1px solid ${currentStage.border}`, padding: '20px 24px', marginTop: 8, marginBottom: 8 }}>
            <label style={{ fontWeight: 700, fontSize: 13.5, color: '#374151', display: 'block', marginBottom: 8 }}>
              {currentStage.label} Review Notes <span style={{ fontSize: 12, color: '#9ca3af', fontWeight: 500 }}>(optional)</span>
            </label>
            <textarea
              value={reviewNote}
              onChange={e => setReviewNote(e.target.value)}
              rows={3}
              placeholder={`Add any comments or review notes as ${currentStage.label}...`}
              style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: `1px solid ${currentStage.border}`, fontSize: 13.5, color: '#111827', resize: 'vertical', boxSizing: 'border-box', fontFamily: 'inherit', outline: 'none' }}
            />
          </div>
        )}

        {/* Action bar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 24px', background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', marginTop: 16 }}>
          <p style={{ margin: 0, fontSize: 12.5, color: '#6b7280' }}>
            ⚠️ <strong>Demo mode</strong> — no data will be saved to the server.
          </p>
          <button
            onClick={handleAdvance}
            style={{ padding: '11px 28px', borderRadius: 8, background: currentStage.color, color: '#fff', border: 'none', fontWeight: 700, fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, transition: 'opacity 0.15s ease' }}
            onMouseEnter={e => e.currentTarget.style.opacity = '0.88'}
            onMouseLeave={e => e.currentTarget.style.opacity = '1'}
          >
            {isFacultyStage ? '📤' : isLastStage ? '✅' : '✓'} {actionLabel} →
          </button>
        </div>
      </div>
    </div>
  );
}
