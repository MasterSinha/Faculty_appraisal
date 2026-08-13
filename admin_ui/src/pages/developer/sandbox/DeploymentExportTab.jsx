import { useSandbox } from './SandboxContext';
import Card from '../../../components/Card';
import { I } from '../../../components/icons';
import { pBtn } from '../../../constants/styleTokens';
import { getConfigsTemplates } from './schemaTemplates';
import { useRef, useState } from 'react';
import JSZip from 'jszip';

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
  const [compiling, setCompiling] = useState(false);

  const handleCompileZip = async () => {
    setCompiling(true);
    try {
      const zip = new JSZip();

      // 1. Add code/configs
      zip.file('docker-compose.yml', configs.docker || '');
      zip.file('nginx.conf', configs.nginx || '');
      zip.file('deploy.sh', configs.setup || '');
      zip.file('models.py', generateSqlAlchemyClasses() || '');
      zip.file('db_schema.sql', configs.schema || '');
      zip.file('subordinates_route.py', configs.routes || '');

      // 2. Add documentation subfolder
      const docs = zip.folder('docs');
      
      docs.file('db_schema.md', `# Database Schema Documentation: ${selectedSchool}

This document describes the database tables generated for the active appraisal template.

## Tables

### 1. \`${selectedSchool.toLowerCase()}_declarations\`
Holds form metadata and overall appraisal scores across approval workflows.
- \`id\` (INTEGER, Primary Key): Unique identifier.
- \`faculty_email\` (VARCHAR, Not Null): Submitter email.
- \`academic_year\` (VARCHAR, Not Null): Evaluation year.
- \`grand_total\` (NUMERIC): Score calculated by the submitter.
- \`hod_total\` (NUMERIC): Score assigned by the Head of Department.
- \`director_total\` (NUMERIC): Score assigned by the School Director.
- \`dean_total\` (NUMERIC): Score assigned by the Dean.
- \`vc_total\` (NUMERIC): Final approved VC score.
- \`status\` (VARCHAR): Current appraisal workflow pipeline status.

## Fields and Columns Configuration
The fields configured on the canvas are mapped to relational tables with corresponding columns matching their input type (text, number, boolean):

${currentFields.map(f => {
  if (f.type === 'table') {
    return `### Table: \`${f.label.toLowerCase().replace(/[^a-z0-9]/g, '_')}\`
Columns:
${(f.columns || []).map(c => `  - \`${c.name}\` (${c.type.toUpperCase()})`).join('\n')}
`;
  } else {
    return `- Standalone field: \`${f.label}\` (Type: ${f.type.toUpperCase()}, Role: ${f.role})`;
  }
}).join('\n')}
`);

      docs.file('api_endpoints.md', `# Backend API Endpoints Guide

This guide defines the REST API endpoints used by the Appraisal frontend system.

## 1. Authentication
* \`POST /api/v1/auth/login\`
  Authenticates user and returns JWT token + profile info.
* \`GET /api/v1/auth/me\`
  Retrieves profile info for the currently authenticated user session.

## 2. Appraisal Submission
* \`GET /api/v1/appraisal/window\`
  Retrieves active appraisal submission cycles and academic years.
* \`POST /api/v1/appraisal/submit\`
  Submits faculty appraisal form answers for the active cycle.
* \`GET /api/v1/appraisal/status\`
  Checks current pipeline submission status of the user's form.

## 3. Reviewer Workflow
* \`GET /api/v1/pending/reviews\`
  Retrieves pending files for review (HOD, Director, Dean, or VC queue).
* \`POST /api/v1/pending/reviews/{id}/approve\`
  Submits reviewer scores, optional notes, and advances form to the next hierarchy level.
`);

      docs.file('frontend_url_paths.md', `# Frontend URL Route Paths

The following routes are mapped by the React router inside the application bundle:

## 1. Authentication & Core
* \`/login\`
  Sign-in screen.
* \`/profile\`
  Edit profile, reset credentials, and MFA setup.
* \`/\`
  User dashboard / overview statistics.

## 2. Admin & Workflow Management
* \`/cycle\`
  Appraisal cycle and submission window setup.
* \`/faculty\`
  Faculty registry lists and registration.
* \`/workflow/templates\`
  Custom approval workflow sequence mapping.
* \`/feedback\`
  Feedback portal and review logs.

## 3. Experimental Sandbox (Developer Only)
* \`/developer/sandbox/form-builder\`
  Visual Form Canvas builder.
* \`/developer/sandbox/roles\`
  Dynamic User Roles and levels hierarchy config.
* \`/developer/sandbox/reporting-lines\`
  HOD and reviewer mapping rules.
* \`/developer/sandbox/workflow-sim\`
  Hierarchy stepper simulator.
* \`/developer/sandbox/deploy-export\`
  Release packager and configs exporter.
* \`/developer/sandbox/sample-demo\`
  Standalone user-facing workflow preview.
`);

      // Generate blob and download
      const content = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(content);
      const link = document.createElement('a');
      link.href = url;
      link.download = `pbas_${selectedSchool.toLowerCase()}_release.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert("❌ Error compiling release: " + err.message);
    } finally {
      setCompiling(false);
    }
  };

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
              onClick={handleCompileZip}
              disabled={compiling}
              className={pBtn}
              style={{ width: '100%', padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, opacity: compiling ? 0.7 : 1, cursor: compiling ? 'not-allowed' : 'pointer' }}
            >
              <I.dl size={16} /> {compiling ? 'Compiling release...' : 'Compile & Download Client Zip'}
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
