import { useState } from 'react';
import { C } from '../../constants/colors';
import { api } from '../../api/client';
import { useFetch } from '../../hooks/useFetch';
import { Loading, ApiError } from '../../components/LoadingState';
import Card from '../../components/Card';
import PageHead from '../../components/PageHead';
import Badge from '../../components/Badge';
import { I } from '../../components/icons';
import { logAction } from '../../utils/activityLog';

export default function TransitionPage() {
  const [tick, setTick] = useState(0);
  const { data: configs, loading, error } = useFetch(() => api.cycle.list(), [tick]);
  const allConfigs = Array.isArray(configs) ? configs : [];

  // Delete confirmations state
  const [deletingYear, setDeletingYear] = useState(null);
  const [confirmInput, setConfirmInput] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [msg, setMsg] = useState(null);

  const handleDelete = async (year) => {
    setActionLoading(true);
    setMsg(null);
    try {
      await api.cycle.remove(year);
      setMsg({ ok: true, text: `Successfully deleted academic year configuration: ${year}` });
      logAction('cycle_deleted', 'Delete Cycle', `Deleted cycle config for ${year}`, { year });
      setDeletingYear(null);
      setConfirmInput('');
      setTick(t => t + 1);
    } catch (e) {
      setMsg({ ok: false, text: e.message || 'Failed to delete year configuration.' });
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="page-enter">
      <PageHead title="Manage Academic Years" sub="List, inspect, and delete appraisal cycle configurations" />

      {msg && (
        <div style={{
          marginBottom: 14, padding: '12px 14px', borderRadius: 8, fontSize: 13,
          color: msg.ok ? C.green : C.red,
          background: msg.ok ? 'rgba(52,211,153,.08)' : 'rgba(248,113,113,.08)',
          border: `1px solid ${msg.ok ? 'rgba(52,211,153,.2)' : 'rgba(248,113,113,.2)'}`
        }}>
          {msg.text}
        </div>
      )}

      {loading && <Loading />}
      {error && <ApiError message={error} />}

      {!loading && !error && (
        <div style={{ display: 'grid', gridTemplateColumns: deletingYear ? '1.2fr 1fr' : '1fr', gap: 14 }}>
          
          <Card title="Appraisal Cycles / Configurations">
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--c-row-border)', color: C.muted, fontWeight: 700 }}>
                    <th style={{ padding: '10px 12px', textAlign: 'left' }}>Academic Year</th>
                    <th style={{ padding: '10px 12px', textAlign: 'center' }}>Status</th>
                    <th style={{ padding: '10px 12px', textAlign: 'center' }}>Opens</th>
                    <th style={{ padding: '10px 12px', textAlign: 'center' }}>Closes</th>
                    <th style={{ padding: '10px 12px', textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {allConfigs.length === 0 ? (
                    <tr>
                      <td colSpan="5" style={{ padding: '24px', textAlign: 'center', color: C.muted, fontStyle: 'italic' }}>
                        No academic year configurations found.
                      </td>
                    </tr>
                  ) : (
                    allConfigs.map(c => (
                      <tr key={c.academic_year} style={{ borderBottom: '1px solid var(--c-row-border)', height: 48 }}>
                        <td style={{ padding: '10px 12px', fontWeight: 600, color: C.text }}>
                          {c.academic_year}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                          <Badge color={c.is_open ? 'green' : 'red'}>
                            {c.is_open ? 'Active (Open)' : 'Closed'}
                          </Badge>
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'center', color: C.subtle, fontFamily: "'JetBrains Mono',monospace" }}>
                          {c.submission_start ? new Date(c.submission_start).toLocaleDateString() : '—'}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'center', color: C.subtle, fontFamily: "'JetBrains Mono',monospace" }}>
                          {c.submission_end ? new Date(c.submission_end).toLocaleDateString() : '—'}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                          <button
                            onClick={() => {
                              setDeletingYear(c.academic_year);
                              setConfirmInput('');
                              setMsg(null);
                            }}
                            disabled={actionLoading}
                            style={{
                              background: 'rgba(239, 68, 68, 0.1)',
                              border: '1px solid rgba(239, 68, 68, 0.3)',
                              borderRadius: 6,
                              padding: '5px 10px',
                              color: '#ef4444',
                              fontSize: 12,
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 6,
                              transition: 'opacity 0.15s'
                            }}
                            onMouseEnter={e => e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)'}
                            onMouseLeave={e => e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)'}
                          >
                            <I.trash size={12} />
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          {deletingYear && (
            <Card title={`Confirm Deletion: ${deletingYear}`}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{
                  padding: 12, borderRadius: 8,
                  background: 'rgba(239, 68, 68, 0.08)',
                  border: '1px solid rgba(239, 68, 68, 0.25)',
                  display: 'flex', gap: 8, alignItems: 'flex-start'
                }}>
                  <div style={{ color: '#ef4444', flexShrink: 0, marginTop: 1 }}>
                    <I.shield size={14} />
                  </div>
                  <div style={{ fontSize: 12, color: C.subtle, lineHeight: 1.5 }}>
                    <strong>Warning:</strong> Deleting the academic year configuration <strong>{deletingYear}</strong> will prevent users from logging in or selecting this cycle. Snapshots and submissions for this year will remain in the database, but their configuration will be permanently deleted.
                  </div>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: C.subtle, marginBottom: 6, textTransform: 'uppercase' }}>
                    Type the Academic Year to Confirm
                  </label>
                  <input
                    type="text"
                    value={confirmInput}
                    onChange={e => setConfirmInput(e.target.value)}
                    placeholder={`e.g. ${deletingYear}`}
                    disabled={actionLoading}
                    style={{
                      width: '100%', padding: '10px 12px', borderRadius: 8,
                      background: 'rgba(255,255,255,.03)',
                      border: '1px solid rgba(255,255,255,.08)',
                      color: '#fff', fontFamily: 'inherit', fontSize: 13,
                      outline: 'none', transition: 'border-color .15s',
                    }}
                  />
                </div>

                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    onClick={() => setDeletingYear(null)}
                    disabled={actionLoading}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      flex: 1, padding: '10px 14px', borderRadius: 8,
                      background: 'rgba(255,255,255,.05)', border: 'none',
                      color: C.subtle, cursor: 'pointer', fontSize: 12.5, fontWeight: 600
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => handleDelete(deletingYear)}
                    disabled={actionLoading || confirmInput.trim() !== deletingYear}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                      flex: 2, padding: '10px 14px', borderRadius: 8,
                      background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
                      border: 'none', color: '#fff', cursor: 'pointer',
                      fontSize: 12.5, fontWeight: 600,
                      opacity: (actionLoading || confirmInput.trim() !== deletingYear) ? 0.5 : 1,
                      boxShadow: confirmInput.trim() === deletingYear ? '0 4px 12px rgba(239,68,68,.2)' : 'none'
                    }}
                  >
                    <I.trash size={13} />
                    {actionLoading ? 'Deleting...' : 'Confirm Delete'}
                  </button>
                </div>
              </div>
            </Card>
          )}

        </div>
      )}
    </div>
  );
}
