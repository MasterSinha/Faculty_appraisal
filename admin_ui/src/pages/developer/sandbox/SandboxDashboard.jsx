import { SandboxProvider, useSandbox } from './SandboxContext';
import FormBuilderTab from './FormBuilderTab';
import ReportingLinesTab from './ReportingLinesTab';
import WorkflowSimulatorTab from './WorkflowSimulatorTab';
import DeploymentExportTab from './DeploymentExportTab';
import SampleDemoTab from './SampleDemoTab';
import PageHead from '../../../components/PageHead';
import { useParams, useNavigate } from 'react-router-dom';
import { useEffect } from 'react';

function SandboxInner() {
  const {
    activeTab, setActiveTab,
    selectedSchool, setSelectedSchool,
    setSimActiveStep,
    setSimRunning,
    setSimLogs,
    cloneFromSchool
  } = useSandbox();

  const { tab } = useParams();
  const navigate = useNavigate();

  // Sync active tab state with Route URL parameter
  useEffect(() => {
    if (tab && tab !== activeTab) {
      setActiveTab(tab);
    } else if (!tab) {
      navigate('/developer/sandbox/form-builder', { replace: true });
    }
  }, [tab, activeTab, setActiveTab, navigate]);

  const isSampleDemo = activeTab === 'sample-demo';

  return (
    <div style={{ padding: isSampleDemo ? 0 : 24, minHeight: 'calc(100vh - 80px)', background: isSampleDemo ? 'transparent' : 'var(--c-bg)' }}>
      {!isSampleDemo && (
        <>
          <PageHead 
            title="Experimental Sandbox Engine" 
            subtitle="Full sandbox playground to model custom forms, configure spreadsheet columns/formulas, establish reporting lines, and view deployment scripts."
          />

          {/* School selector + clone controls — no tab bar (navigation is via sidebar) */}
          <div style={{
            display: 'flex', flexWrap: 'wrap', justifyContent: 'flex-end', alignItems: 'center',
            padding: '14px 20px', borderRadius: 16, background: 'var(--c-sidebar-icon-bg)',
            border: '1px solid var(--c-sidebar-icon-border)', marginBottom: 24, gap: 16
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ display: 'flex', gap: 6, marginRight: 12 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--c-sidebar-muted)', lineHeight: '32px' }}>Clone from:</span>
                <button
                  onClick={() => cloneFromSchool('SoCSEA')}
                  style={{ padding: '4px 8px', borderRadius: 6, background: '#3b82f612', border: '1px solid #3b82f625', color: '#3b82f6', fontSize: 11, cursor: 'pointer' }}
                >
                  SoCSEA
                </button>
                <button
                  onClick={() => cloneFromSchool('SoD')}
                  style={{ padding: '4px 8px', borderRadius: 6, background: '#a78bfa12', border: '1px solid #a78bfa25', color: '#a78bfa', fontSize: 11, cursor: 'pointer' }}
                >
                  SoD
                </button>
              </div>

              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Configure School:</span>
              <select
                value={selectedSchool}
                onChange={(e) => {
                  setSelectedSchool(e.target.value);
                  setSimActiveStep(0);
                  setSimRunning(false);
                  setSimLogs([]);
                }}
                style={{
                  padding: '8px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)',
                  background: 'var(--c-bg)', color: 'var(--c-text)', fontWeight: 600
                }}
              >
                <option value="SoCSEA">Engineering (SoCSEA)</option>
                <option value="SoD">Creative (SoD)</option>
                <option value="Custom">Custom Blank Canvas</option>
              </select>
            </div>
          </div>
        </>
      )}

      {/* Render Active Tab */}
      {activeTab === 'form-builder'    && <FormBuilderTab />}
      {activeTab === 'reporting-lines' && <ReportingLinesTab />}
      {activeTab === 'workflow-sim'    && <WorkflowSimulatorTab />}
      {activeTab === 'deploy-export'   && <DeploymentExportTab />}
      {activeTab === 'sample-demo'     && <SampleDemoTab />}
    </div>
  );
}

export default function SandboxDashboard() {
  return (
    <SandboxProvider>
      <SandboxInner />
    </SandboxProvider>
  );
}
