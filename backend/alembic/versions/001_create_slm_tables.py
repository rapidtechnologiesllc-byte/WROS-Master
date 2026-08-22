"""Create SLM management tables for real-time learning

Revision ID: 001_slm_tables
Revises:
Create Date: 2026-08-18 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = '001_slm_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create SLM tables"""

    # SLMPattern table - stores pattern definitions
    op.create_table(
        'slm_patterns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('pattern', sa.String(255), nullable=False),
        sa.Column('complexity', sa.String(50), nullable=False),
        sa.Column('lookup_type', sa.String(100), nullable=False),
        sa.Column('usage_count', sa.Integer(), server_default='0'),
        sa.Column('accuracy_percentage', sa.Float(), server_default='100.0'),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('enabled', sa.Boolean(), server_default='true'),
        sa.Column('added_by', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_slm_patterns_tenant_complexity', 'slm_patterns', ['tenant_id', 'complexity'])
    op.create_index('ix_slm_patterns_enabled', 'slm_patterns', ['enabled'])

    # SLMPatternUpdate table - audit log of changes
    op.create_table(
        'slm_pattern_updates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('pattern_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('changes', sa.Text(), nullable=True),
        sa.Column('added_by', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_slm_updates_tenant_action', 'slm_pattern_updates', ['tenant_id', 'action'])

    # SLMQuestionLog table - logs every question
    op.create_table(
        'slm_question_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('candidate_id', sa.String(255), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('pattern_id', sa.Integer(), nullable=True),
        sa.Column('complexity', sa.String(50), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('response_time_ms', sa.Integer(), nullable=False),
        sa.Column('was_accurate', sa.Boolean(), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_slm_logs_tenant_source', 'slm_question_logs', ['tenant_id', 'source'])
    op.create_index('ix_slm_logs_candidate', 'slm_question_logs', ['tenant_id', 'candidate_id'])
    op.create_index('ix_slm_logs_created', 'slm_question_logs', ['created_at'])


def downgrade():
    """Drop SLM tables"""
    op.drop_table('slm_question_logs')
    op.drop_table('slm_pattern_updates')
    op.drop_table('slm_patterns')
