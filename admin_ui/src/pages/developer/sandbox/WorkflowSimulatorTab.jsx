import { useSandbox } from './SandboxContext';
import Card from '../../../components/Card';
import { I } from '../../../components/icons';
import { pBtn } from '../../../constants/styleTokens';
import { MOCK_WORKFLOW_STEPS } from './schemaTemplates';

export default function WorkflowSimulatorTab() {
  const {
    currentWorkflow,
    selectedSchool,
    updateWorkflowStepLabel,
    moveWorkflowStep,
    deleteWorkflowStep,
    addWorkflowStep,
    selectedFacultySim, setSelectedFacultySim,
    simRunning, setSimRunning,
    setSimActiveStep,
    setSimLogs,
    mockFaculty,
    simActiveStep,
    mockHods,
    simLogs,
    startSimulation,
    advanceSimulation
  } = useSandbox();

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
      {/* Custom Workflow Builder */}
      <Card title="1. Configure Hierarchy Steps" description={`Approval workflow chain for School: ${selectedSchool}.`}>
        <div style={{ maxHeight: '60vh', overflowY: 'auto' }}>
          {currentWorkflow.map((step, idx) => (
            <div
              key={step.id}
              style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: 12, borderRadius: 12, border: '1px solid var(--c-sidebar-icon-border)',
                background: 'var(--c-sidebar-icon-bg)', marginBottom: 12
              }}
            >
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--c-sidebar-muted)', width: 24 }}>
                {idx + 1}
              </div>

              <div style={{ flex: 1 }}>
                <input
                  type="text"
                  value={step.label}
                  onChange={(e) => updateWorkflowStepLabel(step.id, e.target.value)}
                  style={{
                    width: '90%', padding: '6px 10px', borderRadius: 8,
                    border: '1px solid var(--c-sidebar-icon-border)',
                    background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13, fontWeight: 600
                  }}
                />
              </div>

              <div style={{ display: 'flex', gap: 4 }}>
                <button
                  onClick={() => moveWorkflowStep(idx, -1)}
                  disabled={idx === 0}
                  style={{ padding: 6, borderRadius: 6, cursor: 'pointer', background: 'var(--c-bg)', border: 'none', color: 'var(--c-text)' }}
                >
                  ▲
                </button>
                <button
                  onClick={() => moveWorkflowStep(idx, 1)}
                  disabled={idx === currentWorkflow.length - 1}
                  style={{ padding: 6, borderRadius: 6, cursor: 'pointer', background: 'var(--c-bg)', border: 'none', color: 'var(--c-text)' }}
                >
                  ▼
                </button>
                <button
                  onClick={() => deleteWorkflowStep(step.id)}
                  style={{ padding: 6, borderRadius: 6, cursor: 'pointer', background: 'var(--c-bg)', border: 'none', color: '#ef4444' }}
                >
                  <I.trash size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>

        <button
          onClick={addWorkflowStep}
          style={{
            width: '100%', padding: 10, borderRadius: 10, border: '1px dashed #3b82f6', color: '#3b82f6',
            background: 'transparent', cursor: 'pointer', fontWeight: 600, marginTop: 12,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8
          }}
        >
          <I.addUser size={14} /> Add Review Step
        </button>
      </Card>

      {/* Interactive Routing Chain Visualizer */}
      <Card title="2. Workflow Path Simulator" description="Choose a faculty member to initiate and test personalized reporting flows.">
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Initiate Submission as Faculty:</label>
          <select
            value={selectedFacultySim}
            onChange={(e) => {
              setSelectedFacultySim(e.target.value);
              setSimRunning(false);
              setSimActiveStep(0);
              setSimLogs([]);
            }}
            disabled={simRunning}
            style={{
              width: '100%', padding: '8px 12px', borderRadius: 8,
              border: '1px solid var(--c-sidebar-icon-border)',
              background: 'var(--c-bg)', color: 'var(--c-text)', fontWeight: 600
            }}
          >
            {mockFaculty.map(f => (
              <option key={f.email} value={f.email}>{f.name} ({f.email})</option>
            ))}
          </select>
        </div>

        {/* Visual Flow chart */}
        <div style={{
          display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', justifyContent: 'center',
          padding: 16, background: 'var(--c-sidebar-icon-bg)', borderRadius: 12,
          border: '1px solid var(--c-sidebar-icon-border)', marginBottom: 20
        }}>
          {currentWorkflow.map((step, idx) => {
            const isActive = simActiveStep === idx && simRunning;
            const isCompleted = simActiveStep > idx && simRunning;
            
            // Map step labels to concrete users
            const facultyUser = mockFaculty.find(f => f.email === selectedFacultySim);
            const hodUser = facultyUser ? mockHods.find(h => h.email === facultyUser.assignedHod) : null;
            let displayLabel = step.label;
            if (step.label.toLowerCase().includes('hod') && hodUser) {
              displayLabel = `${step.label} (${hodUser.name})`;
            }

            return (
              <div key={step.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{
                  padding: '8px 14px', borderRadius: 10, fontSize: 11.5, fontWeight: 700,
                  background: isActive ? '#3b82f6' : isCompleted ? '#10b98115' : 'var(--c-bg)',
                  border: `1.5px solid ${isActive ? '#3b82f6' : isCompleted ? '#10b981' : 'var(--c-sidebar-icon-border)'}`,
                  color: isActive ? '#fff' : isCompleted ? '#10b981' : 'var(--c-sidebar-muted)',
                  boxShadow: isActive ? '0 0 12px rgba(59,130,246,0.3)' : 'none'
                }}>
                  {displayLabel}
                </div>
                {idx < currentWorkflow.length - 1 && (
                  <span style={{ fontSize: 14, color: 'var(--c-sidebar-muted)' }}>➔</span>
                )}
              </div>
            );
          })}
        </div>

        {/* Simulator controls console */}
        <div style={{ borderTop: '1px solid var(--c-sidebar-icon-border)', paddingTop: 16 }}>
          {!simRunning ? (
            <button
              onClick={startSimulation}
              className={pBtn}
              style={{ width: '100%', padding: '10px 14px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
            >
              🚀 Start Simulation Run
            </button>
          ) : (
            <div>
              <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
                <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: '#3b82f6', background: 'rgba(59,130,246,0.1)', padding: '2px 8px', borderRadius: 4 }}>
                  Active Step {simActiveStep + 1}: {currentWorkflow[simActiveStep]?.label}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <button
                  onClick={() => advanceSimulation(true)}
                  style={{
                    padding: 10, borderRadius: 8, border: 'none', background: '#10b981', color: '#fff',
                    fontWeight: 600, fontSize: 13, cursor: 'pointer'
                  }}
                >
                  ✅ Approve Step
                </button>
                <button
                  onClick={() => advanceSimulation(false)}
                  style={{
                    padding: 10, borderRadius: 8, border: 'none', background: '#ef4444', color: '#fff',
                    fontWeight: 600, fontSize: 13, cursor: 'pointer'
                  }}
                >
                  ❌ Reject (Backtrack)
                </button>
              </div>
            </div>
          )}

          {/* Console logging display */}
          <div style={{ marginTop: 16 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--c-sidebar-muted)' }}>Simulation Output Logs:</span>
            <div style={{
              marginTop: 6, height: 160, padding: 12, borderRadius: 8, background: '#0f172a',
              border: '1px solid var(--c-sidebar-icon-border)', color: '#38bdf8',
              fontFamily: 'monospace', fontSize: 11.5, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4
            }}>
              {simLogs.length === 0 ? (
                <span style={{ color: '#64748b' }}>Console idle. Start simulation to inspect logs.</span>
              ) : (
                simLogs.map((log, lidx) => <span key={lidx}>{log}</span>)
              )}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
