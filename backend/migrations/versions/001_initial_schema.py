"""initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-10-04 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == 'postgresql'

    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Organizations
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Users
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('org_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='member'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_users_org_id', 'users', ['org_id'])
    op.create_index('ix_users_email', 'users', ['email'])

    # Teams
    op.create_table(
        'teams',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('org_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
    )
    op.create_index('ix_teams_org_id', 'teams', ['org_id'])

    # Team Members
    op.create_table(
        'team_members',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('team_id', sa.String(36), sa.ForeignKey('teams.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    )
    op.create_index('ix_team_members_team_id', 'team_members', ['team_id'])
    op.create_index('ix_team_members_user_id', 'team_members', ['user_id'])

    # API Keys
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False),
        sa.Column('prefix', sa.String(16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_api_keys_user_id', 'api_keys', ['user_id'])
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'])

    # Documents
    op.create_table(
        'documents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('org_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('team_id', sa.String(36), sa.ForeignKey('teams.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('visibility', sa.String(50), nullable=False, server_default='private'),
        sa.Column('status', sa.String(50), nullable=False, server_default='processed'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_documents_org_id', 'documents', ['org_id'])
    op.create_index('ix_documents_owner_id', 'documents', ['owner_id'])
    op.create_index('ix_documents_team_id', 'documents', ['team_id'])

    # Chunks
    if is_postgres:
        op.create_table(
            'chunks',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
            sa.Column('org_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('chunk_index', sa.Integer(), nullable=False),
            sa.Column('page', sa.Integer(), nullable=True),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('embedding', pgvector.sqlalchemy.Vector(384), nullable=True),
            sa.Column('tsv', postgresql.TSVECTOR(), nullable=True),
        )
        op.execute("CREATE INDEX IF NOT EXISTS ix_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);")
        op.execute("CREATE INDEX IF NOT EXISTS ix_chunks_tsv ON chunks USING gin (tsv);")
    else:
        op.create_table(
            'chunks',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
            sa.Column('org_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('chunk_index', sa.Integer(), nullable=False),
            sa.Column('page', sa.Integer(), nullable=True),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('embedding', sa.JSON(), nullable=True),
            sa.Column('tsv', sa.Text(), nullable=True),
        )
    op.create_index('ix_chunks_org_id', 'chunks', ['org_id'])
    op.create_index('ix_chunks_document_id', 'chunks', ['document_id'])

    # Query Logs
    op.create_table(
        'query_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('org_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('retrieved_chunk_ids', sa.JSON(), nullable=True),
        sa.Column('scores', sa.JSON(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('provider', sa.String(50), nullable=False, server_default='groq'),
        sa.Column('cache_hit', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('mode', sa.String(50), nullable=False, server_default='standard'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_query_logs_org_id', 'query_logs', ['org_id'])
    op.create_index('ix_query_logs_user_id', 'query_logs', ['user_id'])

    # Feedback
    op.create_table(
        'feedback',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('query_log_id', sa.String(36), sa.ForeignKey('query_logs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_feedback_query_log_id', 'feedback', ['query_log_id'])

    # Eval Cases
    op.create_table(
        'eval_cases',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('org_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('expected_doc_id', sa.String(36), nullable=True),
        sa.Column('expected_answer', sa.Text(), nullable=True),
        sa.Column('source', sa.String(50), nullable=False, server_default='manual'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_eval_cases_org_id', 'eval_cases', ['org_id'])

    # Eval Runs
    op.create_table(
        'eval_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('org_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('hit_at_k', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('mrr', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('faithfulness', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('p50_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('p95_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_eval_runs_org_id', 'eval_runs', ['org_id'])

    # Eval Results
    op.create_table(
        'eval_results',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('eval_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('eval_cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('hit', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('faithfulness', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('latency_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('answer', sa.Text(), nullable=True),
    )
    op.create_index('ix_eval_results_run_id', 'eval_results', ['run_id'])
    op.create_index('ix_eval_results_case_id', 'eval_results', ['case_id'])

    # Response Cache
    op.create_table(
        'response_cache',
        sa.Column('key', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('citations', sa.JSON(), nullable=True),
        sa.Column('corpus_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_response_cache_user_id', 'response_cache', ['user_id'])


def downgrade() -> None:
    op.drop_table('response_cache')
    op.drop_table('eval_results')
    op.drop_table('eval_runs')
    op.drop_table('eval_cases')
    op.drop_table('feedback')
    op.drop_table('query_logs')
    op.drop_table('chunks')
    op.drop_table('documents')
    op.drop_table('api_keys')
    op.drop_table('team_members')
    op.drop_table('teams')
    op.drop_table('users')
    op.drop_table('organizations')
