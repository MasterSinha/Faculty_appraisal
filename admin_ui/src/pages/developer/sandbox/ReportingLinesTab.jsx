import { useSandbox } from './SandboxContext';
import Card from '../../../components/Card';

export default function ReportingLinesTab() {
  const {
    mockFaculty, setMockFaculty,
    mockHods
  } = useSandbox();

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
      {/* Target Mapping Editor */}
      <Card title="1. Configure User Reporting Connections" description="Establish customized HOD connections for individual faculty accounts.">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {mockFaculty.map((faculty, fidx) => (
            <div 
              key={faculty.email} 
              style={{
                padding: 16, borderRadius: 12, border: '1px solid var(--c-sidebar-icon-border)',
                background: 'var(--c-sidebar-icon-bg)'
              }}
            >
              <h4 style={{ margin: '0 0 8px 0', color: 'var(--c-sidebar-text)' }}>{faculty.name}</h4>
              <span style={{ fontSize: 11, color: 'var(--c-sidebar-muted)' }}>Email: {faculty.email}</span>
              
              <div style={{ marginTop: 12 }}>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Assign Target HOD:</label>
                <select
                  value={faculty.assignedHod}
                  onChange={(e) => {
                    const updated = [...mockFaculty];
                    updated[fidx].assignedHod = e.target.value;
                    setMockFaculty(updated);
                  }}
                  style={{
                    width: '100%', padding: '6px 10px', borderRadius: 8,
                    border: '1px solid var(--c-sidebar-icon-border)',
                    background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13, marginTop: 4
                  }}
                >
                  {mockHods.map(hod => (
                    <option key={hod.email} value={hod.email}>{hod.name} ({hod.email})</option>
                  ))}
                </select>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Visual Reporting Network Preview */}
      <Card title="2. Reporting Topology Preview" description="Visual structure of custom hierarchy links.">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 16, background: 'var(--c-sidebar-icon-bg)', borderRadius: 12, border: '1px solid var(--c-sidebar-icon-border)' }}>
          {mockFaculty.map(faculty => {
            const myHod = mockHods.find(h => h.email === faculty.assignedHod);
            return (
              <div 
                key={faculty.email}
                style={{ 
                  display: 'flex', alignItems: 'center', gap: 16, padding: 12, 
                  borderRadius: 8, background: 'var(--c-bg)', border: '1px solid var(--c-sidebar-icon-border)' 
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 12 }}>{faculty.name}</div>
                  <div style={{ fontSize: 10, color: 'var(--c-sidebar-muted)' }}>Faculty</div>
                </div>
                <div style={{ fontSize: 14, color: '#3b82f6', fontWeight: 800 }}>➔ reports to ➔</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 12, color: '#3b82f6' }}>{myHod?.name}</div>
                  <div style={{ fontSize: 10, color: 'var(--c-sidebar-muted)' }}>Target Reviewer HOD</div>
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
