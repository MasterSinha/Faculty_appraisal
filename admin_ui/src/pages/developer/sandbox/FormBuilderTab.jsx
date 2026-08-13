import { useSandbox } from './SandboxContext';
import Card from '../../../components/Card';
import { I } from '../../../components/icons';
import { pBtn } from '../../../constants/styleTokens';
import { useRef } from 'react';

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
    addField
  } = useSandbox();

  const fileInputRef = useRef(null);

  const renderFieldPreview = (field) => {
    const isReadOnly = field.role !== simulatedRole || field.access === 'reviewer-edit';
    const isDeselected = disabledSections[field.id];
    
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
                          options: Array.isArray(col.options) ? col.options.join(', ') : (col.options || ''),
                          formulaExpr: col.formulaExpr || ''
                        });
                      }
                    }}
                    style={{
                      padding: 8, textAlign: 'left', fontWeight: 600,
                      color: 'var(--c-sidebar-text)', cursor: 'pointer',
                      borderRight: '1px solid var(--c-sidebar-icon-border)'
                    }}
                    title="Click to edit column properties"
                  >
                    {col.name} {col.type === 'formula' && <span style={{ color: '#10b981', fontSize: 10 }}>(Formula)</span>}
                    ✏️
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
                        formulaExpr: ''
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
                {!isReadOnly && <th style={{ padding: 8, width: 40 }} />}
              </tr>
            </thead>
            <tbody>
              {(previewTables[field.id] || []).map((row, rowIdx) => (
                <tr key={rowIdx} style={{ borderBottom: '1px solid var(--c-sidebar-icon-border)' }}>
                  {(field.columns || []).map((col, cidx) => {
                    const cellVal = col.type === 'formula' ? evaluateCellFormula(col.formulaExpr, row) : (row[col.name] || '');
                    return (
                      <td key={cidx} style={{ padding: 8, color: 'var(--c-text)' }}>
                        {isReadOnly || col.type === 'formula' || isDeselected ? (
                          <span>{String(cellVal)}</span>
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
                            {(col.options || '').split(',').map(o => o.trim()).filter(Boolean).map(o => (
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
                        ) : (
                          <input
                            type={col.type === 'number' ? 'number' : 'text'}
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
                  {!isReadOnly && (
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
              {!isReadOnly && !isDeselected && (
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

    return (
      <input
        type={field.type}
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
                                <div style={{ borderTop: '1px solid var(--c-sidebar-icon-border)', paddingTop: 12, marginTop: 4, display: 'flex', gap: 16 }}>
                                  <div style={{ flex: 1 }}>
                                    <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Table Max Marks</label>
                                    <input
                                      type="number"
                                      value={field.tableMaxMarks}
                                      onChange={(e) => updateField(field.id, 'tableMaxMarks', Number(e.target.value))}
                                      style={{ width: '100%', padding: '6px 10px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12, marginTop: 4 }}
                                    />
                                  </div>
                                  <div style={{ flex: 1 }}>
                                    <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Row Max Marks</label>
                                    <input
                                      type="number"
                                      value={field.rowMaxMarks}
                                      onChange={(e) => updateField(field.id, 'rowMaxMarks', Number(e.target.value))}
                                      style={{ width: '100%', padding: '6px 10px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 12, marginTop: 4 }}
                                    />
                                  </div>
                                  <div style={{ flex: 2 }}>
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
                                </div>
                              )}
                            </div>

                            <div style={{ marginTop: 16, borderTop: '1px dashed var(--c-sidebar-icon-border)', paddingTop: 12 }}>
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
                  <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Dropdown Options (comma-separated)</label>
                  <input
                    type="text"
                    value={editingColumn.options}
                    onChange={(e) => setEditingColumn({ ...editingColumn, options: e.target.value })}
                    placeholder="Ongoing, Completed, Approved"
                    style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)', color: 'var(--c-text)', marginTop: 4 }}
                  />
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
                              formulaExpr: editingColumn.formulaExpr
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
                              formulaExpr: editingColumn.formulaExpr
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
