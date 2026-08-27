"""Add Doctor Agent tracing tables

Revision ID: 2026_08_27_add_doctor_agent_tracing
Revises:
Create Date: 2026-08-27 10:00:00.000000

Doctor Agent Self-Healing Tracing
- doctor_traces: Log every fix attempt (message_id, attempt_num, strategy, success, error, fix_applied)
- doctor_strategies: Configurable fix strategies (admin-editable without code changes)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_08_27_add_doctor_agent_tracing'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create doctor_traces table
    op.create_table(
        'doctor_traces',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('message_id', sa.String(100), nullable=False, index=True),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('strategy_name', sa.String(50), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('fix_applied', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_doctor_traces_message_id', 'doctor_traces', ['message_id'])
    op.create_index('ix_doctor_traces_timestamp', 'doctor_traces', ['timestamp'])
    op.create_index('ix_doctor_traces_message_attempt', 'doctor_traces', ['message_id', 'attempt_number'])
    op.create_index('ix_doctor_traces_failed', 'doctor_traces', ['success', 'timestamp'])

    # Create doctor_strategies table (configurable)
    op.create_table(
        'doctor_strategies',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('config', sa.String(1000), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_doctor_strategy_name')
    )

    # Seed default strategies
    op.execute("""
        INSERT INTO doctor_strategies (name, description, enabled, "order", config) VALUES
        ('ALTERNATIVE_CONTACT', 'Try SMS, LinkedIn DM, WhatsApp instead of email', true, 1, '{"timeout_seconds": 30}'),
        ('DATA_CORRECTION', 'Fetch from CRM, correct typos, validate email/phone', true, 2, '{"max_corrections": 5}'),
        ('SERVICE_RETRY', 'Retry with exponential backoff (1s, 5s, 30s)', true, 3, '{"max_retries": 3, "backoff_strategy": "exponential"}'),
        ('ESCALATE_TO_WROS', 'Create WROS ticket for support team', true, 4, '{"auto_notify_support": true}')
    """)


def downgrade():
    # Drop indexes
    op.drop_index('ix_doctor_traces_failed', table_name='doctor_traces')
    op.drop_index('ix_doctor_traces_message_attempt', table_name='doctor_traces')
    op.drop_index('ix_doctor_traces_timestamp', table_name='doctor_traces')
    op.drop_index('ix_doctor_traces_message_id', table_name='doctor_traces')

    # Drop tables
    op.drop_table('doctor_strategies')
    op.drop_table('doctor_traces')
