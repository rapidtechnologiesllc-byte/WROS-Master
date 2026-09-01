"""
SLM Encryption Models

Database tables for encrypted SLM data and decryption access logs.
All sensitive data is encrypted at rest and only decrypted with permission checks.

Tables:
- SalarySensitiveData: Encrypted salary bands (min/max by region)
- DecryptionAccessLog: Audit trail of all decryption requests
- EncryptionKeyMetadata: Key rotation tracking

All data is encrypted using Fernet (symmetric encryption).
Only authorized users can decrypt based on role/permission checks.
"""

from datetime import datetime
from sqlalchemy import Column, String, Float, Date, DateTime, Boolean, JSON, func
from sqlalchemy.ext.declarative import declarative_base

from app.models.base import Base


class SalarySensitiveData(Base):
    """
    Encrypted salary band lookup table.

    Instead of storing actual min/max salary in SLMJobMetadata,
    we store salary_band_id which references this encrypted table.

    Only CEO, Finance, HR, BU Heads can decrypt these values.
    """

    __tablename__ = "salary_sensitive_data"

    salary_band_id = Column(String(36), primary_key=True)  # BAND_001, BAND_002, etc.
    min_salary = Column(String, nullable=False)  # Encrypted float
    max_salary = Column(String, nullable=False)  # Encrypted float
    currency = Column(String(10), nullable=False)  # USD, EUR, GBP (not encrypted - needed for display)
    region = Column(String(100), nullable=True)  # Encrypted region name (optional)
    effective_date = Column(Date, nullable=True)  # When this band became active
    is_active = Column(Boolean, default=True)  # Is this band currently in use?

    # Metadata
    created_at = Column(DateTime, default=func.now())
    created_by = Column(String(50), nullable=True)  # User ID who created band
    last_updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class DecryptionAccessLog(Base):
    """
    Audit log for all decryption operations.

    Tracks every attempt to decrypt sensitive data:
    - Who decrypted it
    - What field was decrypted (salary, job_title, etc.)
    - When (timestamp)
    - Whether it succeeded or was denied

    Used for:
    - Compliance audits (who accessed what)
    - Security monitoring (unusual access patterns)
    - Debugging (tracing decryption errors)
    """

    __tablename__ = "decryption_access_log"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(50), nullable=False, index=True)  # User making request
    field_type = Column(String(100), nullable=False, index=True)  # salary, job_title, job_description, feedback
    value_preview = Column(String(50), nullable=True)  # First 20 chars of encrypted value (for tracking)
    action = Column(String(100), nullable=False)  # DECRYPT_SALARY, DECRYPT_JOB_TITLE, etc.
    success = Column(Boolean, nullable=False)  # Was decryption allowed/successful?
    reason_if_denied = Column(String(255), nullable=True)  # Why was it denied?
    timestamp = Column(DateTime, default=func.now(), index=True, nullable=False)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6 for tracking
    user_agent = Column(String(255), nullable=True)  # Browser/client info


class EncryptionKeyMetadata(Base):
    """
    Metadata for encryption key management.

    Tracks:
    - Which keys are in use (active)
    - When keys were last rotated
    - Which services have which keys

    Enables:
    - Key rotation tracking
    - Identifying outdated keys
    - Permission-based key access
    """

    __tablename__ = "encryption_key_metadata"

    key_id = Column(String(36), primary_key=True)
    field_type = Column(String(100), nullable=False, unique=True)  # salary, job_title, job_description, feedback, general
    service_name = Column(String(100), nullable=True)  # slm, flash, ceo_dashboard (optional)
    is_active = Column(Boolean, default=True)  # Is this key currently in use?
    last_rotated = Column(DateTime, nullable=True)  # When was key last rotated?
    rotation_schedule = Column(String(50), nullable=True)  # 90days, 6months, annual, etc.
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=True)  # When does this key expire?
    parent_key_id = Column(String(36), nullable=True)  # If re-keyed, link to old key


class EncryptedSLMJobMetadata(Base):
    """
    Extended SLMJobMetadata with encrypted fields.

    This supplements the existing SLMJobMetadata table:
    - job_id: Same as in SLMJobMetadata (reference only)
    - job_title: Encrypted (confidential role info)
    - job_description: Encrypted (business strategy)
    - required_skills: Encrypted (strategic skill gaps)
    - experience_level: Encrypted (internal hierarchy)
    - salary_band_id: Reference to SalarySensitiveData table (encrypted separately)

    Aggregated metrics remain unencrypted:
    - candidates_submitted, interviewed, hired, etc.
    - hire_success_rate, time_to_hire, etc.

    Access by role:
    - CEO: Full access to all encrypted fields
    - Finance: Salary band only
    - HR: All encrypted fields
    - BU Head: All encrypted fields (own BU only)
    - Manager: No encrypted access
    - Thunder: No access (works with encrypted data)
    """

    __tablename__ = "encrypted_slm_job_metadata"

    id = Column(String(36), primary_key=True)
    job_id = Column(String(50), nullable=False, unique=True, index=True)  # FK to jobs table

    # Encrypted fields (stored as encrypted strings in DB)
    encrypted_job_title = Column(String, nullable=False)  # Encrypted
    encrypted_job_description = Column(String, nullable=True)  # Encrypted
    encrypted_required_skills = Column(String, nullable=True)  # Encrypted JSON array
    encrypted_experience_level = Column(String, nullable=True)  # Encrypted

    # Salary band reference (min/max salary encrypted separately)
    salary_band_id = Column(String(36), nullable=True)  # FK to SalarySensitiveData

    # Un-encrypted aggregated metrics (safe for SLM/Thunder)
    candidates_submitted = Column(JSON, nullable=True)  # Aggregated count
    candidates_interviewed = Column(JSON, nullable=True)
    candidates_hired = Column(JSON, nullable=True)
    hire_success_rate = Column(Float, nullable=True)

    # Access tracking
    created_at = Column(DateTime, default=func.now())
    created_by = Column(String(50), nullable=True)
    last_accessed_by = Column(String(50), nullable=True)
    last_accessed_at = Column(DateTime, nullable=True)


class EncryptedSLMFeedback(Base):
    """
    Extended SLMFeedback with encrypted fields.

    This supplements the existing SLMFeedback table:
    - feedback_session_id: Anonymized (OK to expose)
    - field_name: Field type like "skills", "title" (OK to expose)
    - parsed_value: Encrypted (what SLM extracted)
    - corrected_value: Encrypted (recruiter's correction)
    - correction_context: Encrypted (why it was wrong)
    - confidence_score: Not encrypted (metric only)
    - feedback_type: Not encrypted (category only)

    Only Manager, HR, CEO can decrypt feedback data.
    """

    __tablename__ = "encrypted_slm_feedback"

    id = Column(String(36), primary_key=True)
    feedback_session_id = Column(String(100), nullable=False, index=True)  # Anonymized session
    field_name = Column(String(100), nullable=False, index=True)  # OK to expose: skills, title, etc.

    # Encrypted fields
    encrypted_parsed_value = Column(String, nullable=True)  # What SLM extracted
    encrypted_corrected_value = Column(String, nullable=True)  # Recruiter's fix
    encrypted_correction_context = Column(String, nullable=True)  # Why was it wrong?

    # Un-encrypted fields (metrics only)
    confidence_score = Column(Float, nullable=True)  # 0-1
    feedback_type = Column(String(50), nullable=True)  # correction, validation, edge_case

    # Audit trail
    created_at = Column(DateTime, default=func.now())
    created_by = Column(String(50), nullable=True)  # Recruiter who made correction
    flagged_for_review = Column(Boolean, default=False)  # Does this correction need review?
