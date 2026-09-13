"""add part_guideline to form_section_definitions

Revision ID: c7e3f91d84b2
Revises: a5f80bcfb86a
Create Date: 2026-09-13 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c7e3f91d84b2'
down_revision: Union[str, Sequence[str], None] = 'a5f80bcfb86a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("form_section_definitions")}
    if "part_guideline" not in existing_cols:
        op.add_column(
            "form_section_definitions",
            sa.Column("part_guideline", sa.String(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("form_section_definitions", "part_guideline")
