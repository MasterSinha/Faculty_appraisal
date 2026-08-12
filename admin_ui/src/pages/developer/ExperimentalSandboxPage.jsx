import { useState, useRef } from 'react';
import { C } from '../../constants/colors';
import Card from '../../components/Card';
import PageHead from '../../components/PageHead';
import { I } from '../../components/icons';
import { pBtn, oBtn } from '../../constants/styleTokens';

export default function ExperimentalSandboxPage() {
  const [activeTab, setActiveTab] = useState('form-builder');
  const [selectedSchool, setSelectedSchool] = useState('SoCSEA');

  // Multi-school Form Configurations (Engineering, Creative, Media, Custom)
  const [schoolForms, setSchoolForms] = useState({
    SoCSEA: [
      { id: 'f1', label: 'Faculty Name', type: 'text', part: 'Part A', role: 'faculty', required: true, access: 'full' },
      { 
        id: 'f2', 
        label: 'Research Project Grants', 
        type: 'table', 
        part: 'Part B', 
        role: 'faculty', 
        columns: [
          { name: 'Project Title', type: 'text' },
          { name: 'Funding Agency', type: 'text' },
          { name: 'Amount Sanctioned', type: 'number' },
          { name: 'Overhead Received', type: 'number' },
          { name: 'Total Project Value', type: 'formula', formulaExpr: 'Amount Sanctioned + Overhead Received' },
          { name: 'Status', type: 'dropdown', options: ['Ongoing', 'Completed', 'Approved'] },
          { name: 'Co-Principal Investigator?', type: 'checkbox' }
        ],
        tableMaxMarks: 50,
        rowMaxMarks: 10,
        isOptional: true,
        attachmentType: 'per-row',
        access: 'full'
      },
      { id: 'f3', label: 'Peer Review & Behavior Grid', type: 'table', part: 'Part C', role: 'hod', columns: [{ name: 'Integrity Rating', type: 'dropdown', options: ['Outstanding', 'Good', 'Average'] }, { name: 'Collaboration', type: 'text' }, { name: 'Senior Remarks', type: 'text' }], tableMaxMarks: 20, rowMaxMarks: 5, isOptional: false, attachmentType: 'none', access: 'reviewer-edit' }
    ],
    SoD: [
      { id: 'd1', label: 'Designer Name', type: 'text', part: 'Part A', role: 'faculty', required: true, access: 'full' },
      { id: 'd2', label: 'Design Portfolio URL', type: 'text', part: 'Part B', role: 'faculty', required: true, access: 'full' },
      { 
        id: 'd3', 
        label: 'Exhibition Listings', 
        type: 'table', 
        part: 'Part B', 
        role: 'faculty', 
        columns: [
          { name: 'Exhibition Title', type: 'text' },
          { name: 'Year', type: 'number' },
          { name: 'Location', type: 'text' }
        ],
        tableMaxMarks: 100,
        rowMaxMarks: 20,
        isOptional: false,
        attachmentType: 'per-table',
        access: 'full'
      }
    ],
    Custom: []
  });

  // Target Reporting Mappings state
  const [mockFaculty, setMockFaculty] = useState([
    { email: 'faculty1@univ.edu', name: 'Dr. Alan Turing', assignedHod: 'hod1@univ.edu' },
    { email: 'faculty2@univ.edu', name: 'Dr. Grace Hopper', assignedHod: 'hod2@univ.edu' }
  ]);
  const [mockHods, setMockHods] = useState([
    { email: 'hod1@univ.edu', name: 'HOD Computer Science (CS)' },
    { email: 'hod2@univ.edu', name: 'HOD Computer Engineering (CE)' }
  ]);
  const [selectedFacultySim, setSelectedFacultySim] = useState('faculty1@univ.edu');

  // Workflow Routing Paths per School
  const [schoolWorkflows, setSchoolWorkflows] = useState({
    SoCSEA: [
      { id: 'w1', label: 'Faculty Submission' },
      { id: 'w2', label: 'Assigned HOD Review' },
      { id: 'w3', label: 'Director Review' },
      { id: 'w4', label: 'Dean Approval' },
      { id: 'w5', label: 'VC Finalization' }
    ],
    SoD: [
      { id: 'ws1', label: 'Faculty Submission' },
      { id: 'ws2', label: 'Director Review' }, // Creative bypasses HOD
      { id: 'ws3', label: 'Dean Approval' },
      { id: 'ws4', label: 'VC Finalization' }
    ],
    Custom: [
      { id: 'c1', label: 'Faculty Submission' },
      { id: 'c2', label: 'VC Finalization' }
    ]
  });

  // Interactive Simulator state
  const [simActiveStep, setSimActiveStep] = useState(0);
  const [simLogs, setSimLogs] = useState([]);
  const [simRunning, setSimRunning] = useState(false);
  const [simulatedRole, setSimulatedRole] = useState('faculty');

  // Preview form values
  const [previewData, setPreviewData] = useState({});
  const [previewTables, setPreviewTables] = useState({
    f2: [ { 'Project Title': 'Quantum Cryptography Prototyping', 'Funding Agency': 'DST-SERB', 'Amount Sanctioned': '450000', 'Overhead Received': '50000', 'Status': 'Ongoing', 'Co-Principal Investigator?': 'true' } ],
    f3: [ { 'Integrity Rating': 'Outstanding', 'Collaboration': 'Strong', 'Senior Remarks': 'Respectful and cooperative.' } ],
    d3: [ { 'Exhibition Title': '', 'Year': '', 'Location': '' } ]
  });

  // Keep track of deselected optional tables in simulation
  const [disabledSections, setDisabledSections] = useState({});

  // Column Designer state
  const [newColName, setNewColName] = useState('');
  const [newColType, setNewColType] = useState('text');
  const [newColOptions, setNewColOptions] = useState('');
  const [newColFormula, setNewColFormula] = useState('');

  // Deployment Export Tab configuration viewer state
  const [selectedConfigType, setSelectedConfigType] = useState('docker');

  const fileInputRef = useRef(null);

  // Current Form Fields based on School
  const currentFields = schoolForms[selectedSchool] || [];
  const currentWorkflow = schoolWorkflows[selectedSchool] || [];

  // Add field helper
  const addField = () => {
    const newField = {
      id: Date.now().toString(),
      label: `New Field ${currentFields.length + 1}`,
      type: 'text',
      part: 'Part A',
      role: 'faculty',
      required: false,
      columns: [],
      tableMaxMarks: 0,
      rowMaxMarks: 0,
      isOptional: false,
      attachmentType: 'none',
      access: 'full'
    };
    setSchoolForms({
      ...schoolForms,
      [selectedSchool]: [...currentFields, newField]
    });
  };

  // Update field property
  const updateField = (id, key, val) => {
    setSchoolForms({
      ...schoolForms,
      [selectedSchool]: currentFields.map(f => f.id === id ? { ...f, [key]: val } : f)
    });
  };

  // Delete field
  const deleteField = (id) => {
    setSchoolForms({
      ...schoolForms,
      [selectedSchool]: currentFields.filter(f => f.id !== id)
    });
  };

  // Add column to table field type with specific data type config
  const addTableColumn = (fieldId) => {
    if (!newColName.trim()) return;
    setSchoolForms({
      ...schoolForms,
      [selectedSchool]: currentFields.map(f => {
        if (f.id === fieldId) {
          const cols = f.columns || [];
          const newCol = {
            name: newColName,
            type: newColType,
            options: newColType === 'dropdown' ? newColOptions.split(',').map(o => o.trim()) : [],
            formulaExpr: newColType === 'formula' ? newColFormula : ''
          };
          return { ...f, columns: [...cols, newCol] };
        }
        return f;
      })
    });
    // Reset column creation inputs
    setNewColName('');
    setNewColType('text');
    setNewColOptions('');
    setNewColFormula('');
  };

  // Remove column from table
  const removeTableColumn = (fieldId, colIdx) => {
    setSchoolForms({
      ...schoolForms,
      [selectedSchool]: currentFields.map(f => {
        if (f.id === fieldId) {
          const cols = [...(f.columns || [])];
          cols.splice(colIdx, 1);
          return { ...f, columns: cols };
        }
        return f;
      })
    });
  };

  // Add row to tabular preview
  const addTableRow = (fieldId, cols) => {
    const newRow = {};
    cols.forEach(c => {
      if (c.type === 'checkbox') {
        newRow[c.name] = 'false';
      } else {
        newRow[c.name] = '';
      }
    });
    const existing = previewTables[fieldId] || [];
    setPreviewTables({
      ...previewTables,
      [fieldId]: [...existing, newRow]
    });
  };

  // Update table cell
  const updateTableCell = (fieldId, rowIdx, colName, val) => {
    const rows = [...(previewTables[fieldId] || [])];
    rows[rowIdx] = { ...rows[rowIdx], [colName]: val };
    setPreviewTables({
      ...previewTables,
      [fieldId]: rows
    });
  };

  // Duplicate / Clone layout from another school
  const cloneFromSchool = (sourceSchool) => {
    if (sourceSchool === selectedSchool) return;
    if (window.confirm(`Are you sure you want to clone the form layout from ${sourceSchool}? This will overwrite your current configuration.`)) {
      setSchoolForms({
        ...schoolForms,
        [selectedSchool]: JSON.parse(JSON.stringify(schoolForms[sourceSchool]))
      });
    }
  };

  // Add workflow step helper
  const addWorkflowStep = () => {
    const newStep = {
      id: Date.now().toString(),
      label: `New Review Step ${currentWorkflow.length + 1}`
    };
    setSchoolWorkflows({
      ...schoolWorkflows,
      [selectedSchool]: [...currentWorkflow, newStep]
    });
  };

  // Update workflow step label
  const updateWorkflowStepLabel = (id, val) => {
    setSchoolWorkflows({
      ...schoolWorkflows,
      [selectedSchool]: currentWorkflow.map(s => s.id === id ? { ...s, label: val } : s)
    });
  };

  // Move workflow step up/down
  const moveWorkflowStep = (idx, direction) => {
    const nextIdx = idx + direction;
    if (nextIdx < 0 || nextIdx >= currentWorkflow.length) return;
    const nextSteps = [...currentWorkflow];
    const temp = nextSteps[idx];
    nextSteps[idx] = nextSteps[nextIdx];
    nextSteps[nextIdx] = temp;
    setSchoolWorkflows({
      ...schoolWorkflows,
      [selectedSchool]: nextSteps
    });
  };

  // Delete workflow step
  const deleteWorkflowStep = (id) => {
    setSchoolWorkflows({
      ...schoolWorkflows,
      [selectedSchool]: currentWorkflow.filter(s => s.id !== id)
    });
  };

  // Simulator Engine logs
  const logSim = (msg) => {
    const timestamp = new Date().toLocaleTimeString();
    setSimLogs(prev => [`[${timestamp}] ${msg}`, ...prev]);
  };

  const startSimulation = () => {
    setSimActiveStep(0);
    setSimRunning(true);
    setSimLogs([]);

    const facultyUser = mockFaculty.find(f => f.email === selectedFacultySim);
    const assignedHodUser = mockHods.find(h => h.email === facultyUser.assignedHod);

    logSim(`🚀 Initializing workflow for School: ${selectedSchool}`);
    logSim(`Submitting Faculty: ${facultyUser.name} (${facultyUser.email})`);
    logSim(`Target Reporting HOD: ${assignedHodUser.name} (${assignedHodUser.email})`);
    logSim(`Appraisal Form populated with ${currentFields.length} custom fields.`);
  };

  const advanceSimulation = (approve = true) => {
    if (!simRunning) return;
    const currentStep = currentWorkflow[simActiveStep];
    const facultyUser = mockFaculty.find(f => f.email === selectedFacultySim);
    const assignedHodUser = mockHods.find(h => h.email === facultyUser.assignedHod);

    if (approve) {
      logSim(`✅ Step ${simActiveStep + 1} (${currentStep.label}) APPROVED.`);
      if (simActiveStep + 1 < currentWorkflow.length) {
        setSimActiveStep(prev => prev + 1);
        const nextStep = currentWorkflow[simActiveStep + 1];
        
        let routedTo = nextStep.label;
        if (nextStep.label.toLowerCase().includes('hod')) {
          routedTo = `${nextStep.label} (${assignedHodUser.name})`;
        }
        logSim(`👉 Appraisal routed to Step ${simActiveStep + 2}: ${routedTo}`);
      } else {
        logSim("🎉 APPRAISAL FULLY APPROVED AND snapshot saved successfully!");
        setSimRunning(false);
      }
    } else {
      logSim(`❌ Step ${simActiveStep + 1} (${currentStep.label}) REJECTED.`);
      logSim(`↩️ Backtracking appraisal directly to Faculty (${facultyUser.name}) for revisions.`);
      setSimActiveStep(0);
    }
  };

  // Calculate dynamic Total Max Marks for preview
  const calculateTotalMaxMarks = () => {
    let total = 0;
    currentFields.forEach(f => {
      // Skip if marked as not applicable
      if (disabledSections[f.id]) return;

      if (f.type === 'table') {
        total += Number(f.tableMaxMarks || 0);
      } else if (f.type === 'number') {
        total += 50;
      } else {
        total += 10;
      }
    });
    return total;
  };

  // Evaluate formula columns dynamically
  const evaluateCellFormula = (formulaExpr, rowObj) => {
    if (!formulaExpr) return 0;
    try {
      // Replace variable names in expression with actual numeric cell values
      let evaluated = formulaExpr;
      Object.keys(rowObj).forEach(key => {
        const val = Number(rowObj[key]) || 0;
        // Escape special chars in key for regex matching
        const escapedKey = key.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
        evaluated = evaluated.replace(new RegExp(escapedKey, 'g'), val.toString());
      });
      // Evaluate basic arithmetic expression safely
      return Function(`"use strict"; return (${evaluated})`)();
    } catch (e) {
      return 'Error';
    }
  };

  // Export custom schema to local JSON file
  const handleExportSchema = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({ schoolForms, schoolWorkflows }, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `pbas_custom_schema_${selectedSchool.toLowerCase()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  // Import custom schema from local JSON file
  const handleImportSchema = (e) => {
    const fileReader = new FileReader();
    fileReader.readAsText(e.target.files[0], "UTF-8");
    fileReader.onload = e => {
      try {
        const parsed = JSON.parse(e.target.result);
        if (parsed.schoolForms && parsed.schoolWorkflows) {
          setSchoolForms(parsed.schoolForms);
          setSchoolWorkflows(parsed.schoolWorkflows);
          alert("Custom Form & Workflow Schema imported successfully!");
        } else {
          alert("Invalid schema file structure.");
        }
      } catch (err) {
        alert("Failed to parse JSON file.");
      }
    };
  };

  // Generate dynamic SQLAlchemy code models based on configurations
  const generateSqlAlchemyClasses = () => {
    return `from sqlalchemy import Column, String, Integer, Numeric, Boolean, ForeignKey
from src.setup.database import Base

# ===========================================================================
# Auto-Generated Database Classes for School: ${selectedSchool}
# ===========================================================================

class ${selectedSchool}Declaration(Base):
    __tablename__ = "${selectedSchool.toLowerCase()}_declarations"
    
    id = Column(Integer, primary_key=True)
    faculty_email = Column(String, nullable=False)
    academic_year = Column(String, nullable=False)
    part_a_total = Column(Numeric, default=0.0)
    status = Column(String, default="Submitted")

${currentFields.filter(f => f.type === 'table').map(f => {
  const className = `${selectedSchool}${f.label.replace(/ /g, '')}Item`;
  const tableName = `${selectedSchool.toLowerCase()}_${f.label.toLowerCase().replace(/ /g, '_')}_items`;
  return `class ${className}(Base):
    __tablename__ = "${tableName}"
    
    id = Column(Integer, primary_key=True)
    declaration_id = Column(Integer, ForeignKey("${selectedSchool.toLowerCase()}_declarations.id"))
    ${f.attachmentType !== 'none' ? "attachment_path = Column(String, nullable=True)\n    " : ""}${(f.columns || []).map(c => {
      let pyType = 'String';
      if (c.type === 'number' || c.type === 'formula') pyType = 'Numeric';
      if (c.type === 'checkbox') pyType = 'Boolean';
      return `${c.name.toLowerCase().replace(/[^a-z0-9]/g, '_')} = Column(${pyType}, nullable=True)`;
    }).join('\n    ')}
`;
}).join('\n')}`;
  };

  // Config files templates
  const CONFIGS_TEMPLATES = {
    docker: `version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: client_pbas_db
    restart: always
    environment:
      POSTGRES_DB: \${DB_NAME:-pbas}
      POSTGRES_USER: \${DB_USER:-postgres}
      POSTGRES_PASSWORD: \${DB_PASSWORD:-supersecurepwd}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: client_pbas_backend
    restart: always
    environment:
      - DATABASE_URL=postgresql://\${DB_USER}:\${DB_PASSWORD}@db:5432/\${DB_NAME}
      - JWT_SECRET_KEY=\${JWT_SECRET}
      - ENVIRONMENT=production
    depends_on:
      - db
    volumes:
      - ./uploads:/app/uploads

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: client_pbas_frontend
    restart: always
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - /etc/letsencrypt:/etc/letsencrypt

volumes:
  pgdata:`,

    nginx: `server {
    listen 80;
    server_name pbas.clientcollege.edu;

    # Redirect http to https
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name pbas.clientcollege.edu;

    ssl_certificate /etc/letsencrypt/live/pbas.clientcollege.edu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pbas.clientcollege.edu/privkey.pem;

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}`,

    setup: `#!/bin/bash
# automated SSH installation script
echo "=============================================="
echo "Starting installation for college appraisal..."
echo "=============================================="

# 1. Install Docker & docker-compose
if ! [ -x "$(command -v docker)" ]; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com -o get-docker.sh
  sh get-docker.sh
  usermod -aG docker $USER
fi

# 2. Prepare environment directories
mkdir -p uploads backend frontend

# 3. Create active .env
cat <<EOT > .env
DB_NAME=pbas_prod
DB_USER=postgres_admin
DB_PASSWORD=$(openssl rand -hex 16)
JWT_SECRET=$(openssl rand -hex 32)
EOT

# 4. Spin up standard container blocks
echo "Spiralling up docker-compose stack..."
docker compose up -d --build

echo "Application is now online and running schema migration scripts."`,

    schema: `-- Auto-Generated Migration for ${selectedSchool}
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Template fields mapping schema:
${currentFields.map(f => {
  const table = f.type === 'table' ? `CREATE TABLE IF NOT EXISTS custom_${selectedSchool.toLowerCase()}_${f.id} (
    id SERIAL PRIMARY KEY,
    faculty_email VARCHAR(255) NOT NULL,
    academic_year VARCHAR(50) NOT NULL,
    ${f.attachmentType !== 'none' ? 'attachment_url TEXT,\n    ' : ''}${(f.columns || []).map(c => `${c.name.toLowerCase().replace(/[^a-z0-9]/g, '_')} TEXT`).join(',\n    ')}
);` : `-- Field: ${f.label} (${f.type})`;
  return table;
}).join('\n\n')}
`
  };

  return (
    <div style={{ padding: 24, minHeight: 'calc(100vh - 80px)', background: 'var(--c-bg)' }}>
      <PageHead 
        title="Experimental Sandbox Engine" 
        subtitle="Full sandbox playground to model custom forms, configure spreadsheet columns/formulas, establish reporting lines, and view deployment scripts."
      />

      {/* School selector & Tab header controls */}
      <div style={{ 
        display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', 
        marginBottom: 24, padding: 16, borderRadius: 12, background: 'var(--c-sidebar-icon-bg)', 
        border: '1px solid var(--c-sidebar-icon-border)', gap: 16 
      }}>
        <div style={{ display: 'flex', gap: 12 }}>
          <button
            onClick={() => setActiveTab('form-builder')}
            style={{
              padding: '8px 16px', borderRadius: 8, cursor: 'pointer', border: 'none', fontWeight: 600,
              background: activeTab === 'form-builder' ? '#3b82f6' : 'transparent',
              color: activeTab === 'form-builder' ? '#ffffff' : 'var(--c-sidebar-muted)'
            }}
          >
            Form Designer
          </button>
          <button
            onClick={() => setActiveTab('reporting-lines')}
            style={{
              padding: '8px 16px', borderRadius: 8, cursor: 'pointer', border: 'none', fontWeight: 600,
              background: activeTab === 'reporting-lines' ? '#3b82f6' : 'transparent',
              color: activeTab === 'reporting-lines' ? '#ffffff' : 'var(--c-sidebar-muted)'
            }}
          >
            Target Mappings
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

      {activeTab === 'form-builder' ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
          {/* Custom Form Designer */}
          <Card title="1. Custom Form Designer" description={`Adding custom fields to form template of ${selectedSchool}.`}>
            {/* Import / Export JSON Schema */}
            <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
              <button 
                onClick={handleExportSchema}
                style={{ padding: '6px 12px', borderRadius: 8, background: '#3b82f615', border: '1px solid #3b82f630', color: '#3b82f6', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}
              >
                💾 Export Schema JSON
              </button>
              <button 
                onClick={() => fileInputRef.current.click()}
                style={{ padding: '6px 12px', borderRadius: 8, background: '#10b98115', border: '1px solid #10b98130', color: '#10b981', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}
              >
                📂 Import Schema JSON
              </button>
              <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleImportSchema} 
                accept=".json" 
                style={{ display: 'none' }} 
              />
            </div>

            <div style={{ maxHeight: '52vh', overflowY: 'auto', paddingRight: 8 }}>
              {currentFields.map((field) => (
                <div 
                  key={field.id} 
                  style={{
                    padding: 16, borderRadius: 12, border: '1px solid var(--c-sidebar-icon-border)',
                    marginBottom: 16, background: 'var(--c-sidebar-icon-bg)', position: 'relative'
                  }}
                >
                  <button 
                    onClick={() => deleteField(field.id)}
                    style={{ position: 'absolute', top: 12, right: 12, background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer' }}
                  >
                    <I.trash size={14} />
                  </button>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                    <div>
                      <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Field Label</label>
                      <input
                        type="text"
                        value={field.label}
                        onChange={(e) => updateField(field.id, 'label', e.target.value)}
                        style={{ width: '90%', padding: '6px 10px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13 }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Input Type</label>
                      <select
                        value={field.type}
                        onChange={(e) => updateField(field.id, 'type', e.target.value)}
                        style={{ width: '100%', padding: '6px 10px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13 }}
                      >
                        <option value="text">Short Text</option>
                        <option value="number">Number</option>
                        <option value="textarea">Paragraph text</option>
                        <option value="table">Table (Multiple Rows)</option>
                      </select>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                    <div>
                      <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Appraisal Part</label>
                      <select
                        value={field.part}
                        onChange={(e) => updateField(field.id, 'part', e.target.value)}
                        style={{ width: '90%', padding: '6px 10px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13 }}
                      >
                        <option value="Part A">Part A (General Info)</option>
                        <option value="Part B">Part B (Academic Performance)</option>
                        <option value="Part C">Part C (HOD Remarks)</option>
                        <option value="Part D">Part D (Director Review)</option>
                        <option value="Part E">Part E (Future Expansion Slot)</option>
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Input Owner Role</label>
                      <select
                        value={field.role}
                        onChange={(e) => updateField(field.id, 'role', e.target.value)}
                        style={{ width: '100%', padding: '6px 10px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13 }}
                      >
                        <option value="faculty">Faculty (Self)</option>
                        <option value="hod">HOD</option>
                        <option value="director">Director</option>
                        <option value="dean">Dean</option>
                        <option value="vc">VC</option>
                      </select>
                    </div>
                  </div>

                  {/* Access Permissions Dropdown */}
                  <div style={{ marginBottom: 12 }}>
                    <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-sidebar-muted)' }}>Access & Visibility Restrictions</label>
                    <select
                      value={field.access || 'full'}
                      onChange={(e) => updateField(field.id, 'access', e.target.value)}
                      style={{ width: '100%', padding: '6px 10px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13 }}
                    >
                      <option value="full">Full Access (Faculty fills, Reviewers read)</option>
                      <option value="reviewer-edit">Reviewer Only (Faculty can see empty grid, but cannot edit)</option>
                      <option value="reviewer-hidden">Reviewer Only (Completely hidden from Faculty view)</option>
                    </select>
                  </div>

                  {/* Config columns if table type */}
                  {field.type === 'table' && (
                    <div style={{ borderTop: '1px solid var(--c-sidebar-icon-border)', paddingTop: 10, marginTop: 10 }}>
                      {/* Advanced Table Settings */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                        <div>
                          <label style={{ fontSize: 11, color: 'var(--c-sidebar-muted)' }}>Table Max Marks</label>
                          <input
                            type="number"
                            value={field.tableMaxMarks || 0}
                            onChange={(e) => updateField(field.id, 'tableMaxMarks', Number(e.target.value))}
                            style={{ width: '80%', padding: '4px 8px', borderRadius: 6, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)' }}
                          />
                        </div>
                        <div>
                          <label style={{ fontSize: 11, color: 'var(--c-sidebar-muted)' }}>Row Max Marks</label>
                          <input
                            type="number"
                            value={field.rowMaxMarks || 0}
                            onChange={(e) => updateField(field.id, 'rowMaxMarks', Number(e.target.value))}
                            style={{ width: '85%', padding: '4px 8px', borderRadius: 6, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)' }}
                          />
                        </div>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <input
                            type="checkbox"
                            checked={field.isOptional || false}
                            onChange={(e) => updateField(field.id, 'isOptional', e.target.checked)}
                            id={`opt-${field.id}`}
                          />
                          <label htmlFor={`opt-${field.id}`} style={{ fontSize: 12, color: 'var(--c-text)' }}>Is Table Optional</label>
                        </div>
                        <div>
                          <label style={{ fontSize: 11, color: 'var(--c-sidebar-muted)' }}>Required Attachments</label>
                          <select
                            value={field.attachmentType || 'none'}
                            onChange={(e) => updateField(field.id, 'attachmentType', e.target.value)}
                            style={{ width: '100%', padding: '4px 8px', borderRadius: 6, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)' }}
                          >
                            <option value="none">No Attachments</option>
                            <option value="per-row">One per Table Row</option>
                            <option value="per-table">One for the whole Table</option>
                          </select>
                        </div>
                      </div>

                      <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--c-sidebar-muted)' }}>Columns List</label>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', margin: '6px 0' }}>
                        {(field.columns || []).map((col, cidx) => (
                          <span 
                            key={cidx} 
                            style={{ 
                              background: '#3b82f615', color: '#3b82f6', border: '1px solid #3b82f630',
                              padding: '4px 10px', borderRadius: 8, fontSize: 11.5, display: 'flex', alignItems: 'center', gap: 6 
                            }}
                          >
                            <strong>{col.name}</strong> ({col.type.toUpperCase()})
                            <button 
                              onClick={() => removeTableColumn(field.id, cidx)}
                              style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', padding: 0, fontWeight: 700 }}
                            >
                              ×
                            </button>
                          </span>
                        ))}
                      </div>

                      {/* Add Column Options Creator */}
                      <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-sidebar-icon-border)', padding: 12, borderRadius: 8, marginTop: 8 }}>
                        <h5 style={{ margin: '0 0 8px 0', fontSize: 11.5 }}>Add New Spreadsheet Column</h5>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
                          <input
                            type="text"
                            placeholder="Column Title (e.g. Sales)"
                            value={newColName}
                            onChange={(e) => setNewColName(e.target.value)}
                            style={{ padding: '6px 8px', borderRadius: 6, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)', color: 'var(--c-text)', fontSize: 12 }}
                          />
                          <select
                            value={newColType}
                            onChange={(e) => setNewColType(e.target.value)}
                            style={{ padding: '6px 8px', borderRadius: 6, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)', color: 'var(--c-text)', fontSize: 12 }}
                          >
                            <option value="text">Text</option>
                            <option value="number">Number</option>
                            <option value="email">Email</option>
                            <option value="phone">Phone</option>
                            <option value="dropdown">Dropdown Options</option>
                            <option value="checkbox">Checkbox (Yes/No)</option>
                            <option value="formula">Formula Column</option>
                          </select>
                        </div>

                        {newColType === 'dropdown' && (
                          <input
                            type="text"
                            placeholder="Options (comma-separated, e.g. Pass, Fail)"
                            value={newColOptions}
                            onChange={(e) => setNewColOptions(e.target.value)}
                            style={{ width: '90%', padding: '6px 8px', borderRadius: 6, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)', color: 'var(--c-text)', fontSize: 12, marginBottom: 8 }}
                          />
                        )}

                        {newColType === 'formula' && (
                          <input
                            type="text"
                            placeholder="Formula (e.g. Price * Quantity)"
                            value={newColFormula}
                            onChange={(e) => setNewColFormula(e.target.value)}
                            style={{ width: '90%', padding: '6px 8px', borderRadius: 6, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)', color: 'var(--c-text)', fontSize: 12, marginBottom: 8 }}
                          />
                        )}

                        <button
                          onClick={() => addTableColumn(field.id)}
                          style={{ width: '100%', padding: '6px', borderRadius: 6, background: '#3b82f6', color: '#fff', border: 'none', cursor: 'pointer', fontSize: 11.5, fontWeight: 600 }}
                        >
                          + Append Spreadsheet Column
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <button 
              onClick={addField}
              style={{
                width: '100%', padding: 10, borderRadius: 10, border: '1px dashed #3b82f6', color: '#3b82f6',
                background: 'transparent', cursor: 'pointer', fontWeight: 600, marginTop: 12,
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8
              }}
            >
              <I.addUser size={14} /> Add Template Field
            </button>
          </Card>

          {/* Role Preview Simulation & Models Class Visualizer */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <Card title="2. Role & Part Simulation" description="Simulate specific user views and test tabular data grids.">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
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

              {/* Simulated Live Form */}
              <div style={{ padding: 16, borderRadius: 12, background: 'var(--c-sidebar-icon-bg)', border: '1px solid var(--c-sidebar-icon-border)', minHeight: 220 }}>
                <h4 style={{ margin: '0 0 16px 0', borderBottom: '1px solid var(--c-sidebar-icon-border)', paddingBottom: 8, fontSize: 14 }}>
                  Rendered Form Template
                </h4>

                {currentFields.length === 0 ? (
                  <div style={{ color: 'var(--c-sidebar-muted)', textAlign: 'center', marginTop: 48 }}>
                    No fields defined yet for this school. Add fields on the designer.
                  </div>
                ) : (
                  currentFields.map((field) => {
                    // Access rules logic
                    const isReadOnly = field.role !== simulatedRole || field.access === 'reviewer-edit';
                    const isHidden = field.access === 'reviewer-hidden' && simulatedRole === 'faculty';
                    const isDeselected = disabledSections[field.id];

                    if (isHidden) return null;

                    return (
                      <div key={field.id} style={{ marginBottom: 20, opacity: isReadOnly || isDeselected ? 0.5 : 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--c-text)', textDecoration: isDeselected ? 'line-through' : 'none' }}>
                            {field.label} {field.required && <span style={{ color: '#ef4444' }}>*</span>}
                          </span>
                          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                            {field.access !== 'full' && (
                              <span style={{ fontSize: 9, color: '#f59e0b', background: '#f59e0b15', padding: '1px 6px', borderRadius: 4, fontWeight: 700 }}>
                                {field.access === 'reviewer-edit' ? 'REVIEWER-EDIT' : 'SECRET TO FACULTY'}
                              </span>
                            )}
                            {/* Optional Section Selector */}
                            {field.isOptional && !isReadOnly && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginRight: 8 }}>
                                <input
                                  type="checkbox"
                                  checked={!isDeselected}
                                  onChange={(e) => setDisabledSections({ ...disabledSections, [field.id]: !e.target.checked })}
                                  id={`check-${field.id}`}
                                />
                                <label htmlFor={`check-${field.id}`} style={{ fontSize: 11, color: 'var(--c-sidebar-muted)' }}>Applicable</label>
                              </div>
                            )}
                            <span style={{ fontSize: 10, color: 'var(--c-sidebar-muted)', background: 'var(--c-bg)', padding: '2px 6px', borderRadius: 4 }}>
                              {field.part} &bull; {field.role.toUpperCase()}
                            </span>
                          </div>
                        </div>

                        {field.type === 'table' ? (
                          <div style={{ overflowX: 'auto', border: '1px solid var(--c-sidebar-icon-border)', borderRadius: 8, padding: 8, background: 'var(--c-bg)' }}>
                            {field.tableMaxMarks > 0 && (
                              <div style={{ fontSize: 11, color: '#3b82f6', marginBottom: 6, fontWeight: 600 }}>
                                Table Max Marks: {field.tableMaxMarks} &nbsp;|&nbsp; Row Max Marks: {field.rowMaxMarks}
                              </div>
                            )}

                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                              <thead>
                                <tr style={{ borderBottom: '1px solid var(--c-sidebar-icon-border)' }}>
                                  {(field.columns || []).map((col, idx) => (
                                    <th key={idx} style={{ textAlign: 'left', padding: 6, color: 'var(--c-sidebar-muted)' }}>{col.name}</th>
                                  ))}
                                  {field.attachmentType === 'per-row' && (
                                    <th style={{ textAlign: 'left', padding: 6, color: 'var(--c-sidebar-muted)' }}>Attachment</th>
                                  )}
                                </tr>
                              </thead>
                              <tbody>
                                {(previewTables[field.id] || []).map((row, rowIdx) => (
                                  <tr key={rowIdx}>
                                    {(field.columns || []).map((col, colIdx) => {
                                      if (col.type === 'formula') {
                                        const computedVal = evaluateCellFormula(col.formulaExpr, row);
                                        return (
                                          <td key={colIdx} style={{ padding: 4 }}>
                                            <input
                                              type="text"
                                              disabled
                                              value={computedVal}
                                              style={{ width: '90%', padding: '4px 6px', borderRadius: 4, border: '1px solid var(--c-sidebar-icon-border)', background: 'rgba(59,130,246,0.1)', color: '#3b82f6', fontWeight: 'bold' }}
                                            />
                                          </td>
                                        );
                                      }

                                      if (col.type === 'checkbox') {
                                        return (
                                          <td key={colIdx} style={{ padding: 4, textAlign: 'center' }}>
                                            <input
                                              type="checkbox"
                                              disabled={isReadOnly || isDeselected}
                                              checked={row[col.name] === 'true'}
                                              onChange={(e) => updateTableCell(field.id, rowIdx, col.name, e.target.checked ? 'true' : 'false')}
                                            />
                                          </td>
                                        );
                                      }

                                      if (col.type === 'dropdown') {
                                        const dropdownOpts = col.options || [];
                                        return (
                                          <td key={colIdx} style={{ padding: 4 }}>
                                            <select
                                              disabled={isReadOnly || isDeselected}
                                              value={row[col.name] || ''}
                                              onChange={(e) => updateTableCell(field.id, rowIdx, col.name, e.target.value)}
                                              style={{ width: '90%', padding: '4px 6px', borderRadius: 4, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)', color: 'var(--c-text)' }}
                                            >
                                              <option value="">Select...</option>
                                              {dropdownOpts.map((opt, oidx) => (
                                                <option key={oidx} value={opt}>{opt}</option>
                                              ))}
                                            </select>
                                          </td>
                                        );
                                      }

                                      return (
                                        <td key={colIdx} style={{ padding: 4 }}>
                                          <input
                                            type={col.type === 'number' ? 'number' : col.type === 'email' ? 'email' : col.type === 'phone' ? 'tel' : 'text'}
                                            disabled={isReadOnly || isDeselected}
                                            value={row[col.name] || ''}
                                            onChange={(e) => updateTableCell(field.id, rowIdx, col.name, e.target.value)}
                                            style={{ width: '90%', padding: '4px 6px', borderRadius: 4, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-sidebar-icon-bg)', color: 'var(--c-text)' }}
                                          />
                                        </td>
                                      );
                                    })}
                                    {field.attachmentType === 'per-row' && (
                                      <td style={{ padding: 4 }}>
                                        <button 
                                          disabled={isReadOnly || isDeselected}
                                          onClick={() => alert("Upload Attachment for this row")}
                                          style={{ padding: '2px 6px', borderRadius: 4, background: 'var(--c-sidebar-icon-bg)', border: '1px solid var(--c-sidebar-icon-border)', color: 'var(--c-text)', fontSize: 11, cursor: 'pointer' }}
                                        >
                                          📎 Attach
                                        </button>
                                      </td>
                                    )}
                                  </tr>
                                ))}
                              </tbody>
                            </table>

                            {/* Table level attachment & add row buttons */}
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                              {!isReadOnly && !isDeselected && (
                                <button
                                  onClick={() => addTableRow(field.id, field.columns || [])}
                                  style={{ padding: '4px 8px', borderRadius: 4, background: 'transparent', border: '1px dashed #3b82f6', color: '#3b82f6', cursor: 'pointer', fontSize: 11 }}
                                >
                                  + Add Table Row
                                </button>
                              )}

                              {field.attachmentType === 'per-table' && !isDeselected && (
                                <button
                                  disabled={isReadOnly}
                                  onClick={() => alert("Upload one attachment for this entire table")}
                                  style={{ padding: '4px 8px', borderRadius: 4, background: '#3b82f615', border: '1px solid #3b82f630', color: '#3b82f6', cursor: 'pointer', fontSize: 11 }}
                                >
                                  📎 Upload Table PDF Attachment
                                </button>
                              )}
                            </div>
                          </div>
                        ) : field.type === 'textarea' ? (
                          <textarea
                            disabled={isReadOnly || isDeselected}
                            value={previewData[field.id] || ''}
                            onChange={(e) => setPreviewData({ ...previewData, [field.id]: e.target.value })}
                            placeholder={isReadOnly ? `Locked. Controlled by ${field.role.toUpperCase()}` : "Enter response..."}
                            style={{ width: '95%', minHeight: 60, padding: 8, borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13 }}
                          />
                        ) : (
                          <input
                            type={field.type}
                            disabled={isReadOnly || isDeselected}
                            value={previewData[field.id] || ''}
                            onChange={(e) => setPreviewData({ ...previewData, [field.id]: e.target.value })}
                            placeholder={isReadOnly ? `Locked. Controlled by ${field.role.toUpperCase()}` : "Enter response..."}
                            style={{ width: '95%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--c-sidebar-icon-border)', background: 'var(--c-bg)', color: 'var(--c-text)', fontSize: 13 }}
                          />
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </Card>

            {/* SQLAlchemy dynamic classes generator view */}
            <Card title="3. Live Model Classes & Schemas" description="Python SQLAlchemy DB Classes compiled dynamically from visual configurations.">
              <pre style={{
                background: '#0f172a', color: '#34d399', padding: 16, borderRadius: 8,
                fontSize: 12, fontFamily: 'monospace', overflow: 'auto', maxHeight: 200, margin: 0,
                border: '1px solid #34d39930'
              }}>
                <code>{generateSqlAlchemyClasses()}</code>
              </pre>
            </Card>
          </div>
        </div>
      ) : activeTab === 'reporting-lines' ? (
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
      ) : activeTab === 'workflow-sim' ? (
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
                return (
                  <div key={step.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{
                      padding: '8px 12px', borderRadius: 8, fontWeight: 600, fontSize: 12,
                      background: isActive ? '#3b82f6' : isCompleted ? '#10b981' : 'var(--c-bg)',
                      color: isActive || isCompleted ? '#ffffff' : 'var(--c-sidebar-muted)',
                      border: `1px solid ${isActive ? '#3b82f6' : isCompleted ? '#10b981' : 'var(--c-sidebar-icon-border)'}`,
                      boxShadow: isActive ? '0 0 12px rgba(59, 130, 246, 0.4)' : 'none',
                      transition: 'all 0.3s ease'
                    }}>
                      {step.label}
                    </div>
                    {idx < currentWorkflow.length - 1 && (
                      <span style={{ color: 'var(--c-sidebar-muted)', fontWeight: 700 }}>➔</span>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Simulation controls */}
            <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
              {!simRunning ? (
                <button onClick={startSimulation} className={pBtn} style={{ flex: 1 }}>
                  Begin Mock Route Flow
                </button>
              ) : (
                <>
                  <button onClick={() => advanceSimulation(true)} className={pBtn} style={{ flex: 2, background: '#10b981' }}>
                    Mock Action: Approve Step
                  </button>
                  <button onClick={() => advanceSimulation(false)} className={oBtn} style={{ flex: 1, borderColor: '#ef4444', color: '#ef4444' }}>
                    Mock Action: Reject
                  </button>
                </>
              )}
            </div>

            {/* Simulation Logs */}
            <div style={{
              background: '#0f172a', color: '#38bdf8', fontFamily: 'monospace',
              padding: 16, borderRadius: 8, fontSize: 12, minHeight: 150, maxHeight: 200, overflowY: 'auto'
            }}>
              <div style={{ color: '#94a3b8', borderBottom: '1px solid #1e293b', paddingBottom: 4, marginBottom: 8, fontWeight: 600 }}>
                Live Simulation Output Console
              </div>
              {simLogs.length === 0 ? (
                <div style={{ color: '#64748b' }}>Waiting to begin mock route...</div>
              ) : (
                simLogs.map((log, i) => <div key={i} style={{ marginBottom: 4 }}>{log}</div>)
              )}
            </div>
          </Card>
        </div>
      ) : (
        /* Deploy & Export Tab */
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: 24 }}>
          {/* Configs File Viewer */}
          <Card title="1. Auto-Generated Deployment Configs" description="View custom code snippets generated automatically for the active school configuration.">
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
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
                onClick={() => setSelectedConfigType('schema')}
                style={{
                  padding: '6px 12px', borderRadius: 6, cursor: 'pointer', border: 'none', fontSize: 12, fontWeight: 600,
                  background: selectedConfigType === 'schema' ? '#3b82f6' : 'var(--c-sidebar-icon-bg)',
                  color: selectedConfigType === 'schema' ? '#fff' : 'var(--c-sidebar-muted)'
                }}
              >
                college_migrations.sql
              </button>
            </div>

            <pre style={{
              background: '#0f172a', color: '#e2e8f0', padding: 16, borderRadius: 8,
              fontSize: 12.5, fontFamily: 'monospace', overflow: 'auto', maxHeight: '50vh', margin: 0
            }}>
              <code>{CONFIGS_TEMPLATES[selectedConfigType]}</code>
            </pre>
          </Card>

          {/* Checklist & Mock Exporter */}
          <Card title="2. Compile Client Bundle" description="Package custom settings and export a clean installation zip.">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{
                padding: 12, borderRadius: 8, background: '#3b82f612', border: '1px solid #3b82f625',
                fontSize: 13, color: 'var(--c-text)', lineHeight: 1.5
              }}>
                <strong>Compilation Mode:</strong> SoCSEA (Engineering) App Bundle<br/>
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
        </div>
      )}
    </div>
  );
}
