"""add_activity_logs_table

Revision ID: a5f80bcfb86a
Revises: 64c73e873a51
Create Date: 2026-08-25 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = 'a5f80bcfb86a'
down_revision: Union[str, Sequence[str], None] = '64c73e873a51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def safe_create_table(name, *args, **kwargs):
    from alembic import context
    if context.is_offline_mode():
        getattr(op, "create_table")(name, *args, **kwargs)
        return
    conn = op.get_bind()
    import sqlalchemy as sa
    inspector = sa.inspect(conn)
    if name not in inspector.get_table_names():
        getattr(op, "create_table")(name, *args, **kwargs)
    else:
        # Table exists. Self-heal by adding any missing columns.
        existing_cols = {c["name"] for c in inspector.get_columns(name)}
        for arg in args:
            if isinstance(arg, sa.Column):
                if arg.name not in existing_cols:
                    op.add_column(name, arg)


def upgrade() -> None:
    safe_create_table(
        'activity_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('detail', sa.String(), nullable=False),
        sa.Column('meta', JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('academic_year', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Seed activity_logs with historical data from declarations (submissions)
    op.execute("""
        INSERT INTO activity_logs (id, type, title, detail, meta, academic_year, created_at)
        SELECT 
            gen_random_uuid(),
            'submission',
            'Appraisal Submitted',
            f.full_name || ' (' || COALESCE(f.school, '') || ') submitted self-appraisal form',
            json_build_object('email', f.email, 'role', f.appraisal_role, 'school', f.school)::jsonb,
            d.academic_year,
            d.submitted_at
        FROM declarations d
        JOIN faculty_profiles f ON d.faculty_email = f.email
        WHERE d.submitted_at IS NOT NULL;
    """)

    # Seed activity_logs with historical data from appraisal_reviews
    op.execute("""
        INSERT INTO activity_logs (id, type, title, detail, meta, academic_year, created_at)
        SELECT 
            gen_random_uuid(),
            'review',
            'Reviewed by ' || CASE 
                WHEN r.reviewer_role = 'hod' THEN 'HOD'
                WHEN r.reviewer_role = 'center_head' THEN 'Center Head'
                WHEN r.reviewer_role = 'director' THEN 'Director'
                WHEN r.reviewer_role = 'dean' THEN 'Dean'
                WHEN r.reviewer_role = 'vc' THEN 'VC'
                WHEN r.reviewer_role = 'registrar' THEN 'Registrar'
                WHEN r.reviewer_role = 'reporting_officer' THEN 'Reporting Officer'
                ELSE UPPER(r.reviewer_role)
            END,
            CASE 
                WHEN r.status = 'Rejected' THEN 
                    CASE 
                        WHEN r.reviewer_role = 'hod' THEN 'HOD'
                        WHEN r.reviewer_role = 'center_head' THEN 'Center Head'
                        WHEN r.reviewer_role = 'director' THEN 'Director'
                        WHEN r.reviewer_role = 'dean' THEN 'Dean'
                        WHEN r.reviewer_role = 'vc' THEN 'VC'
                        WHEN r.reviewer_role = 'registrar' THEN 'Registrar'
                        WHEN r.reviewer_role = 'reporting_officer' THEN 'Reporting Officer'
                        ELSE UPPER(r.reviewer_role)
                    END || ' (' || r.reviewer_email || ') rejected ' || f.full_name || '''s appraisal form'
                ELSE 
                    CASE 
                        WHEN r.reviewer_role = 'hod' THEN 'HOD'
                        WHEN r.reviewer_role = 'center_head' THEN 'Center Head'
                        WHEN r.reviewer_role = 'director' THEN 'Director'
                        WHEN r.reviewer_role = 'dean' THEN 'Dean'
                        WHEN r.reviewer_role = 'vc' THEN 'VC'
                        WHEN r.reviewer_role = 'registrar' THEN 'Registrar'
                        WHEN r.reviewer_role = 'reporting_officer' THEN 'Reporting Officer'
                        ELSE UPPER(r.reviewer_role)
                    END || ' (' || r.reviewer_email || ') reviewed ' || f.full_name || '''s appraisal form (' || r.status || ')'
            END,
            json_build_object('faculty_email', r.faculty_email, 'reviewer', r.reviewer_email)::jsonb,
            r.academic_year,
            r.reviewed_at
        FROM appraisal_reviews r
        JOIN faculty_profiles f ON r.faculty_email = f.email
        WHERE r.reviewed_at IS NOT NULL;
    """)


def downgrade() -> None:
    op.drop_table('activity_logs')
