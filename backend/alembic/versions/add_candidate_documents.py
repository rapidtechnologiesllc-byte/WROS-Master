import logging
"""Add candidate_documents table

Revision ID: add_candidate_documents
Revises: 
Create Date: 2026-02-03 10:12:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'add_candidate_documents'
down_revision = None  # Update this to your latest migration
branch_labels = None
depends_on = None

def upgrade():
    """Create candidate_documents table"""
    op.create_table(
        'candidate_documents',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('candidate_id', sa.String(length=50), nullable=False),
        sa.Column('document_type', sa.String(length=50), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('stored_filename', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('file_extension', sa.String(length=10), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        
        # SharePoint information
        sa.Column('sharepoint_url', sa.Text(), nullable=True),
        sa.Column('sharepoint_file_id', sa.String(length=255), nullable=True),
        sa.Column('sharepoint_folder_path', sa.String(length=500), nullable=True),
        
        # Security and validation
        sa.Column('is_virus_scanned', sa.Boolean(), default=False),
        sa.Column('virus_scan_result', sa.String(length=50), nullable=True),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('verified_by', sa.String(length=50), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        
        # Versioning
        sa.Column('version', sa.Integer(), default=1),
        sa.Column('is_latest', sa.Boolean(), default=True),
        sa.Column('replaced_by', sa.Integer(), nullable=True),
        
        # Audit trail
        sa.Column('uploaded_by', sa.String(length=50), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), default=False),
        
        # Additional metadata
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('tags', sa.String(length=500), nullable=True),
        
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        
        # Foreign keys
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidateID'], ),
        sa.ForeignKeyConstraint(['verified_by'], ['users.UserID'], ),
        sa.ForeignKeyConstraint(['replaced_by'], ['candidate_documents.id'], ),
    )
    
    # Create indexes
    op.create_index('ix_candidate_documents_id', 'candidate_documents', ['id'])
    op.create_index('ix_candidate_documents_candidate_id', 'candidate_documents', ['candidate_id'])
    op.create_index('ix_candidate_documents_document_type', 'candidate_documents', ['document_type'])
    op.create_index('ix_candidate_documents_is_latest', 'candidate_documents', ['is_latest'])
    op.create_index('ix_candidate_documents_is_deleted', 'candidate_documents', ['is_deleted'])

def downgrade():
    """Drop candidate_documents table"""
    op.drop_index('ix_candidate_documents_is_deleted', table_name='candidate_documents')
    op.drop_index('ix_candidate_documents_is_latest', table_name='candidate_documents')
    op.drop_index('ix_candidate_documents_document_type', table_name='candidate_documents')
    op.drop_index('ix_candidate_documents_candidate_id', table_name='candidate_documents')
    op.drop_index('ix_candidate_documents_id', table_name='candidate_documents')
    op.drop_table('candidate_documents')
