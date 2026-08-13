import { useSandbox } from './SandboxContext';
import Card from '../../../components/Card';
import { I } from '../../../components/icons';
import { pBtn } from '../../../constants/styleTokens';
import { useRef, useState } from 'react';

export default function FormBuilderTab() {
  const {
    currentFields,
    simulatedRole, setSimulatedRole,
    calculateTotalMaxMarks,
    activePreviewTab, setActivePreviewTab,
    editingFieldId, setEditingFieldId,
    editingColumn, setEditingColumn,
    schoolForms, setSchoolForms,
    selectedSchool,
    updateField,
    deleteField,
    removeTableColumn,
    previewTables, setPreviewTables,
    updateTableCell,
    addTableRow,
    previewData, setPreviewData,
    disabledSections, setDisabledSections,
    deletePreviewTableRow,
    addPreviewTableRow,
    evaluateCellFormula,
    generateSqlAlchemyClasses,
    handleExportSchema,
    handleImportSchema,
    addField,
    schoolDescriptions,
    setSchoolDescriptions
  } = useSandbox();

  const fileInputRef = useRef(null);
  const [newOptionText, setNewOptionText] = useState('');

  const calculateColumnAggregate = (fieldId, col) => {
    if (!col.aggregate || col.aggregate === 'none') return '';
    const rows = previewTables[fieldId] || [];
    const values = rows.map(r => {
      const val = col.type === 'formula' ? evaluateCellFormula(col.formulaExpr, r) : r[col.name];
      return Number(val);
    }).filter(v => !isNaN(v) && v !== null && v !== undefined);

    if (values.length === 0) return '';

    switch (col.aggregate) {
      case 'sum': {
        const sum = values.reduce((a, b) => a + b, 0);
        return `Total: ${sum}`;
      }
      case 'avg': {
        const sum = values.reduce((a, b) => a + b, 0);
        const avg = (sum / values.length).toFixed(1);
        return `Avg: ${avg}`;
      }
      case 'max': {
        return `Max: ${Math.max(...values)}`;
      }
      case 'min': {
        return `Min: ${Math.min(...values)}`;
      }
      default: return '';
    }
  };

  const clampNumericValue = (val, minVal, maxVal) => {
    if (val === '' || isNaN(Number(val))) return val;
    let num = Number(val);
    const min = minVal !== undefined ? Number(minVal) : 0;
    const max = maxVal !== undefined ? Number(maxVal) : Infinity;
    if (num < min) num = min;
    if (num > max) num = max;
    return num.toString();
  };

  const renderFieldPreview = (field) => {
    const isReadOnly = field.role !== simulatedRole || field.access === 'reviewer-edit';
    const isDeselected = disabledSections[field.id];
    const canAddRows = field.allowAddRows !== false;
    const canDeleteRows = field.allowDeleteRows !== false;

    // Auto-initialize default rows from defaultRowCount if table is empty
    const defaultRowCount = field.defaultRowCount || 0;
    const existingRows = previewTables[field.id];
    if (defaultRowCount > 0 && (!existingRows || existingRows.length === 0)) {
      const initRows = Array.from({ length: defaultRowCount }, (_, rowIdx) => {
        const row = {};
        (field.columns || []).forEach(c => {
          if (c.prefilled && c.prefilledValues) {
            row[c.name] = c.prefilledValues[rowIdx] ?? '';
          } else {
            row[c.name] = c.type === 'checkbox' ? 'false' : '';
          }
        });
        return row;
      });
      // Use setTimeout to avoid render-phase setState
      setTimeout(() => setPreviewTables(prev => ({ ...prev, [field.id]: initRows })), 0);
    }

    if (field.type === 'table') {
      return (
        <div style={{ overflowX: 'auto', marginBottom: 12 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ background: 'var(--c-sidebar-icon-bg)', borderBottom: '2px solid var(--c-sidebar-icon-border)' }}>
                {(field.columns || []).map((col, cidx) => (
                  <th
                    key={cidx}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (simulatedRole === 'faculty' && field.role === 'faculty') {
                        setEditingColumn({
                          fieldId: field.id,
                          colIdx: cidx,
                          name: col.name,
                          type: col.type,
                          options: Array.isArray(col.options) ? [...col.options] : (col.options || '').split(',').map(o => o.trim()).filter(Boolean),
                          formulaExpr: col.formulaExpr || '',
                          maxMarks: col.maxMarks || '',
                          minVal: col.minVal === undefined ? 0 : col.minVal,
                          aggregate: col.aggregate || 'none',
                          width: col.width || '',
                          prefilled: col.prefilled || false,
                          prefilledValues: col.prefilledValues ? [...col.prefilledValues] : []
                        });
                      }
                    }}
                     style={{
                      padding: 8, textAlign: 'left', fontWeight: 600,
                      color: 'var(--c-sidebar-text)', cursor: 'pointer',
                      borderRight: '1px solid var(--c-sidebar-icon-border)',
                      whiteSpace: 'normal', wordBreak: 'break-word',
                      verticalAlign: 'top',
                      width: col.width ? col.width : undefined,
                      minWidth: col.width ? col.width : 80
                    }}
                    title="Click to edit column properties"
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <span>{col.name}</span>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                        {col.type === 'formula' && <span style={{ color: '#10b981', fontSize: 10 }}>(Formula)</span>}
                        {col.maxMarks && <span style={{ color: '#ec4899', fontSize: 10 }}>[Max: {col.maxMarks}]</span>}
                        <span style={{ color: '#94a3b8', fontSize: 10 }}>✏️</span>
                      </div>
                    </div>
                  </th>
                ))}
                {!isReadOnly && (
                  <th
                    onClick={(e) => {
                      e.stopPropagation();
                      setEditingColumn({
                        fieldId: field.id,
                        colIdx: -1,
                        name: '',
                        type: 'text',
                        options: '',
                        formulaExpr: '',
                        maxMarks: '',
                        minVal: 0,
                        aggregate: 'none',
                        width: '',
                        prefilled: false,
                        prefilledValues: []
                      });
                    }}
                    style={{
                      padding: '8px 12px', width: 90, color: '#3b82f6',
                      cursor: 'pointer', fontWeight: 700, fontSize: 11
                    }}
                  >
                    ➕ Add Column
                  </th>
                )}
                {(!isReadOnly && canDeleteRows) && <th style={{ padding: 8, width: 40 }} />}
              </tr>
            </thead>
            <tbody>
              {(previewTables[field.id] || []).map((row, rowIdx) => (
                <tr key={rowIdx} style={{ borderBottom: '1px solid var(--c-sidebar-icon-border)' }}>
                  {(field.columns || []).map((col, cidx) => {
                    // Pre-filled columns always show their preset value
                    const prefilledVal = col.prefilled && col.prefilledValues ? (col.prefilledValues[rowIdx] ?? '') : null;
                    const cellVal = col.prefilled ? prefilledVal : (col.type === 'formula' ? evaluateCellFormula(col.formulaExpr, row) : (row[col.name] || ''));
                    return (
                      <td key={cidx} style={{ padding: 8, color: 'var(--c-text)', width: col.width ? col.width : undefined, minWidth: col.width ? col.width : 80, verticalAlign: 'top' }}>
                        {isReadOnly || col.type === 'formula' || isDeselected || col.prefilled ? (
                          <span style={col.prefilled ? { color: 'var(--c-sidebar-muted)', fontStyle: 'italic', fontSize: 11 } : {}}>{String(cellVal)}</span>
                        ) : col.type === 'dropdown' ? (
                          <select
                            value={cellVal}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) => {
                              updateTableCell(field.id, rowIdx, col.name, e.target.value);
                            }}
                            style={{ padding: 4, borderRadius: 4, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 11 }}
                          >
                            <option value="">Select...</option>
                            {(Array.isArray(col.options) ? col.options : (col.options || '').split(',').map(o => o.trim()).filter(Boolean)).map(o => (
                              <option key={o} value={o}>{o}</option>
                            ))}
                          </select>
                        ) : col.type === 'checkbox' ? (
                          <input
                            type="checkbox"
                            onClick={(e) => e.stopPropagation()}
                            checked={cellVal === 'true' || cellVal === true}
                            onChange={(e) => {
                              updateTableCell(field.id, rowIdx, col.name, e.target.checked);
                            }}
                          />
                        ) : col.type === 'number' ? (
                          <input
                            type="number"
                            value={cellVal}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) => {
                              const clamped = clampNumericValue(e.target.value, col.minVal, col.maxMarks);
                              updateTableCell(field.id, rowIdx, col.name, clamped);
                            }}
                            placeholder={`[${col.minVal === undefined ? 0 : col.minVal}-${col.maxMarks || '∞'}]`}
                            style={{ padding: '4px 6px', width: '90%', borderRadius: 4, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 11 }}
                          />
                        ) : (
                          <input
                            type="text"
                            value={cellVal}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) => {
                              updateTableCell(field.id, rowIdx, col.name, e.target.value);
                            }}
                            style={{ padding: '4px 6px', width: '90%', borderRadius: 4, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 11 }}
                          />
                        )}
                      </td>
                    );
                  })}
                  {!isReadOnly && canDeleteRows && (
                    <td style={{ padding: 8, textAlign: 'center' }}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          const rows = [...(previewTables[field.id] || [])];
                          rows.splice(rowIdx, 1);
                          setPreviewTables({ ...previewTables, [field.id]: rows });
                        }}
                        style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer' }}
                      >
                        ✕
                      </button>
                    </td>
                  )}
                </tr>
              ))}
              {!isReadOnly && !isDeselected && canAddRows && (
                <tr>
                  <td colSpan={(field.columns || []).length + 2} style={{ padding: 8 }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        addTableRow(field.id, field.columns);
                      }}
                      style={{ padding: '4px 8px', borderRadius: 4, background: '#3b82f615', border: '1px dashed #3b82f640', color: '#3b82f6', cursor: 'pointer', fontSize: 11 }}
                    >
                      ➕ Add Row
                    </button>
                  </td>
                </tr>
              )}
              {(() => {
                const hasAggregates = (field.columns || []).some(col => col.aggregate && col.aggregate !== 'none');
                if (!hasAggregates) return null;
                return (
                  <tr style={{ background: 'var(--c-sidebar-icon-bg)', borderTop: '2px solid var(--c-sidebar-icon-border)', fontWeight: 'bold' }}>
                    {(field.columns || []).map((col, cidx) => {
                      const aggVal = calculateColumnAggregate(field.id, col);
                      return (
                        <td key={cidx} style={{ padding: 8, color: '#3b82f6', fontSize: 11.5 }}>
                          {aggVal}
                        </td>
                      );
                    })}
                    {!isReadOnly && <td />}
                    {!isReadOnly && <td />}
                  </tr>
                );
              })()}
            </tbody>
          </table>
        </div>
      );
    }

    if (field.type === 'textarea') {
      return (
        <textarea
          disabled={isReadOnly || isDeselected}
          value={previewData[field.id] || ''}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => setPreviewData({ ...previewData, [field.id]: e.target.value })}
          placeholder={isReadOnly ? `Locked. Controlled by ${field.role.toUpperCase()}` : "Enter response..."}
          style={{ width: '95%', minHeight: 60, padding: 8, borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13 }}
        />
      );
    }

    if (field.type === 'number') {
      return (
        <input
          type="number"
          disabled={isReadOnly || isDeselected}
          value={previewData[field.id] || ''}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => {
            const clamped = clampNumericValue(e.target.value, field.minVal, field.rowMaxMarks);
            setPreviewData({ ...previewData, [field.id]: clamped });
          }}
          placeholder={isReadOnly ? `Locked. Controlled by ${field.role.toUpperCase()}` : `Score Range: [${field.minVal === undefined ? 0 : field.minVal} to ${field.rowMaxMarks || 'unlimited'}]`}
          style={{ width: '95%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13 }}
        />
      );
    }

    return (
      <input
        type="text"
        disabled={isReadOnly || isDeselected}
        value={previewData[field.id] || ''}
        onClick={(e) => e.stopPropagation()}
        onChange={(e) => setPreviewData({ ...previewData, [field.id]: e.target.value })}
        placeholder={isReadOnly ? `Locked. Controlled by ${field.role.toUpperCase()}` : "Enter response..."}
        style={{ width: '95%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13 }}
      />
    );
  };

  return (
    <div style={{ width: '100%' }}>
      <Card title="Interactive Form Canvas (Excel & Google Forms Style)" description="Click any field card below to expand and edit settings inline. Click columns in tables to configure data types.">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20, borderBottom: '1px solid var(--c-sidebar-icon-border)', paddingBottom: 16 }}>
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Simulated Role View</label>
            <select
              value={simulatedRole}
              onChange={(e) => setSimulatedRole(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontWeight: 600 }}
            >
              <option value="faculty">Faculty (Self)</option>
              <option value="hod">HOD Reviewer</option>
              <option value="director">Director Reviewer</option>
              <option value="dean">Dean Reviewer</option>
              <option value="vc">VC Final Approval</option>
            </select>
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Simulation Appraisal Max Marks</label>
            <div style={{ padding: '8px 12px', borderRadius: 8, background: '#3b82f615', border: '1px solid #3b82f630', color: '#3b82f6', fontWeight: 800, textAlign: 'center' }}>
              {calculateTotalMaxMarks()} Marks
            </div>
          </div>
        </div>

        <div style={{ marginBottom: 20 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Global Form Instructions & Submission Guidelines</label>
          <textarea
            value={schoolDescriptions[selectedSchool] || ''}
            onChange={(e) => setSchoolDescriptions({ ...schoolDescriptions, [selectedSchool]: e.target.value })}
            placeholder="Enter instructions that appear at the top of the form..."
            style={{ width: '100%', minHeight: 50, padding: '8px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12.5, marginTop: 4 }}
          />
        </div>

        {/* Tab Navigation for Parts */}
        {(() => {
          const previewParts = Array.from(new Set(currentFields.map(f => f.part || 'Part A'))).sort();
          return (
            <>
              {previewParts.length > 0 && (
                <div style={{ display: 'flex', gap: 8, marginBottom: 20, borderBottom: '1px solid var(--c-sidebar-icon-border)', paddingBottom: 12 }}>
                  {previewParts.map(part => (
                    <button
                      key={part}
                      onClick={() => setActivePreviewTab(part)}
                      style={{
                        padding: '6px 14px', borderRadius: 8, border: 'none', fontSize: 12.5, cursor: 'pointer',
                        background: activePreviewTab === part ? '#3b82f6' : 'var(--c-sidebar-icon-bg)',
                        color: activePreviewTab === part ? '#fff' : 'var(--c-sidebar-muted)',
                        fontWeight: 600
                      }}
                    >
                      {part}
                    </button>
                  ))}
                </div>
              )}

              {/* Fields Canvas */}
              <div style={{ minHeight: 300 }} onClick={() => setEditingFieldId(null)}>
                {schoolDescriptions[selectedSchool] && (
                  <div style={{
                    padding: '12px 16px', borderRadius: 12, background: 'rgba(59, 130, 246, 0.08)',
                    border: '1px solid rgba(59, 130, 246, 0.15)', color: 'var(--c-text)', fontSize: 12.5,
                    marginBottom: 20, display: 'flex', gap: 10, alignItems: 'flex-start'
                  }}>
                    <span style={{ fontSize: 18, flexShrink: 0, marginTop: 2 }}>ℹ️</span>
                    <div>
                      <strong style={{ color: '#3b82f6' }}>Form Guidelines:</strong>{' '}
                      <span style={{ whiteSpace: 'pre-wrap' }}>{schoolDescriptions[selectedSchool]}</span>
                    </div>
                  </div>
                )}
                {currentFields.filter(field => field.part === activePreviewTab || previewParts.length === 0).length === 0 ? (
                  <div style={{ color: 'var(--c-sidebar-muted)', textAlign: 'center', marginTop: 80 }}>
                    No fields defined in this section yet. Click 'Add Field' buttons below to start.
                  </div>
                ) : (
                  currentFields
                    .filter(field => field.part === activePreviewTab || previewParts.length === 0)
                    .map(field => {
                      const isEditingThisField = field.id === editingFieldId;
                      if (isEditingThisField) {
                        return (
                          <div
                            key={field.id}
                            onClick={(e) => e.stopPropagation()}
                            style={{
                              padding: 20, borderRadius: 12, background: 'var(--c-sidebar-icon-bg)',
                              border: '2px solid #3b82f6', boxShadow: '0 4px 20px rgba(59, 130, 246, 0.1)',
                              marginBottom: 20, transition: 'all 0.2s ease', position: 'relative'
                            }}
                          >
                            {/* Properties Editor */}
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                              <div style={{ display: 'flex', gap: 12 }}>
                                <div style={{ flex: 2 }}>
                                  <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Field Label Name</label>
                                  <input
                                    type="text"
                                    value={field.label}
                                    onChange={(e) => updateField(field.id, 'label', e.target.value)}
                                    style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13, marginTop: 4 }}
                                  />
                                </div>
                                <div style={{ flex: 1 }}>
                                  <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Field Type</label>
                                  <select
                                    value={field.type}
                                    onChange={(e) => updateField(field.id, 'type', e.target.value)}
                                    style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13, marginTop: 4 }}
                                  >
                                    <option value="text">Text Input</option>
                                    <option value="number">Number Input</option>
                                    <option value="textarea">Textarea (Paragraph)</option>
                                    <option value="table">Table Grid (Excel-like)</option>
                                  </select>
                                </div>
                              </div>

                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center', marginTop: 4 }}>
                                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--c-text)' }}>
                                  <input
                                    type="checkbox"
                                    checked={field.required}
                                    onChange={(e) => updateField(field.id, 'required', e.target.checked)}
                                  />
                                  Required Field
                                </label>

                                {field.type === 'table' && (
                                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--c-text)' }}>
                                    <input
                                      type="checkbox"
                                      checked={field.isOptional}
                                      onChange={(e) => updateField(field.id, 'isOptional', e.target.checked)}
                                    />
                                    Optional Table
                                  </label>
                                )}

                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                  <span style={{ fontSize: 12, color: 'var(--c-sidebar-muted)' }}>Part:</span>
                                  <select
                                    value={field.part}
                                    onChange={(e) => updateField(field.id, 'part', e.target.value)}
                                    style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12 }}
                                  >
                                    <option value="Part A">Part A</option>
                                    <option value="Part B">Part B</option>
                                    <option value="Part C">Part C</option>
                                    <option value="Part D">Part D</option>
                                  </select>
                                </div>

                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                  <span style={{ fontSize: 12, color: 'var(--c-sidebar-muted)' }}>Owner:</span>
                                  <select
                                    value={field.role}
                                    onChange={(e) => updateField(field.id, 'role', e.target.value)}
                                    style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12 }}
                                  >
                                    <option value="faculty">Faculty (Self)</option>
                                    <option value="hod">HOD Reviewer</option>
                                    <option value="director">Director Reviewer</option>
                                    <option value="dean">Dean Reviewer</option>
                                    <option value="vc">VC Final Approval</option>
                                  </select>
                                </div>

                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                  <span style={{ fontSize: 12, color: 'var(--c-sidebar-muted)' }}>Access:</span>
                                  <select
                                    value={field.access}
                                    onChange={(e) => updateField(field.id, 'access', e.target.value)}
                                    style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12 }}
                                  >
                                    <option value="full">Full Access</option>
                                    <option value="reviewer-edit">Reviewer Edit Only</option>
                                    <option value="reviewer-hidden">Secret to Faculty</option>
                                  </select>
                                </div>
                              </div>

                              {field.type === 'table' && (
                                <div style={{ borderTop: '1px solid var(--c-sidebar-icon-border)', paddingTop: 12, marginTop: 4, display: 'flex', flexDirection: 'column', gap: 12 }}>
                                  <div style={{ display: 'flex', gap: 16 }}>
                                    <div style={{ flex: 1 }}>
                                      <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Attachment Mode</label>
                                      <select
                                        value={field.attachmentType}
                                        onChange={(e) => updateField(field.id, 'attachmentType', e.target.value)}
                                        style={{ width: '100%', padding: '6px 10px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12, marginTop: 4 }}
                                      >
                                        <option value="none">No Attachments</option>
                                        <option value="per-row">One PDF per Row</option>
                                        <option value="per-table">One PDF for the Entire Table</option>
                                      </select>
                                    </div>
                                    <div style={{ flex: 1 }}>
                                      <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Default Row Count</label>
                                      <input
                                        type="number"
                                        min={0}
                                        max={50}
                                        value={field.defaultRowCount ?? 1}
                                        onChange={(e) => updateField(field.id, 'defaultRowCount', Number(e.target.value))}
                                        style={{ width: '100%', padding: '6px 10px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12, marginTop: 4 }}
                                      />
                                    </div>
                                  </div>
                                  <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
                                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--c-text)', cursor: 'pointer' }}>
                                      <input
                                        type="checkbox"
                                        checked={field.allowAddRows !== false}
                                        onChange={(e) => updateField(field.id, 'allowAddRows', e.target.checked)}
                                      />
                                      Allow user to add rows
                                    </label>
                                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--c-text)', cursor: 'pointer' }}>
                                      <input
                                        type="checkbox"
                                        checked={field.allowDeleteRows !== false}
                                        onChange={(e) => updateField(field.id, 'allowDeleteRows', e.target.checked)}
                                      />
                                      Allow user to delete rows
                                    </label>
                                  </div>
                                </div>
                              )}

                              {field.type === 'number' && (
                                <div style={{ borderTop: '1px solid var(--c-sidebar-icon-border)', paddingTop: 12, marginTop: 4, display: 'flex', gap: 16 }}>
                                  <div style={{ flex: 1 }}>
                                    <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Min Value Constraint</label>
                                    <input
                                      type="number"
                                      value={field.minVal === undefined ? 0 : field.minVal}
                                      onChange={(e) => updateField(field.id, 'minVal', Number(e.target.value))}
                                      style={{ width: '100%', padding: '6px 10px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12, marginTop: 4 }}
                                    />
                                  </div>
                                  <div style={{ flex: 1 }}>
                                    <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Max Marks Limit (Score Limit)</label>
                                    <input
                                      type="number"
                                      value={field.rowMaxMarks}
                                      onChange={(e) => updateField(field.id, 'rowMaxMarks', Number(e.target.value))}
                                      style={{ width: '100%', padding: '6px 10px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12, marginTop: 4 }}
                                    />
                                  </div>
                                </div>
                              )}

                              <div style={{ marginTop: 12 }}>
                                <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Field Guidelines / Description (Instructions next to field)</label>
                                <textarea
                                  value={field.description || ''}
                                  onChange={(e) => updateField(field.id, 'description', e.target.value)}
                                  placeholder="Describe how the user should fill this field or table..."
                                  style={{ width: '100%', minHeight: 45, padding: '6px 10px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12, marginTop: 4 }}
                                />
                              </div>
                            </div>

                            <div style={{ marginTop: 16, borderTop: '1px dashed var(--c-sidebar-icon-border)', paddingTop: 12 }}>
                              {field.description && (
                                <div style={{ fontSize: 11.5, color: 'var(--c-sidebar-muted)', marginTop: 2, marginBottom: 8, fontStyle: 'italic', display: 'flex', gap: 4, alignItems: 'flex-start' }}>
                                  <span style={{ flexShrink: 0 }}>💡</span>
                                  <span style={{ whiteSpace: 'pre-wrap' }}>{field.description}</span>
                                </div>
                              )}
                              {renderFieldPreview(field)}
                            </div>

                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 16, borderTop: '1px solid var(--c-sidebar-icon-border)', paddingTop: 12 }}>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  deleteField(field.id);
                                  setEditingFieldId(null);
                                }}
                                style={{
                                  background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)',
                                  padding: '6px 12px', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                                  display: 'flex', alignItems: 'center', gap: 4
                                }}
                              >
                                🗑️ Delete Field
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setEditingFieldId(null);
                                }}
                                style={{
                                  background: '#3b82f6', color: '#fff', border: 'none',
                                  padding: '6px 16px', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer'
                                }}
                              >
                                Done Editing
                              </button>
                            </div>
                          </div>
                        );
                      }

                      // Regular Inactive card preview mode
                      return (
                        <div
                          key={field.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingFieldId(field.id);
                          }}
                          style={{
                            padding: 16, borderRadius: 12, background: 'var(--c-sidebar-icon-bg)',
                            border: '1px solid var(--c-sidebar-icon-border)', marginBottom: 20,
                            cursor: 'pointer', transition: 'all 0.15s ease',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.05)'
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.borderColor = '#3b82f650'}
                          onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--c-sidebar-icon-border)'}
                          title="Click to edit field settings"
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--c-text)' }}>
                              {field.label} {field.required && <span style={{ color: '#ef4444' }}>*</span>}
                            </span>
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                              <span style={{ fontSize: 9, color: 'var(--c-sidebar-muted)', background: 'var(--c-bg)', padding: '2px 6px', borderRadius: 4, fontWeight: 600 }}>
                                {field.type.toUpperCase()}
                              </span>
                              <span style={{ fontSize: 9, color: '#10b981', background: '#10b98110', padding: '2px 6px', borderRadius: 4, fontWeight: 600 }}>
                                {field.part}
                              </span>
                              <span style={{ fontSize: 9, color: '#f59e0b', background: '#f59e0b10', padding: '2px 6px', borderRadius: 4, fontWeight: 600 }}>
                                {field.role.toUpperCase()}
                              </span>
                            </div>
                          </div>
                          
                          <div>
                            {field.description && (
                              <div style={{ fontSize: 11.5, color: 'var(--c-sidebar-muted)', marginTop: 2, marginBottom: 8, fontStyle: 'italic', display: 'flex', gap: 4, alignItems: 'flex-start' }}>
                                <span style={{ flexShrink: 0 }}>💡</span>
                                <span style={{ whiteSpace: 'pre-wrap' }}>{field.description}</span>
                              </div>
                            )}
                            {renderFieldPreview(field)}
                          </div>
                        </div>
                      );
                    })
                )}
              </div>
            </>
          );
        })()}

        {/* Sleek action bar to add fields */}
        <div style={{
          display: 'flex', flexWrap: 'wrap', gap: 12, justifyContent: 'center',
          padding: 20, borderRadius: 16, border: '2px dashed var(--c-sidebar-icon-border)',
          background: 'var(--c-sidebar-icon-bg)', marginTop: 24
        }}>
          <button
            onClick={() => addField('text')}
            style={{ padding: '10px 16px', borderRadius: 8, border: 'none', background: '#3b82f615', color: '#3b82f6', fontWeight: 600, fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            ➕ Add Text Field
          </button>

          <button
            onClick={() => addField('number')}
            style={{ padding: '10px 16px', borderRadius: 8, border: 'none', background: '#10b98115', color: '#10b981', fontWeight: 600, fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            ➕ Add Number Field
          </button>

          <button
            onClick={() => addField('table')}
            style={{ padding: '10px 16px', borderRadius: 8, border: 'none', background: '#a78bfa15', color: '#a78bfa', fontWeight: 600, fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            ➕ Add Table Grid
          </button>
        </div>
      </Card>

      {/* Column Properties Overlay Modal */}
      {editingColumn && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 9999, backdropFilter: 'blur(4px)'
        }}>
          <div style={{
            background: 'var(--c-bg)', border: '1px solid var(--c-sidebar-icon-border)',
            borderRadius: 16, padding: 24, width: 400, boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            color: 'var(--c-text)'
          }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: 16, fontWeight: 700 }}>
              {editingColumn.colIdx === -1 ? 'Add New Table Column' : 'Edit Column Properties'}
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Column Header Name</label>
                <input
                  type="text"
                  value={editingColumn.name}
                  onChange={(e) => setEditingColumn({ ...editingColumn, name: e.target.value })}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)', color: 'var(--c-text)', marginTop: 4 }}
                />
              </div>

              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--c-text)', cursor: 'pointer', padding: '6px 10px', borderRadius: 8, background: editingColumn.prefilled ? 'rgba(245,158,11,0.1)' : 'var(--c-sidebar-icon-bg)', border: `1px solid ${editingColumn.prefilled ? 'rgba(245,158,11,0.3)' : 'var(--c-sidebar-icon-border)'}`, userSelect: 'none' }}>
                <input
                  type="checkbox"
                  checked={editingColumn.prefilled || false}
                  onChange={(e) => setEditingColumn({ ...editingColumn, prefilled: e.target.checked })}
                />
                <span><strong>Pre-filled column</strong> — values are set by the creator and locked for users</span>
              </label>

              {editingColumn.prefilled && (() => {
                // Find parent field to get defaultRowCount
                const parentField = currentFields.find(f => f.id === editingColumn.fieldId);
                const rowCount = parentField?.defaultRowCount || 1;
                const vals = editingColumn.prefilledValues || [];
                return (
                  <div>
                    <label style={{ fontSize: 11, fontWeight: 600, color: '#f59e0b' }}>Pre-filled Values (one per default row)</label>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6 }}>
                      {Array.from({ length: rowCount }, (_, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 11, color: 'var(--c-sidebar-muted)', minWidth: 50 }}>Row {i + 1}:</span>
                          <input
                            type="text"
                            value={vals[i] || ''}
                            onChange={(e) => {
                              const newVals = [...vals];
                              newVals[i] = e.target.value;
                              setEditingColumn({ ...editingColumn, prefilledValues: newVals });
                            }}
                            style={{ flex: 1, padding: '5px 8px', borderRadius: 6, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)', color: 'var(--c-text)', fontSize: 12 }}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}

              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Data Type</label>
                <select
                  value={editingColumn.type}
                  onChange={(e) => setEditingColumn({ ...editingColumn, type: e.target.value })}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)', color: 'var(--c-text)', marginTop: 4 }}
                >
                  <option value="text">Text (General)</option>
                  <option value="number">Number (Numeric)</option>
                  <option value="dropdown">Dropdown (Selection)</option>
                  <option value="checkbox">Checkbox (Boolean)</option>
                  <option value="formula">Formula (Excel-like)</option>
                </select>
              </div>

              {editingColumn.type === 'dropdown' && (
                <div>
                  <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Dropdown Option Items</label>
                  <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                    <input
                      type="text"
                      value={newOptionText}
                      onChange={(e) => setNewOptionText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          if (newOptionText.trim()) {
                            const opts = editingColumn.options || [];
                            setEditingColumn({
                              ...editingColumn,
                              options: [...opts, newOptionText.trim()]
                            });
                            setNewOptionText('');
                          }
                        }
                      }}
                      placeholder="Type option and click Add..."
                      style={{ flex: 1, padding: '6px 10px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)', color: 'var(--c-text)', fontSize: 12.5 }}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        if (newOptionText.trim()) {
                          const opts = editingColumn.options || [];
                          setEditingColumn({
                            ...editingColumn,
                            options: [...opts, newOptionText.trim()]
                          });
                          setNewOptionText('');
                        }
                      }}
                      style={{ padding: '6px 12px', borderRadius: 8, background: '#3b82f6', color: '#fff', border: 'none', fontWeight: 600, fontSize: 12, cursor: 'pointer' }}
                    >
                      Add
                    </button>
                  </div>

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
                    {(editingColumn.options || []).length === 0 ? (
                      <span style={{ fontSize: 11, color: 'var(--c-sidebar-muted)' }}>No options added yet.</span>
                    ) : (
                      (editingColumn.options || []).map((opt, oidx) => (
                        <div
                          key={oidx}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 6,
                            padding: '4px 8px', borderRadius: 6, background: 'var(--c-sidebar-icon-bg)',
                            border: '1px solid var(--c-sidebar-icon-border)', fontSize: 11, fontWeight: 600
                          }}
                        >
                          <span>{opt}</span>
                          <button
                            type="button"
                            onClick={() => {
                              const opts = [...(editingColumn.options || [])];
                              opts.splice(oidx, 1);
                              setEditingColumn({ ...editingColumn, options: opts });
                            }}
                            style={{ background: 'transparent', border: 'none', color: '#ef4444', padding: 0, fontSize: 10, cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                          >
                            ✕
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {editingColumn.type === 'formula' && (
                <div>
                  <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Formula Expression (use column names)</label>
                  <input
                    type="text"
                    value={editingColumn.formulaExpr}
                    onChange={(e) => setEditingColumn({ ...editingColumn, formulaExpr: e.target.value })}
                    placeholder="Amount Sanctioned + Overhead Received"
                    style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)', color: 'var(--c-text)', marginTop: 4 }}
                  />
                </div>
              )}

              {(editingColumn.type === 'number' || editingColumn.type === 'formula') && (
                <>
                  <div style={{ display: 'flex', gap: 12 }}>
                    <div style={{ flex: 1 }}>
                      <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Min Value Limit</label>
                      <input
                        type="number"
                        value={editingColumn.minVal === undefined ? 0 : editingColumn.minVal}
                        onChange={(e) => setEditingColumn({ ...editingColumn, minVal: e.target.value })}
                        placeholder="e.g. 0"
                        style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)', color: 'var(--c-text)', marginTop: 4 }}
                      />
                    </div>
                    <div style={{ flex: 1 }}>
                      <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Max Marks Limit</label>
                      <input
                        type="number"
                        value={editingColumn.maxMarks}
                        onChange={(e) => setEditingColumn({ ...editingColumn, maxMarks: e.target.value })}
                        placeholder="e.g. 50"
                        style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)', color: 'var(--c-text)', marginTop: 4 }}
                      />
                    </div>
                  </div>
                  <div>
                    <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Aggregate Calculation Column Total</label>
                    <select
                      value={editingColumn.aggregate}
                      onChange={(e) => setEditingColumn({ ...editingColumn, aggregate: e.target.value })}
                      style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)', color: 'var(--c-text)', marginTop: 4 }}
                    >
                      <option value="none">None (No aggregate)</option>
                      <option value="sum">Sum / Total Addition</option>
                      <option value="avg">Average Value</option>
                      <option value="max">Maximum Value</option>
                      <option value="min">Minimum Value</option>
                    </select>
                  </div>
                </>
              )}

              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}
                >Column Width (px) — leave blank for auto</label>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 4 }}>
                  <input
                    type="range"
                    min={60}
                    max={400}
                    step={10}
                    value={editingColumn.width ? parseInt(editingColumn.width) : 120}
                    onChange={(e) => setEditingColumn({ ...editingColumn, width: e.target.value + 'px' })}
                    style={{ flex: 1 }}
                  />
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--c-text)', minWidth: 40 }}>
                    {editingColumn.width || 'auto'}
                  </span>
                  <button
                    type="button"
                    onClick={() => setEditingColumn({ ...editingColumn, width: '' })}
                    style={{ padding: '4px 8px', borderRadius: 6, background: 'var(--c-sidebar-icon-bg)', border: '1px solid var(--c-sidebar-icon-border)', color: 'var(--c-sidebar-muted)', cursor: 'pointer', fontSize: 11 }}
                  >
                    Reset
                  </button>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 24, gap: 12 }}>
              {editingColumn.colIdx !== -1 ? (
                <button
                  onClick={() => {
                    removeTableColumn(editingColumn.fieldId, editingColumn.colIdx);
                    setEditingColumn(null);
                  }}
                  style={{ padding: '8px 12px', borderRadius: 8, background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.2)', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}
                >
                  🗑️ Delete
                </button>
              ) : <div />}

              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={() => setEditingColumn(null)}
                  style={{ padding: '8px 12px', borderRadius: 8, background: 'var(--c-sidebar-icon-bg)', border: '1px solid var(--c-sidebar-icon-border)', color: 'var(--c-sidebar-muted)', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    if (editingColumn.colIdx === -1) {
                      // Add column
                      setSchoolForms({
                        ...schoolForms,
                        [selectedSchool]: currentFields.map(f => {
                          if (f.id === editingColumn.fieldId) {
                            const cols = f.columns || [];
                            const newCol = {
                              name: editingColumn.name || `Column ${cols.length + 1}`,
                              type: editingColumn.type,
                              options: editingColumn.options,
                              formulaExpr: editingColumn.formulaExpr,
                              maxMarks: editingColumn.maxMarks ? Number(editingColumn.maxMarks) : undefined,
                              minVal: editingColumn.minVal !== '' ? Number(editingColumn.minVal) : 0,
                              aggregate: editingColumn.aggregate || 'none',
                              width: editingColumn.width || undefined,
                              prefilled: editingColumn.prefilled || false,
                              prefilledValues: editingColumn.prefilled ? (editingColumn.prefilledValues || []) : undefined
                            };
                            return { ...f, columns: [...cols, newCol] };
                          }
                          return f;
                        })
                      });
                    } else {
                      // Update column
                      setSchoolForms({
                        ...schoolForms,
                        [selectedSchool]: currentFields.map(f => {
                          if (f.id === editingColumn.fieldId) {
                            const cols = [...(f.columns || [])];
                            cols[editingColumn.colIdx] = {
                              name: editingColumn.name,
                              type: editingColumn.type,
                              options: editingColumn.options,
                              formulaExpr: editingColumn.formulaExpr,
                              maxMarks: editingColumn.maxMarks ? Number(editingColumn.maxMarks) : undefined,
                              minVal: editingColumn.minVal !== '' ? Number(editingColumn.minVal) : 0,
                              aggregate: editingColumn.aggregate || 'none',
                              width: editingColumn.width || undefined,
                              prefilled: editingColumn.prefilled || false,
                              prefilledValues: editingColumn.prefilled ? (editingColumn.prefilledValues || []) : undefined
                            };
                            return { ...f, columns: cols };
                          }
                          return f;
                        })
                      });
                    }
                    setEditingColumn(null);
                  }}
                  style={{ padding: '8px 16px', borderRadius: 8, background: '#3b82f6', color: '#fff', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}
                >
                  Save Changes
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
