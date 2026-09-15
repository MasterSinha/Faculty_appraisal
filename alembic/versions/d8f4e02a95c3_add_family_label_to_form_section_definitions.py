"""add family_label to form_section_definitions

Revision ID: d8f4e02a95c3
Revises: c7e3f91d84b2
Create Date: 2026-09-15 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd8f4e02a95c3'
down_revision: Union[str, Sequence[str], None] = 'c7e3f91d84b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("form_section_definitions")}
    if "family_label" not in existing_cols:
        op.add_column(
            "form_section_definitions",
            sa.Column("family_label", sa.String(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("form_section_definitions", "family_label")
