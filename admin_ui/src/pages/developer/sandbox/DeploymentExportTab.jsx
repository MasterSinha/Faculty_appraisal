import { useSandbox } from './SandboxContext';
import Card from '../../../components/Card';
import { I } from '../../../components/icons';
import { pBtn } from '../../../constants/styleTokens';
import { getConfigsTemplates } from './schemaTemplates';
import { useRef } from 'react';

export default function DeploymentExportTab() {
  const {
    selectedSchool,
    currentFields,
    selectedConfigType, setSelectedConfigType,
    handleExportSchema,
    handleImportSchema,
    generateSqlAlchemyClasses
  } = useSandbox();

  const fileInputRef = useRef(null);
  const configs = getConfigsTemplates(selectedSchool, currentFields);

  const getCodePreview = () => {
    if (selectedConfigType === 'models') {
      return generateSqlAlchemyClasses();
    }
    return configs[selectedConfigType] || '';
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: 24 }}>
      {/* Configs File Viewer */}
      <Card title="1. Auto-Generated Deployment Configs" description="View custom code snippets generated automatically for the active school configuration.">
        <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
          <button
            onClick={() => setSelectedConfigType('docker')}
            style={{
              padding: '6px 12px', borderRadius: 6, cursor: 'pointer', border: 'none', fontSize: 12, fontWeight: 600,
              background: selectedConfigType === 'docker' ? '#3b82f6' : 'var(--c-sidebar-icon-bg)',
              color: selectedConfigType === 'docker' ? '#fff' : 'var(--c-sidebar-muted)'
            }}
          >
            docker-compose.yml
          </button>
          <button
            onClick={() => setSelectedConfigType('nginx')}
            style={{
              padding: '6px 12px', borderRadius: 6, cursor: 'pointer', border: 'none', fontSize: 12, fontWeight: 600,
              background: selectedConfigType === 'nginx' ? '#3b82f6' : 'var(--c-sidebar-icon-bg)',
              color: selectedConfigType === 'nginx' ? '#fff' : 'var(--c-sidebar-muted)'
            }}
          >
            nginx.conf
          </button>
          <button
            onClick={() => setSelectedConfigType('setup')}
            style={{
              padding: '6px 12px', borderRadius: 6, cursor: 'pointer', border: 'none', fontSize: 12, fontWeight: 600,
              background: selectedConfigType === 'setup' ? '#3b82f6' : 'var(--c-sidebar-icon-bg)',
              color: selectedConfigType === 'setup' ? '#fff' : 'var(--c-sidebar-muted)'
            }}
          >
            deploy.sh
          </button>
          <button
            onClick={() => setSelectedConfigType('models')}
            style={{
              padding: '6px 12px', borderRadius: 6, cursor: 'pointer', border: 'none', fontSize: 12, fontWeight: 600,
              background: selectedConfigType === 'models' ? '#3b82f6' : 'var(--c-sidebar-icon-bg)',
              color: selectedConfigType === 'models' ? '#fff' : 'var(--c-sidebar-muted)'
            }}
          >
            models.py
          </button>
          <button
            onClick={() => setSelectedConfigType('schema')}
            style={{
              padding: '6px 12px', borderRadius: 6, cursor: 'pointer', border: 'none', fontSize: 12, fontWeight: 600,
              background: selectedConfigType === 'schema' ? '#3b82f6' : 'var(--c-sidebar-icon-bg)',
              color: selectedConfigType === 'schema' ? '#fff' : 'var(--c-sidebar-muted)'
            }}
          >
            db_schema.sql
          </button>
          <button
            onClick={() => setSelectedConfigType('routes')}
            style={{
              padding: '6px 12px', borderRadius: 6, cursor: 'pointer', border: 'none', fontSize: 12, fontWeight: 600,
              background: selectedConfigType === 'routes' ? '#3b82f6' : 'var(--c-sidebar-icon-bg)',
              color: selectedConfigType === 'routes' ? '#fff' : 'var(--c-sidebar-muted)'
            }}
          >
            subordinates_route.py
          </button>
        </div>

        <pre style={{
          background: '#0f172a', color: '#e2e8f0', padding: 16, borderRadius: 8,
          fontSize: 12.5, fontFamily: 'monospace', overflow: 'auto', maxHeight: '50vh', margin: 0
        }}>
          <code>{getCodePreview()}</code>
        </pre>
      </Card>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Checklist & Mock Exporter */}
        <Card title="2. Compile Client Bundle" description="Package custom settings and export a clean installation zip.">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{
              padding: 12, borderRadius: 8, background: '#3b82f612', border: '1px solid #3b82f625',
              fontSize: 13, color: 'var(--c-text)', lineHeight: 1.5
            }}>
              <strong>Compilation Mode:</strong> {selectedSchool} App Bundle<br/>
              Includes standard user management, cycle windows, and statistics dashboard. Excludes proprietary sandbox page.
            </div>

            <button
              onClick={() => alert("Mock Exporter Tool:\nCompiling React bundle...\nAssembling PostgreSQL schemas...\nCreating client zip file: 'pbas_college_release.zip'") }
              className={pBtn}
              style={{ width: '100%', padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
            >
              <I.dl size={16} /> Compile & Download Client Zip
            </button>

            <div style={{ borderTop: '1px solid var(--c-sidebar-icon-border)', paddingTop: 12, marginTop: 4 }}>
              <h4 style={{ margin: '0 0 10px 0', fontSize: 13, color: 'var(--c-sidebar-text)' }}>SSH Installation Checklist</h4>
              <ol style={{ paddingLeft: 20, margin: 0, fontSize: 12.5, color: 'var(--c-sidebar-muted)', lineHeight: 1.6 }}>
                <li>Gain SSH login access to client VM.</li>
                <li>Upload and unzip compiled <code>pbas_college_release.zip</code>.</li>
                <li>Run <code>chmod +x deploy.sh</code>.</li>
                <li>Execute setup script <code>./deploy.sh</code> to automatically install Docker, set secrets, and run schema migration tables.</li>
                <li>Configure DNS A record pointing to target VM public IP.</li>
              </ol>
            </div>
          </div>
        </Card>

        {/* Schema Template Import/Export */}
        <Card title="3. Schema Import / Export" description="Save the active form canvas fields config to disk, or import a saved JSON file.">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <button 
              onClick={handleExportSchema}
              style={{ width: '100%', padding: '10px 14px', borderRadius: 8, background: '#3b82f615', border: '1px solid #3b82f630', color: '#3b82f6', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}
            >
              💾 Export Schema JSON
            </button>
            <button 
              onClick={() => fileInputRef.current.click()}
              style={{ width: '100%', padding: '10px 14px', borderRadius: 8, background: '#10b98115', border: '1px solid #10b98130', color: '#10b981', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}
            >
              📂 Import Schema JSON
            </button>
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={handleImportSchema} 
              style={{ display: 'none' }} 
              accept=".json"
            />
          </div>
        </Card>
      </div>
    </div>
  );
}
