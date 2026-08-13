import { useState } from 'react';
import { useSandbox, DEFAULT_ROLES } from './SandboxContext';
import Card from '../../../components/Card';

// ─── Colour palette for quick pick ────────────────────────────────────────────
const COLOR_PALETTE = [
  '#1d4ed8', '#7c3aed', '#0891b2', '#059669', '#b45309',
  '#dc2626', '#db2777', '#65a30d', '#0369a1', '#6d28d9',
  '#92400e', '#374151',
];

// ─── Small helpers ─────────────────────────────────────────────────────────────
const slugify = (s) => s.toLowerCase().replace(/[^a-z0-9]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');

function HierarchyArrow({ color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height: 28, justifyContent: 'center' }}>
      <div style={{ width: 2, flex: 1, background: `${color}60` }} />
      <svg width="12" height="8" viewBox="0 0 12 8" style={{ flexShrink: 0 }}>
        <path d="M6 8 L0 0 L12 0 Z" fill={color} opacity="0.5" />
      </svg>
    </div>
  );
}

// ─── Role card (in the hierarchy list) ─────────────────────────────────────────
function RoleCard({ role, isSelected, isFirst, isLast, onSelect, onMoveUp, onMoveDown, onDelete }) {
  const canDelete = !isFirst; // first role (submitter) cannot be deleted without replacement

  return (
    <div
      onClick={() => onSelect(role.id)}
      style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px',
        borderRadius: 10, border: `2px solid ${isSelected ? role.color : 'var(--c-sidebar-icon-border)'}`,
        background: isSelected ? `${role.color}10` : 'var(--c-sidebar-icon-bg)',
        cursor: 'pointer', transition: 'all 0.15s ease',
        boxShadow: isSelected ? `0 0 0 1px ${role.color}30` : 'none'
      }}
    >
      {/* Level badge */}
      <div style={{
        width: 32, height: 32, borderRadius: 8, flexShrink: 0,
        background: role.color, color: '#fff', fontWeight: 800, fontSize: 12,
        display: 'flex', alignItems: 'center', justifyContent: 'center'
      }}>
        L{role.level}
      </div>

      {/* Name + description */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--c-text)', display: 'flex', alignItems: 'center', gap: 6 }}>
          {role.name}
          {role.isSubmitter && (
            <span style={{ fontSize: 9.5, fontWeight: 700, color: role.color, background: `${role.color}18`, border: `1px solid ${role.color}30`, padding: '1px 7px', borderRadius: 20, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Submitter
            </span>
          )}
        </div>
        <div style={{ fontSize: 11.5, color: 'var(--c-sidebar-muted)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {role.description || 'No description'}
        </div>
      </div>

      {/* Reorder + delete controls */}
      <div style={{ display: 'flex', gap: 4, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
        <button
          disabled={isFirst}
          onClick={() => onMoveUp(role.id)}
          title="Move up in hierarchy"
          style={{ padding: '4px 7px', borderRadius: 6, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: isFirst ? 'var(--c-sidebar-muted)' : 'var(--c-text)', cursor: isFirst ? 'default' : 'pointer', fontSize: 12 }}>
          ↑
        </button>
        <button
          disabled={isLast}
          onClick={() => onMoveDown(role.id)}
          title="Move down in hierarchy"
          style={{ padding: '4px 7px', borderRadius: 6, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: isLast ? 'var(--c-sidebar-muted)' : 'var(--c-text)', cursor: isLast ? 'default' : 'pointer', fontSize: 12 }}>
          ↓
        </button>
        {canDelete && (
          <button
            onClick={() => onDelete(role.id)}
            title="Remove role"
            style={{ padding: '4px 7px', borderRadius: 6, border: '1px solid rgba(239,68,68,0.2)', background: 'rgba(239,68,68,0.06)', color: '#ef4444', cursor: 'pointer', fontSize: 12 }}>
            ✕
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Role property editor panel ───────────────────────────────────────────────
function RoleEditor({ role, roles, onChange, onClose }) {
  const [draft, setDraft] = useState({ ...role });
  const set = (k, v) => setDraft(d => ({ ...d, [k]: v }));

  const handleSave = () => {
    // Auto-derive key from name if key wasn't manually set
    const saved = { ...draft, key: draft.key || slugify(draft.name) };
    onChange(saved);
    onClose();
  };

  const nameConflict = roles.some(r => r.id !== draft.id && slugify(r.name) === slugify(draft.name));

  return (
    <div style={{
      background: 'var(--c-sidebar-icon-bg)', borderRadius: 14,
      border: `2px solid ${draft.color}40`, padding: 22, display: 'flex', flexDirection: 'column', gap: 14
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: 'var(--c-text)' }}>Edit Role</h3>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--c-sidebar-muted)', cursor: 'pointer', fontSize: 16 }}>✕</button>
      </div>

      {/* Name */}
      <div>
        <label style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--c-sidebar-muted)', display: 'block', marginBottom: 5 }}>Role Name</label>
        <input
          value={draft.name}
          onChange={e => { set('name', e.target.value); set('key', slugify(e.target.value)); }}
          style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: `1px solid ${nameConflict ? '#ef4444' : 'var(--c-sidebar-icon-border)'}`, background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13, boxSizing: 'border-box' }}
          placeholder="e.g. Principal Investigator"
        />
        {nameConflict && <div style={{ fontSize: 11, color: '#ef4444', marginTop: 3 }}>Another role with this name already exists</div>}
      </div>

      {/* Internal key (auto-derived, editable) */}
      <div>
        <label style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--c-sidebar-muted)', display: 'block', marginBottom: 5 }}>
          Internal Key <span style={{ fontWeight: 500, color: 'var(--c-sidebar-muted)' }}>(used in form field ownership)</span>
        </label>
        <input
          value={draft.key}
          onChange={e => set('key', slugify(e.target.value))}
          style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13, fontFamily: 'monospace', boxSizing: 'border-box' }}
          placeholder="e.g. principal_investigator"
        />
      </div>

      {/* Description */}
      <div>
        <label style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--c-sidebar-muted)', display: 'block', marginBottom: 5 }}>Description</label>
        <textarea
          value={draft.description || ''}
          onChange={e => set('description', e.target.value)}
          rows={2}
          style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13, resize: 'vertical', boxSizing: 'border-box', fontFamily: 'inherit' }}
          placeholder="Brief description of this role's responsibility"
        />
      </div>

      {/* Submitter toggle */}
      <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={draft.isSubmitter || false}
          onChange={e => set('isSubmitter', e.target.checked)}
          style={{ marginTop: 2, width: 16, height: 16 }}
        />
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--c-text)' }}>Form Submitter</div>
          <div style={{ fontSize: 11.5, color: 'var(--c-sidebar-muted)', marginTop: 2 }}>This role fills out and submits the appraisal form. All other roles are reviewers/approvers.</div>
        </div>
      </label>

      {/* Colour picker */}
      <div>
        <label style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--c-sidebar-muted)', display: 'block', marginBottom: 8 }}>Accent Colour</label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
          {COLOR_PALETTE.map(c => (
            <button
              key={c}
              onClick={() => set('color', c)}
              title={c}
              style={{
                width: 26, height: 26, borderRadius: 6, background: c, border: `3px solid ${draft.color === c ? '#fff' : 'transparent'}`,
                outline: draft.color === c ? `2px solid ${c}` : 'none',
                cursor: 'pointer', transition: 'all 0.1s ease', flexShrink: 0
              }}
            />
          ))}
        </div>
        <input
          type="color"
          value={draft.color}
          onChange={e => set('color', e.target.value)}
          style={{ height: 32, width: 60, padding: 2, borderRadius: 6, border: '1px solid var(--c-sidebar-icon-border)', cursor: 'pointer' }}
          title="Custom colour"
        />
      </div>

      {/* Save/cancel */}
      <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', paddingTop: 4, borderTop: '1px solid var(--c-sidebar-icon-border)' }}>
        <button onClick={onClose} style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-sidebar-muted)', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={!draft.name.trim() || nameConflict}
          style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: nameConflict || !draft.name.trim() ? '#94a3b8' : draft.color, color: '#fff', fontWeight: 700, fontSize: 13, cursor: nameConflict || !draft.name.trim() ? 'not-allowed' : 'pointer' }}>
          Save Role
        </button>
      </div>
    </div>
  );
}

// ─── Main Tab ─────────────────────────────────────────────────────────────────
export default function RolesTab() {
  const { sandboxRoles, setSandboxRoles } = useSandbox();
  const [selectedId, setSelectedId] = useState(null);

  const sorted = [...sandboxRoles].sort((a, b) => a.level - b.level);
  const selectedRole = sorted.find(r => r.id === selectedId);

  // ── Mutations ──
  const moveRole = (id, direction) => {
    const idx = sorted.findIndex(r => r.id === id);
    const nextIdx = idx + direction;
    if (nextIdx < 0 || nextIdx >= sorted.length) return;
    const next = sorted.map(r => ({ ...r }));
    const aLevel = next[idx].level;
    const bLevel = next[nextIdx].level;
    next[idx].level = bLevel;
    next[nextIdx].level = aLevel;
    setSandboxRoles(next);
  };

  const deleteRole = (id) => {
    if (sorted.length <= 1) return;
    const remaining = sandboxRoles.filter(r => r.id !== id);
    // Re-number levels
    const resort = [...remaining].sort((a, b) => a.level - b.level).map((r, i) => ({ ...r, level: i + 1 }));
    setSandboxRoles(resort);
    if (selectedId === id) setSelectedId(null);
  };

  const updateRole = (updated) => {
    setSandboxRoles(sandboxRoles.map(r => r.id === updated.id ? updated : r));
    setSelectedId(null);
  };

  const addRole = () => {
    const maxLevel = Math.max(...sorted.map(r => r.level), 0);
    const newRole = {
      id: `role_${Date.now()}`,
      name: `New Role ${sandboxRoles.length + 1}`,
      key: `new_role_${sandboxRoles.length + 1}`,
      level: maxLevel + 1,
      color: COLOR_PALETTE[sandboxRoles.length % COLOR_PALETTE.length],
      description: '',
      isSubmitter: false
    };
    setSandboxRoles([...sandboxRoles, newRole]);
    setSelectedId(newRole.id);
  };

  const resetToDefaults = () => {
    if (window.confirm('Reset all roles to the default 5-role hierarchy? This cannot be undone.')) {
      setSandboxRoles(DEFAULT_ROLES);
      setSelectedId(null);
    }
  };

  return (
    <div style={{ width: '100%' }}>
      <Card
        title="User Roles & Hierarchy"
        description="Define the roles involved in the appraisal workflow. The order below represents the approval hierarchy — from the submitter at the top down to the final approver."
      >
        <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>

          {/* ── Left: Hierarchy list ── */}
          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Toolbar */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--c-sidebar-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                {sorted.length} Role{sorted.length !== 1 ? 's' : ''} in Hierarchy
              </span>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={resetToDefaults}
                  style={{ padding: '6px 12px', borderRadius: 7, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-sidebar-muted)', fontSize: 11.5, fontWeight: 600, cursor: 'pointer' }}>
                  Reset to defaults
                </button>
                <button
                  onClick={addRole}
                  style={{ padding: '6px 14px', borderRadius: 7, border: 'none', background: '#3b82f6', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}>
                  ➕ Add Role
                </button>
              </div>
            </div>

            {/* Hierarchy chain */}
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {sorted.map((role, i) => (
                <div key={role.id}>
                  <RoleCard
                    role={role}
                    isSelected={selectedId === role.id}
                    isFirst={i === 0}
                    isLast={i === sorted.length - 1}
                    onSelect={id => setSelectedId(prev => prev === id ? null : id)}
                    onMoveUp={id => moveRole(id, -1)}
                    onMoveDown={id => moveRole(id, 1)}
                    onDelete={deleteRole}
                  />
                  {i < sorted.length - 1 && <HierarchyArrow color={role.color} />}
                </div>
              ))}
            </div>

            {/* Info about impact */}
            <div style={{ marginTop: 20, padding: '12px 16px', borderRadius: 10, background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.15)', fontSize: 12, color: 'var(--c-sidebar-muted)', lineHeight: 1.6 }}>
              <strong style={{ color: '#3b82f6' }}>💡 How roles connect to the rest of the sandbox:</strong><br />
              • <strong>Form Canvas</strong> — the "Owner" dropdown for each field will show your custom roles<br />
              • <strong>Sample Demo</strong> — the workflow progression uses this exact role chain<br />
              • <strong>Hierarchy Simulator</strong> — approval stages follow this order
            </div>
          </div>

          {/* ── Right: Editor panel ── */}
          <div style={{ width: 340, flexShrink: 0 }}>
            {selectedRole ? (
              <RoleEditor
                key={selectedRole.id}
                role={selectedRole}
                roles={sorted}
                onChange={updateRole}
                onClose={() => setSelectedId(null)}
              />
            ) : (
              <div style={{
                background: 'var(--c-sidebar-icon-bg)', borderRadius: 14, border: '1px dashed var(--c-sidebar-icon-border)',
                padding: '40px 24px', textAlign: 'center', color: 'var(--c-sidebar-muted)'
              }}>
                <div style={{ fontSize: 32, marginBottom: 12 }}>👈</div>
                <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 6 }}>Select a role to edit</div>
                <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                  Click any role in the hierarchy to edit its name, description, colour, and submitter flag.
                </div>
              </div>
            )}

            {/* Visual legend */}
            <div style={{ marginTop: 16, background: 'var(--c-sidebar-icon-bg)', borderRadius: 12, border: '1px solid var(--c-sidebar-icon-border)', padding: '14px 16px' }}>
              <div style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--c-sidebar-muted)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 0.4 }}>
                Colour Preview
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {sorted.map((role, i) => (
                  <div key={role.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: role.color, flexShrink: 0 }} />
                    <span style={{ fontSize: 12, color: 'var(--c-text)', fontWeight: 600 }}>{role.name}</span>
                    <span style={{ fontSize: 10.5, color: 'var(--c-sidebar-muted)', marginLeft: 'auto' }}>L{role.level}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
