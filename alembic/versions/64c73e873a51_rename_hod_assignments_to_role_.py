"""rename_hod_assignments_to_role_assignments

Revision ID: 64c73e873a51
Revises: 7c2cdbc683ef
Create Date: 2026-08-16 18:30:10.261870

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64c73e873a51'
down_revision: Union[str, Sequence[str], None] = '7c2cdbc683ef'
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
    """Upgrade schema."""
    # 1. Create role_assignments table
    safe_create_table(
        'role_assignments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('role_type', sa.String(), nullable=False),
        sa.Column('scope_type', sa.String(), nullable=False),
        sa.Column('scope_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(), nullable=True, server_default='active'),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('academic_year', sa.String(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['faculty_profiles.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['faculty_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    from alembic import context
    if context.is_offline_mode():
        op.drop_table('hod_assignments')
        return
        
    # 2. Migrate existing data from hod_assignments if it exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'hod_assignments' in tables:
        conn.execute(sa.text("""
            INSERT INTO role_assignments (id, role_type, scope_type, scope_id, user_id, status, start_date, academic_year, created_by)
            SELECT id, 'HOD', 'department', CAST(department_id AS VARCHAR), faculty_id, 'active', assigned_at, academic_year, created_by
            FROM hod_assignments
        """))
        
        # 3. Drop old hod_assignments table
        op.drop_table('hod_assignments')


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate hod_assignments table
    safe_create_table(
        'hod_assignments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('faculty_id', sa.UUID(), nullable=False),
        sa.Column('department_id', sa.UUID(), nullable=False),
        sa.Column('academic_year', sa.String(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['faculty_profiles.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['faculty_id'], ['faculty_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    from alembic import context
    if context.is_offline_mode():
        op.drop_table('role_assignments')
        return
        
    # Migrate data back if role_assignments exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'role_assignments' in tables:
        conn.execute(sa.text("""
            INSERT INTO hod_assignments (id, faculty_id, department_id, academic_year, created_by, assigned_at)
            SELECT id, user_id, CAST(scope_id AS UUID), academic_year, created_by, start_date
            FROM role_assignments
            WHERE role_type = 'HOD'
        """))
        
        # Drop role_assignments table
        op.drop_table('role_assignments')
