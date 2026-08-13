import { createContext, useContext, useState, useEffect } from 'react';
import { 
  INITIAL_SCHOOL_FORMS, 
  INITIAL_MOCK_FACULTY, 
  INITIAL_MOCK_HODS, 
  INITIAL_SCHOOL_WORKFLOWS 
} from './schemaTemplates';

const SandboxContext = createContext(null);

export function SandboxProvider({ children }) {
  const [activeTab, setActiveTab] = useState('form-builder');
  const [selectedSchool, setSelectedSchool] = useState('SoCSEA');

  // School Form Templates
  const [schoolForms, setSchoolForms] = useState(INITIAL_SCHOOL_FORMS);
  
  // School Form Guidelines / Descriptions
  const [schoolDescriptions, setSchoolDescriptions] = useState({
    SoCSEA: 'Engineering Faculty Self Appraisal: Please fill Parts A through D. Attach PDF proofs for all journal listings and research project grants.',
    SoD: 'Design Faculty Appraisal: Focus on exhibition listings, design portfolio URLs, and creative workshop conduct.',
    Custom: ''
  });
  
  // Faculty reporting lines state
  const [mockFaculty, setMockFaculty] = useState(INITIAL_MOCK_FACULTY);
  const [mockHods, setMockHods] = useState(INITIAL_MOCK_HODS);
  const [selectedFacultySim, setSelectedFacultySim] = useState('faculty1@univ.edu');

  // Workflows
  const [schoolWorkflows, setSchoolWorkflows] = useState(INITIAL_SCHOOL_WORKFLOWS);

  // Simulation state
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

  // Keep track of deselected optional tables
  const [disabledSections, setDisabledSections] = useState({});

  // Inline editors state
  const [editingFieldId, setEditingFieldId] = useState(null);
  const [editingColumn, setEditingColumn] = useState(null);

  // Configuration scripts tab state
  const [selectedConfigType, setSelectedConfigType] = useState('docker');
  const [activePreviewTab, setActivePreviewTab] = useState('Part A');

  // Reset active preview tab and editor state if school changes
  useEffect(() => {
    setActivePreviewTab('Part A');
    setEditingFieldId(null);
  }, [selectedSchool]);

  const currentFields = schoolForms[selectedSchool] || [];
  const currentWorkflow = schoolWorkflows[selectedSchool] || [];

  // Workflow actions
  const updateWorkflowStepLabel = (id, val) => {
    setSchoolWorkflows({
      ...schoolWorkflows,
      [selectedSchool]: currentWorkflow.map(s => s.id === id ? { ...s, label: val } : s)
    });
  };

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

  const deleteWorkflowStep = (id) => {
    setSchoolWorkflows({
      ...schoolWorkflows,
      [selectedSchool]: currentWorkflow.filter(s => s.id !== id)
    });
  };

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

  // Actions
  const cloneFromSchool = (schoolKey) => {
    if (!INITIAL_SCHOOL_FORMS[schoolKey]) return;
    setSchoolForms({
      ...schoolForms,
      [selectedSchool]: JSON.parse(JSON.stringify(INITIAL_SCHOOL_FORMS[schoolKey]))
    });
    setSchoolWorkflows({
      ...schoolWorkflows,
      [selectedSchool]: JSON.parse(JSON.stringify(INITIAL_SCHOOL_WORKFLOWS[schoolKey]))
    });
    setPreviewData({});
  };

  const addField = (type) => {
    const id = Date.now().toString();
    const isTable = type === 'table';
    const isNumber = type === 'number';
    
    const newField = {
      id,
      label: `New ${type.toUpperCase()} Field ${currentFields.length + 1}`,
      type,
      part: activePreviewTab,
      role: 'faculty',
      required: false,
      columns: isTable ? [
        { name: 'Item Name', type: 'text' },
        { name: 'Marks', type: 'number' }
      ] : [],
      tableMaxMarks: isTable ? 100 : (isNumber ? 50 : 0),
      rowMaxMarks: isTable ? 20 : (isNumber ? 10 : 0),
      isOptional: false,
      attachmentType: isTable ? 'per-row' : 'none',
      access: 'full'
    };

    setSchoolForms({
      ...schoolForms,
      [selectedSchool]: [...currentFields, newField]
    });
    setEditingFieldId(id);
  };

  const updateField = (fieldId, prop, val) => {
    setSchoolForms({
      ...schoolForms,
      [selectedSchool]: currentFields.map(f => {
        if (f.id === fieldId) {
          return { ...f, [prop]: val };
        }
        return f;
      })
    });
  };

  const deleteField = (fieldId) => {
    setSchoolForms({
      ...schoolForms,
      [selectedSchool]: currentFields.filter(f => f.id !== fieldId)
    });
  };

  const addTableColumn = (fieldId, columnObj) => {
    setSchoolForms({
      ...schoolForms,
      [selectedSchool]: currentFields.map(f => {
        if (f.id === fieldId) {
          const cols = f.columns || [];
          return { ...f, columns: [...cols, columnObj] };
        }
        return f;
      })
    });
  };

  const updateTableColumn = (fieldId, colIdx, columnObj) => {
    setSchoolForms({
      ...schoolForms,
      [selectedSchool]: currentFields.map(f => {
        if (f.id === fieldId) {
          const cols = [...(f.columns || [])];
          cols[colIdx] = columnObj;
          return { ...f, columns: cols };
        }
        return f;
      })
    });
  };

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

  const addTableRow = (fieldId, cols) => {
    const emptyRow = {};
    cols.forEach(c => {
      emptyRow[c.name] = c.type === 'checkbox' ? 'false' : '';
    });
    const existing = previewTables[fieldId] || [];
    setPreviewTables({
      ...previewTables,
      [fieldId]: [...existing, emptyRow]
    });
  };

  const updateTableCell = (fieldId, rowIdx, colName, value) => {
    const existing = [...(previewTables[fieldId] || [])];
    if (existing[rowIdx]) {
      existing[rowIdx][colName] = value;
      setPreviewTables({
        ...previewTables,
        [fieldId]: existing
      });
    }
  };

  const deletePreviewTableRow = (fieldId, rowIdx) => {
    const existing = [...(previewTables[fieldId] || [])];
    existing.splice(rowIdx, 1);
    setPreviewTables({
      ...previewTables,
      [fieldId]: existing
    });
  };

  const calculateTotalMaxMarks = () => {
    let sum = 0;
    currentFields.forEach(f => {
      if (disabledSections[f.id]) return;
      if (f.type === 'number') {
        sum += Number(f.rowMaxMarks) || 0;
      } else if (f.type === 'table') {
        (f.columns || []).forEach(c => {
          if (c.type === 'number' || c.type === 'formula') {
            sum += Number(c.maxMarks) || 0;
          }
        });
      }
    });
    return sum;
  };

  const evaluateCellFormula = (formulaExpr, rowObj) => {
    if (!formulaExpr) return 0;
    try {
      let evaluated = formulaExpr;
      Object.keys(rowObj).forEach(key => {
        const val = Number(rowObj[key]) || 0;
        const escapedKey = key.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
        evaluated = evaluated.replace(new RegExp(escapedKey, 'g'), val.toString());
      });
      return Function(`"use strict"; return (${evaluated})`)();
    } catch (e) {
      return 'Error';
    }
  };

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
    ${f.attachmentType !== 'none' ? "attachment_path = Column(String, nullable=True)\\n    " : ""}${(f.columns || []).map(c => {
      let pyType = 'String';
      if (c.type === 'number' || c.type === 'formula') pyType = 'Numeric';
      if (c.type === 'checkbox') pyType = 'Boolean';
      return `${c.name.toLowerCase().replace(/[^a-z0-9]/g, '_')} = Column(${pyType}, nullable=True)`;
    }).join('\\n    ')}
`;
}).join('\\n')}`;
  };

  const logSim = (msg) => {
    setSimLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
  };

  const startSimulation = () => {
    setSimActiveStep(0);
    setSimRunning(true);
    setSimLogs([]);

    const facultyUser = mockFaculty.find(f => f.email === selectedFacultySim);
    if (!facultyUser) return;
    const assignedHodUser = mockHods.find(h => h.email === facultyUser.assignedHod) || { name: 'None', email: '' };

    logSim(`🚀 Initializing workflow for School: ${selectedSchool}`);
    logSim(`Submitting Faculty: ${facultyUser.name} (${facultyUser.email})`);
    logSim(`Target Reporting HOD: ${assignedHodUser.name} (${assignedHodUser.email})`);
    logSim(`Appraisal Form populated with ${currentFields.length} custom fields.`);
  };

  const advanceSimulation = (approve = true) => {
    if (!simRunning) return;
    const currentStep = currentWorkflow[simActiveStep];
    const facultyUser = mockFaculty.find(f => f.email === selectedFacultySim);
    if (!facultyUser) return;
    const assignedHodUser = mockHods.find(h => h.email === facultyUser.assignedHod) || { name: 'None', email: '' };

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

  const handleExportSchema = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({ schoolForms, schoolWorkflows }, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `pbas_custom_schema_${selectedSchool.toLowerCase()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleImportSchema = (e) => {
    const fileReader = new FileReader();
    if (e.target.files && e.target.files[0]) {
      fileReader.readAsText(e.target.files[0], "UTF-8");
      fileReader.onload = (event) => {
        try {
          const parsed = JSON.parse(event.target.result);
          if (parsed.schoolForms) {
            setSchoolForms({
              ...schoolForms,
              [selectedSchool]: parsed.schoolForms[selectedSchool] || parsed.schoolForms.SoCSEA || []
            });
            alert("✅ Form Schema JSON loaded successfully into Visual Canvas!");
          }
        } catch (err) {
          alert("❌ Error: Invalid Schema JSON file");
        }
      };
    }
  };

  return (
    <SandboxContext.Provider value={{
      activeTab, setActiveTab,
      selectedSchool, setSelectedSchool,
      schoolForms, setSchoolForms,
      schoolDescriptions, setSchoolDescriptions,
      mockFaculty, setMockFaculty,
      mockHods, setMockHods,
      selectedFacultySim, setSelectedFacultySim,
      schoolWorkflows, setSchoolWorkflows,
      simActiveStep, setSimActiveStep,
      simLogs, setSimLogs,
      simRunning, setSimRunning,
      simulatedRole, setSimulatedRole,
      previewData, setPreviewData,
      previewTables, setPreviewTables,
      disabledSections, setDisabledSections,
      editingFieldId, setEditingFieldId,
      editingColumn, setEditingColumn,
      selectedConfigType, setSelectedConfigType,
      activePreviewTab, setActivePreviewTab,
      currentFields,
      currentWorkflow,
      cloneFromSchool,
      addField,
      updateField,
      deleteField,
      addTableColumn,
      updateTableColumn,
      removeTableColumn,
      addTableRow,
      updateTableCell,
      deletePreviewTableRow,
      calculateTotalMaxMarks,
      evaluateCellFormula,
      generateSqlAlchemyClasses,
      updateWorkflowStepLabel,
      moveWorkflowStep,
      deleteWorkflowStep,
      addWorkflowStep,
      startSimulation,
      advanceSimulation,
      handleExportSchema,
      handleImportSchema
    }}>
      {children}
    </SandboxContext.Provider>
  );
}

export function useSandbox() {
  const context = useContext(SandboxContext);
  if (!context) throw new Error("useSandbox must be used within a SandboxProvider");
  return context;
}
