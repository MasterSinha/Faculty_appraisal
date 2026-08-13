export const INITIAL_SCHOOL_FORMS = {
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
        { name: 'Amount Sanctioned', type: 'number', maxMarks: 40, aggregate: 'sum' },
        { name: 'Overhead Received', type: 'number', maxMarks: 10, aggregate: 'sum' },
        { name: 'Total Project Value', type: 'formula', formulaExpr: 'Amount Sanctioned + Overhead Received', maxMarks: 50, aggregate: 'sum' },
        { name: 'Status', type: 'dropdown', options: 'Ongoing, Completed, Approved' },
        { name: 'Co-Principal Investigator?', type: 'checkbox' }
      ],
      isOptional: true,
      attachmentType: 'per-row',
      access: 'full'
    },
    { id: 'f3', label: 'Peer Review & Behavior Grid', type: 'table', part: 'Part C', role: 'hod', columns: [{ name: 'Integrity Rating', type: 'dropdown', options: 'Outstanding, Good, Average' }, { name: 'Collaboration', type: 'text' }, { name: 'Senior Remarks', type: 'text' }], isOptional: false, attachmentType: 'none', access: 'reviewer-edit' }
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
      isOptional: false,
      attachmentType: 'per-table',
      access: 'full'
    }
  ],
  Custom: []
};

export const INITIAL_MOCK_FACULTY = [
  { email: 'faculty1@univ.edu', name: 'Dr. Alan Turing', assignedHod: 'hod1@univ.edu' },
  { email: 'faculty2@univ.edu', name: 'Dr. Grace Hopper', assignedHod: 'hod2@univ.edu' }
];

export const INITIAL_MOCK_HODS = [
  { email: 'hod1@univ.edu', name: 'HOD Computer Science (CS)' },
  { email: 'hod2@univ.edu', name: 'HOD Computer Engineering (CE)' }
];

export const INITIAL_SCHOOL_WORKFLOWS = {
  SoCSEA: [
    { id: 'w1', label: 'Faculty Submission' },
    { id: 'w2', label: 'Assigned HOD Review' },
    { id: 'w3', label: 'Director Review' },
    { id: 'w4', label: 'Dean Approval' },
    { id: 'w5', label: 'VC Finalization' }
  ],
  SoD: [
    { id: 'ws1', label: 'Faculty Submission' },
    { id: 'ws2', label: 'Director Review' },
    { id: 'ws3', label: 'Dean Approval' },
    { id: 'ws4', label: 'VC Finalization' }
  ],
  Custom: [
    { id: 'c1', label: 'Faculty Submission' },
    { id: 'c2', label: 'VC Finalization' }
  ]
};

export const MOCK_WORKFLOW_STEPS = [
  { step: 0, desc: 'Faculty starts draft submission, uploads optional/required tables.' },
  { step: 1, desc: 'Faculty marks draft as completed. System locks self appraisal data and updates status to PENDING HOD.' },
  { step: 2, desc: 'HOD reviewer opens the workflow, fills HOD remarks section, and rates behavior metrics.' },
  { step: 3, desc: 'HOD signs with token. System copies total and forwards file to Director.' },
  { step: 4, desc: 'Director reviews, signs appraisal. State transfers to Dean.' },
  { step: 5, desc: 'Dean inspects marks, logs approval status.' },
  { step: 6, desc: 'VC runs final score calculations and commits cycle data to active history database.' }
];

export const SEC_COLORS = [
  '#3b82f6', // general      — blue
  '#10b981', // academic     — green
  '#f59e0b', // research     — amber
  '#ec4899', // behavior     — pink
  '#8b5cf6', // overall      — violet
  '#94a3b8', // Settings      — slate
];

export const getConfigsTemplates = (selectedSchool, currentFields) => {
  return {
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
};
