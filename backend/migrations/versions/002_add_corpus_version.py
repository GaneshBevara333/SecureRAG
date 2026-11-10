"""Add corpus_version to organizations

Revision ID: 002_add_corpus_version
Revises: 001_initial_schema
Create Date: 2026-10-19
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_add_corpus_version'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'organizations',
        sa.Column('corpus_version', sa.Integer(), nullable=False, server_default='1'),
    )


def downgrade() -> None:
    op.drop_column('organizations', 'corpus_version')
