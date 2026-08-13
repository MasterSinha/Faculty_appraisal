import { useState, useRef, useEffect } from 'react';
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
  const [activePreviewTab, setActivePreviewTab] = useState('Part A');
  const [editingFieldId, setEditingFieldId] = useState(null);
  const [editingColumn, setEditingColumn] = useState(null);

  // Reset active preview tab if school changes
  useEffect(() => {
    setActivePreviewTab('Part A');
    setEditingFieldId(null);
  }, [selectedSchool]);

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
`,
    routes: `# ===========================================================================
# Auto-Generated Optimized & Paginated Backend Routes for School: ${selectedSchool}
# ===========================================================================
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from src.setup.database import get_db
from src.setup.dependencies import CurrentUser

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/subordinates")
async def get_subordinates(
    current_user: CurrentUser,
    academic_year: str = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Optimized:
    1. Returns flat total scores without loading massive snapshot payloads.
    2. Implements server-side list pagination using offset/limit.
    """
    offset = (page - 1) * limit
    
    # Query summary records with offset and limit
    query = (
        select(FacultyProfile, ${selectedSchool}Declaration)
        .join(${selectedSchool}Declaration, FacultyProfile.email == ${selectedSchool}Declaration.faculty_email)
        .where(${selectedSchool}Declaration.academic_year == academic_year)
        .offset(offset)
        .limit(limit)
    )
    
    # Fetch total count for pagination metadata
    count_query = (
        select(func.count(FacultyProfile.id))
        .join(${selectedSchool}Declaration, FacultyProfile.email == ${selectedSchool}Declaration.faculty_email)
        .where(${selectedSchool}Declaration.academic_year == academic_year)
    )
    
    total_count = (await db.execute(count_query)).scalar() or 0
    results = (await db.execute(query)).all()
    
    subordinates = []
    for faculty, decl in results:
        subordinates.append({
            "email": faculty.email,
            "name": faculty.full_name,
            "status": decl.status,
            "part_a_total": float(decl.part_a_total) if decl.part_a_total else 0.0,
        })
        
    return {
        "data": subordinates,
        "pagination": {
            "total_items": total_count,
            "page": page,
            "limit": limit,
            "total_pages": (total_count + limit - 1) // limit
        }
    }
`
  };

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
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 0.6fr', gap: 24 }}>
          {/* Combined Visual Form Designer & Live Simulation */}
          <div>
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
                  onClick={() => {
                    const id = Date.now().toString();
                    const newField = {
                      id, label: `New Text Field ${currentFields.length + 1}`, type: 'text',
                      part: activePreviewTab, role: 'faculty', required: false, columns: [],
                      tableMaxMarks: 0, rowMaxMarks: 0, isOptional: false, attachmentType: 'none', access: 'full'
                    };
                    setSchoolForms({ ...schoolForms, [selectedSchool]: [...currentFields, newField] });
                    setEditingFieldId(id);
                  }}
                  style={{ padding: '10px 16px', borderRadius: 8, border: 'none', background: '#3b82f615', color: '#3b82f6', fontWeight: 600, fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  ➕ Add Text Field
                </button>

                <button
                  onClick={() => {
                    const id = Date.now().toString();
                    const newField = {
                      id, label: `New Number Field ${currentFields.length + 1}`, type: 'number',
                      part: activePreviewTab, role: 'faculty', required: false, columns: [],
                      tableMaxMarks: 50, rowMaxMarks: 10, isOptional: false, attachmentType: 'none', access: 'full'
                    };
                    setSchoolForms({ ...schoolForms, [selectedSchool]: [...currentFields, newField] });
                    setEditingFieldId(id);
                  }}
                  style={{ padding: '10px 16px', borderRadius: 8, border: 'none', background: '#10b98115', color: '#10b981', fontWeight: 600, fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  ➕ Add Number Field
                </button>

                <button
                  onClick={() => {
                    const id = Date.now().toString();
                    const newField = {
                      id, label: `New Table Grid ${currentFields.length + 1}`, type: 'table',
                      part: activePreviewTab, role: 'faculty', required: false,
                      columns: [
                        { name: 'Item Name', type: 'text' },
                        { name: 'Marks', type: 'number' }
                      ],
                      tableMaxMarks: 100, rowMaxMarks: 20, isOptional: false, attachmentType: 'per-row', access: 'full'
                    };
                    setSchoolForms({ ...schoolForms, [selectedSchool]: [...currentFields, newField] });
                    setEditingFieldId(id);
                  }}
                  style={{ padding: '10px 16px', borderRadius: 8, border: 'none', background: '#a78bfa15', color: '#a78bfa', fontWeight: 600, fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  ➕ Add Table Grid
                </button>
              </div>
            </Card>
          </div>

          {/* Quick actions & Dynamic Model schema visualizer */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <Card title="Quick Actions" description="Cloning templates & raw Schema details.">
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

            <Card title="Dynamic Model Classes" description="SQLAlchemy Python classes generated dynamically based on active designer state.">
              <pre style={{
                background: '#0f172a', color: '#34d399', padding: 16, borderRadius: 8,
                fontSize: 12, fontFamily: 'monospace', overflow: 'auto', maxHeight: 300, margin: 0,
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
