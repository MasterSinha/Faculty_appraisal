import { SandboxProvider, useSandbox } from './SandboxContext';
import FormBuilderTab from './FormBuilderTab';
import ReportingLinesTab from './ReportingLinesTab';
import WorkflowSimulatorTab from './WorkflowSimulatorTab';
import DeploymentExportTab from './DeploymentExportTab';
import PageHead from '../../../components/PageHead';

function SandboxInner() {
  const {
    activeTab, setActiveTab,
    selectedSchool, setSelectedSchool,
    setSimActiveStep,
    setSimRunning,
    setSimLogs,
    cloneFromSchool
  } = useSandbox();

  return (
    <div style={{ padding: 24, minHeight: 'calc(100vh - 80px)', background: 'var(--c-bg)' }}>
      <PageHead 
        title="Experimental Sandbox Engine" 
        subtitle="Full sandbox playground to model custom forms, configure spreadsheet columns/formulas, establish reporting lines, and view deployment scripts."
      />

      {/* Selector and tab bar header */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center',
        padding: '16px 20px', borderRadius: 16, background: 'var(--c-sidebar-icon-bg)',
        border: '1px solid var(--c-sidebar-icon-border)', marginBottom: 24, gap: 16
      }}>
        {/* Navigation Tabs */}
        <div style={{ display: 'flex', gap: 6, padding: 4, borderRadius: 10, background: 'var(--c-bg)', border: '1px solid var(--c-sidebar-icon-border)' }}>
          <button
            onClick={() => setActiveTab('form-builder')}
            style={{
              padding: '8px 16px', borderRadius: 8, cursor: 'pointer', border: 'none', fontWeight: 600,
              background: activeTab === 'form-builder' ? '#3b82f6' : 'transparent',
              color: activeTab === 'form-builder' ? '#ffffff' : 'var(--c-sidebar-muted)'
            }}
          >
            Form Canvas
          </button>
          <button
            onClick={() => setActiveTab('reporting-lines')}
            style={{
              padding: '8px 16px', borderRadius: 8, cursor: 'pointer', border: 'none', fontWeight: 600,
              background: activeTab === 'reporting-lines' ? '#3b82f6' : 'transparent',
              color: activeTab === 'reporting-lines' ? '#ffffff' : 'var(--c-sidebar-muted)'
            }}
          >
            Reporting Mappings
          </button>
          <button
            onClick={() => setActiveTab('workflow-sim')}
            style={{
              padding: '8px 16px', borderRadius: 8, cursor: 'pointer', border: 'none', fontWeight: 600,
              background: activeTab === 'workflow-sim' ? '#3b82f6' : 'transparent',
              color: activeTab === 'workflow-sim' ? '#ffffff' : 'var(--c-sidebar-muted)'
            }}
          >
            Hierarchy Simulator
          </button>
          <button
            onClick={() => setActiveTab('deploy-export')}
            style={{
              padding: '8px 16px', borderRadius: 8, cursor: 'pointer', border: 'none', fontWeight: 600,
              background: activeTab === 'deploy-export' ? '#3b82f6' : 'transparent',
              color: activeTab === 'deploy-export' ? '#ffffff' : 'var(--c-sidebar-muted)'
            }}
          >
            Deploy & Export
          </button>
        </div>

        {/* Dynamic clone layout from target school */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ display: 'flex', gap: 6, marginRight: 12 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--c-sidebar-muted)', marginTop: 8 }}>Clone from:</span>
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

      {/* Render Active Tab */}
      {activeTab === 'form-builder' && <FormBuilderTab />}
      {activeTab === 'reporting-lines' && <ReportingLinesTab />}
      {activeTab === 'workflow-sim' && <WorkflowSimulatorTab />}
      {activeTab === 'deploy-export' && <DeploymentExportTab />}
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
