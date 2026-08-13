import { useSandbox } from './SandboxContext';
import { useState, useEffect } from 'react';

// ─── Tiny helper ──────────────────────────────────────────────────────────────
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
    const colNames = Object.keys(row);
    const args = colNames.map(k => Number(row[k]) || 0);
    const body = colNames.reduce((e, k) => e.replace(new RegExp(`\\b${k}\\b`, 'g'), Number(row[k]) || 0), expr);
    // eslint-disable-next-line no-new-func
    return new Function(`return (${body})`)() || 0;
  } catch { return '#ERR'; }
}

// ─── Part tab strip (faculty-style) ───────────────────────────────────────────
function PartTabs({ parts, active, onChange }) {
  if (parts.length <= 1) return null;
  return (
    <div style={{ display: 'flex', gap: 4, marginBottom: 28, borderBottom: '2px solid #e5e7eb', paddingBottom: 0 }}>
      {parts.map(p => (
        <button
          key={p}
          onClick={() => onChange(p)}
          style={{
            padding: '10px 22px', border: 'none', cursor: 'pointer', fontWeight: 700,
            fontSize: 13, background: 'transparent', letterSpacing: 0.3,
            color: active === p ? '#1d4ed8' : '#6b7280',
            borderBottom: `3px solid ${active === p ? '#1d4ed8' : 'transparent'}`,
            marginBottom: -2, transition: 'all 0.15s ease'
          }}
        >
          {p}
        </button>
      ))}
    </div>
  );
}

// ─── Table renderer ───────────────────────────────────────────────────────────
function DemoTable({ field, rows, setRows }) {
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

  const updateCell = (ri, name, val) => {
    const next = rows.map((r, i) => i === ri ? { ...r, [name]: val } : r);
    setRows(next);
  };

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
              <th
                key={ci}
                style={{
                  padding: '10px 14px', textAlign: 'left', fontWeight: 700,
                  color: '#374151', fontSize: 12.5, whiteSpace: 'normal',
                  wordBreak: 'break-word', verticalAlign: 'top',
                  width: col.width || undefined, minWidth: col.width || 80,
                  borderRight: ci < cols.length - 1 ? '1px solid #e5e7eb' : 'none'
                }}
              >
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
                const preVal = col.prefilled && col.prefilledValues ? (col.prefilledValues[ri] ?? '') : null;
                const cellVal = col.prefilled ? preVal : (col.type === 'formula' ? evaluateFormula(col.formulaExpr, row) : (row[col.name] ?? ''));
                return (
                  <td
                    key={ci}
                    style={{
                      padding: '8px 12px', color: '#111827',
                      width: col.width || undefined, minWidth: col.width || 80, verticalAlign: 'middle',
                      borderRight: ci < cols.length - 1 ? '1px solid #f1f5f9' : 'none'
                    }}
                  >
                    {col.prefilled || col.type === 'formula' ? (
                      <span style={{ color: col.prefilled ? '#6b7280' : '#111827', fontSize: 13 }}>{String(cellVal)}</span>
                    ) : col.type === 'dropdown' ? (
                      <select
                        value={cellVal}
                        onChange={e => updateCell(ri, col.name, e.target.value)}
                        style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13, background: '#fff', color: '#111827', outline: 'none' }}
                      >
                        <option value="">Select...</option>
                        {(Array.isArray(col.options) ? col.options : (col.options || '').split(',').map(o => o.trim()).filter(Boolean)).map(o => (
                          <option key={o} value={o}>{o}</option>
                        ))}
                      </select>
                    ) : col.type === 'checkbox' ? (
                      <input
                        type="checkbox"
                        checked={cellVal === 'true' || cellVal === true}
                        onChange={e => updateCell(ri, col.name, e.target.checked)}
                        style={{ width: 16, height: 16, cursor: 'pointer' }}
                      />
                    ) : col.type === 'number' ? (
                      <input
                        type="number"
                        value={cellVal}
                        onChange={e => updateCell(ri, col.name, clamp(e.target.value, col.minVal, col.maxMarks))}
                        placeholder={`${col.minVal ?? 0}–${col.maxMarks ?? '∞'}`}
                        style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13, color: '#111827', outline: 'none' }}
                      />
                    ) : (
                      <input
                        type="text"
                        value={cellVal}
                        onChange={e => updateCell(ri, col.name, e.target.value)}
                        style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13, color: '#111827', outline: 'none' }}
                      />
                    )}
                  </td>
                );
              })}
              {canDel && (
                <td style={{ padding: '8px 6px', textAlign: 'center' }}>
                  <button
                    onClick={() => delRow(ri)}
                    style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: 15, lineHeight: 1 }}
                    title="Remove row"
                  >✕</button>
                </td>
              )}
            </tr>
          ))}

          {canAdd && (
            <tr>
              <td colSpan={cols.length + (canDel ? 1 : 0)} style={{ padding: '8px 12px' }}>
                <button
                  onClick={addRow}
                  style={{
                    padding: '5px 14px', borderRadius: 6, border: '1px dashed #93c5fd',
                    background: '#eff6ff', color: '#1d4ed8', fontSize: 12, fontWeight: 600, cursor: 'pointer'
                  }}
                >
                  ➕ Add Row
                </button>
              </td>
            </tr>
          )}

          {hasAgg && (
            <tr style={{ background: '#f0fdf4', borderTop: '2px solid #bbf7d0' }}>
              {cols.map((col, ci) => (
                <td key={ci} style={{ padding: '8px 12px', fontWeight: 700, color: '#15803d', fontSize: 12 }}>
                  {col.aggregate && col.aggregate !== 'none' ? (
                    <span title={`${col.aggregate} of ${col.name}`}>
                      {col.aggregate.toUpperCase()}: {calcAgg(col)}
                    </span>
                  ) : null}
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

// ─── Main demo page ───────────────────────────────────────────────────────────
export default function SampleDemoTab() {
  const { currentFields, schoolDescriptions, selectedSchool, previewTables, setPreviewTables } = useSandbox();
  const [localTables, setLocalTables] = useState({});
  const [localValues, setLocalValues] = useState({});
  const [activePart, setActivePart] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  const parts = Array.from(new Set(currentFields.map(f => f.part || 'Part A'))).sort();

  useEffect(() => {
    if (!activePart && parts.length > 0) setActivePart(parts[0]);
  }, [parts.join(',')]);

  // Seed tables from previewTables or from defaultRowCount
  useEffect(() => {
    const seeded = {};
    currentFields.forEach(f => {
      if (f.type !== 'table') return;
      if (previewTables[f.id] && previewTables[f.id].length > 0) {
        seeded[f.id] = previewTables[f.id].map(r => ({ ...r }));
      } else {
        const n = f.defaultRowCount || 0;
        seeded[f.id] = Array.from({ length: n }, (_, ri) => {
          const row = {};
          (f.columns || []).forEach(c => {
            row[c.name] = c.prefilled && c.prefilledValues ? (c.prefilledValues[ri] ?? '') : (c.type === 'checkbox' ? 'false' : '');
          });
          return row;
        });
      }
    });
    setLocalTables(seeded);
  }, [currentFields]);

  const setFieldRows = (id, rows) => setLocalTables(prev => ({ ...prev, [id]: rows }));
  const setFieldVal = (id, val) => setLocalValues(prev => ({ ...prev, [id]: val }));

  const visibleFields = currentFields.filter(f => f.role === 'faculty' && (f.part === activePart || parts.length === 0));
  const guidelines = schoolDescriptions[selectedSchool];

  if (submitted) {
    return (
      <div style={{ minHeight: '100vh', background: '#f8fafc', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: "'Inter', sans-serif" }}>
        <div style={{ textAlign: 'center', maxWidth: 480, padding: 40 }}>
          <div style={{ fontSize: 56, marginBottom: 16 }}>✅</div>
          <h2 style={{ fontSize: 24, fontWeight: 800, color: '#111827', margin: '0 0 8px' }}>Form Submitted</h2>
          <p style={{ color: '#6b7280', marginBottom: 32, fontSize: 15 }}>
            This is a demo preview. In production, the data would be saved and routed through the approval workflow.
          </p>
          <button
            onClick={() => setSubmitted(false)}
            style={{ padding: '10px 28px', borderRadius: 8, background: '#1d4ed8', color: '#fff', border: 'none', fontWeight: 700, fontSize: 14, cursor: 'pointer' }}
          >
            ← Back to Form
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f1f5f9', fontFamily: "'Inter', system-ui, sans-serif" }}>
      {/* Header banner */}
      <div style={{ background: 'linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 100%)', padding: '28px 0' }}>
        <div style={{ maxWidth: 860, margin: '0 auto', padding: '0 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                <span style={{ background: 'rgba(255,255,255,0.15)', color: '#bfdbfe', fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 20, letterSpacing: 1, textTransform: 'uppercase' }}>
                  Sample Preview
                </span>
              </div>
              <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: '#fff', lineHeight: 1.3 }}>
                Faculty Self-Appraisal Form
              </h1>
              <p style={{ margin: '4px 0 0', fontSize: 13, color: '#93c5fd' }}>
                {selectedSchool} · Academic Year 2024–25
              </p>
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <div style={{ fontSize: 12, color: '#93c5fd', marginBottom: 2 }}>Status</div>
              <div style={{ background: '#fbbf24', color: '#78350f', fontSize: 12, fontWeight: 700, padding: '4px 12px', borderRadius: 20 }}>
                In Progress
              </div>
            </div>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 860, margin: '0 auto', padding: '32px 24px' }}>
        {/* Guidelines banner */}
        {guidelines && (
          <div style={{
            background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10,
            padding: '14px 18px', marginBottom: 28, display: 'flex', gap: 12, alignItems: 'flex-start'
          }}>
            <span style={{ fontSize: 18, flexShrink: 0, marginTop: 1 }}>ℹ️</span>
            <div>
              <div style={{ fontWeight: 700, color: '#1d4ed8', fontSize: 13, marginBottom: 4 }}>Form Guidelines</div>
              <div style={{ color: '#1e40af', fontSize: 13, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{guidelines}</div>
            </div>
          </div>
        )}

        {/* Part tabs */}
        <PartTabs parts={parts} active={activePart} onChange={setActivePart} />

        {/* Field cards */}
        {visibleFields.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#9ca3af', padding: '80px 0', fontSize: 14 }}>
            No faculty fields defined for this section yet.
          </div>
        ) : (
          visibleFields.map(field => (
            <div
              key={field.id}
              style={{
                background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb',
                padding: '22px 24px', marginBottom: 20, boxShadow: '0 1px 4px rgba(0,0,0,0.05)'
              }}
            >
              {/* Field header */}
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                  <label style={{ fontWeight: 700, fontSize: 14.5, color: '#111827', lineHeight: 1.4 }}>
                    {field.label}
                    {field.required && <span style={{ color: '#ef4444', marginLeft: 4 }}>*</span>}
                  </label>
                  <span style={{ fontSize: 10.5, color: '#6b7280', background: '#f3f4f6', padding: '3px 8px', borderRadius: 20, fontWeight: 600, whiteSpace: 'nowrap', flexShrink: 0 }}>
                    {field.type.toUpperCase()}
                  </span>
                </div>
                {field.description && (
                  <p style={{ margin: '6px 0 0', fontSize: 12.5, color: '#6b7280', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                    💡 {field.description}
                  </p>
                )}
              </div>

              {/* Field input */}
              {field.type === 'table' ? (
                <DemoTable
                  field={field}
                  rows={localTables[field.id] || []}
                  setRows={(rows) => setFieldRows(field.id, rows)}
                />
              ) : field.type === 'text' ? (
                <input
                  type="text"
                  value={localValues[field.id] || ''}
                  onChange={e => setFieldVal(field.id, e.target.value)}
                  placeholder={`Enter ${field.label.toLowerCase()}...`}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13.5, color: '#111827', outline: 'none', boxSizing: 'border-box' }}
                />
              ) : field.type === 'textarea' ? (
                <textarea
                  value={localValues[field.id] || ''}
                  onChange={e => setFieldVal(field.id, e.target.value)}
                  placeholder={`Enter ${field.label.toLowerCase()}...`}
                  rows={4}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13.5, color: '#111827', outline: 'none', resize: 'vertical', boxSizing: 'border-box' }}
                />
              ) : field.type === 'number' ? (
                <div>
                  <input
                    type="number"
                    value={localValues[field.id] || ''}
                    onChange={e => setFieldVal(field.id, clamp(e.target.value, field.minVal, field.rowMaxMarks))}
                    placeholder={`Score range: ${field.minVal ?? 0} to ${field.rowMaxMarks ?? '∞'}`}
                    style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13.5, color: '#111827', outline: 'none', boxSizing: 'border-box' }}
                  />
                  {(field.rowMaxMarks) && (
                    <div style={{ fontSize: 11.5, color: '#6b7280', marginTop: 5 }}>
                      Score range: {field.minVal ?? 0} – {field.rowMaxMarks}
                    </div>
                  )}
                </div>
              ) : field.type === 'dropdown' ? (
                <select
                  value={localValues[field.id] || ''}
                  onChange={e => setFieldVal(field.id, e.target.value)}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13.5, color: '#111827', outline: 'none', background: '#fff' }}
                >
                  <option value="">Select an option...</option>
                  {(Array.isArray(field.options) ? field.options : (field.options || '').split(',').map(o => o.trim()).filter(Boolean)).map(o => (
                    <option key={o} value={o}>{o}</option>
                  ))}
                </select>
              ) : field.type === 'checkbox' ? (
                <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', fontSize: 14 }}>
                  <input
                    type="checkbox"
                    checked={localValues[field.id] === true}
                    onChange={e => setFieldVal(field.id, e.target.checked)}
                    style={{ width: 18, height: 18, cursor: 'pointer' }}
                  />
                  <span style={{ color: '#374151' }}>{field.label}</span>
                </label>
              ) : (
                <div style={{ color: '#9ca3af', fontSize: 13, fontStyle: 'italic' }}>
                  [{field.type} input]
                </div>
              )}
            </div>
          ))
        )}

        {/* Submit bar */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '20px 24px', background: '#fff', borderRadius: 12,
          border: '1px solid #e5e7eb', marginTop: 8
        }}>
          <p style={{ margin: 0, fontSize: 12.5, color: '#6b7280' }}>
            ⚠️ This is a <strong>Sample Demo</strong> — no data will actually be saved.
          </p>
          <button
            onClick={() => setSubmitted(true)}
            style={{
              padding: '11px 32px', borderRadius: 8, background: '#1d4ed8',
              color: '#fff', border: 'none', fontWeight: 700, fontSize: 14, cursor: 'pointer',
              transition: 'background 0.15s ease'
            }}
            onMouseEnter={e => e.currentTarget.style.background = '#1e40af'}
            onMouseLeave={e => e.currentTarget.style.background = '#1d4ed8'}
          >
            Submit Form →
          </button>
        </div>
      </div>
    </div>
  );
}
