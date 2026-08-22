# PHASE 2 CRITICAL FIXES — IMPLEMENTATION PLAN

**Status:** READY TO IMPLEMENT  
**Target:** Complete all 6 show-stopper fixes before Phase 3 kickoff  
**Timeline:** 1 day (7 hours estimated)  
**Blocker:** YES — Phase 3 depends on these being completed  

---

## FIX #1: Add R-01 Database Enforcement (15 min)

### Requirement
Hard constraint: candidates.total_experience_months >= 60 or NULL  
Currently: Only application-level gate (can be bypassed with raw SQL)

### Implementation

**Step 1.1: Update Model (app/models/candidate.py)**
```python
# Add to Candidate class definition
experience_floor_check = CheckConstraint(
    "(total_experience_months IS NULL OR total_experience_months >= 60)",
    name="chk_candidate_experience_5yr"
)
```

**Step 1.2: Create Alembic Migration**
```bash
# Generate migration
alembic revision --autogenerate -m "Add R-01 experience floor CHECK constraint"
```

Edit migration file to ensure it adds the constraint:
```python
# In upgrade():
op.create_check_constraint(
    "chk_candidate_experience_5yr",
    "candidates",
    "(total_experience_months IS NULL OR total_experience_months >= 60)"
)

# In downgrade():
op.drop_constraint("chk_candidate_experience_5yr", "candidates")
```

**Step 1.3: Test**
```python
# Test: Try creating candidate with <60 months experience
# Expected: Database constraint violation (sqlalchemy.exc.IntegrityError)

# Test code location: tests/integration/test_candidate_creation.py
def test_experience_floor_constraint():
    candidate = Candidate(
        candidateEmail="test@example.com",
        candidateMobile="1234567890",
        candidatePassword=get_password_hash("pass"),
        employment_type="W2_FULLTIME",
        total_experience_months=36,  # Less than 60
    )
    db.add(candidate)
    with pytest.raises(IntegrityError):
        db.commit()
```

**Checklist:**
- [ ] CheckConstraint added to candidate.py
- [ ] Migration created and tested
- [ ] Test case added to test suite
- [ ] Verified: raw SQL insert with <60 months is rejected

**Effort:** 15 minutes  
**Files Changed:** 3 (model, migration, test)  
**Risk:** LOW — This is a constraint, not logic  

---

## FIX #2: Implement Multi-Field Dedup Service (2 hours)

### Requirement
R-07: createCandidateSafe() must check email + phone + LinkedIn  
Currently: Email only (phone + LinkedIn fields exist but not checked)

### Implementation

**Step 2.1: Create Dedup Service (app/services/dedup_service.py)**
```python
"""
R-07 Multi-Field Duplicate Detection.

Candidate dedup is performed across three identifying fields:
email, phone (with fuzzy matching), and LinkedIn profile URL.
A match on ANY field is considered a duplicate.
"""
from typing import Optional, Tuple
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from app.models.candidate import Candidate


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    """Normalize phone number for comparison.
    
    Removes all non-digit characters.
    "1 (555) 123-4567" -> "15551234567"
    """
    if not phone:
        return None
    return ''.join(c for c in phone if c.isdigit())


def _phone_match_ratio(phone1: str, phone2: str, threshold: float = 0.8) -> bool:
    """Fuzzy phone number matching.
    
    Tolerates minor digit transpositions/omissions.
    Threshold 0.8 = allow up to 20% difference.
    """
    normalized1 = _normalize_phone(phone1)
    normalized2 = _normalize_phone(phone2)
    
    if not normalized1 or not normalized2:
        return False
    
    # Last 7 digits are most identifying (area code less unique)
    digits1 = normalized1[-7:] if len(normalized1) >= 7 else normalized1
    digits2 = normalized2[-7:] if len(normalized2) >= 7 else normalized2
    
    ratio = SequenceMatcher(None, digits1, digits2).ratio()
    return ratio >= threshold


def find_duplicate_by_email(db: Session, email: str) -> Optional[Candidate]:
    """Check if candidate with this email exists (exact match)."""
    if not email:
        return None
    return db.query(Candidate).filter(
        Candidate.candidateEmail == email.lower()
    ).first()


def find_duplicate_by_phone(db: Session, phone: str, threshold: float = 0.8) -> Optional[Candidate]:
    """Check if candidate with similar phone number exists (fuzzy match).
    
    Returns first candidate whose phone fuzzy-matches, or None.
    """
    if not phone:
        return None
    
    # Get all candidates with phone numbers
    all_candidates = db.query(Candidate).filter(
        Candidate.candidateMobile.isnot(None)
    ).all()
    
    for candidate in all_candidates:
        if _phone_match_ratio(phone, candidate.candidateMobile, threshold):
            return candidate
    
    return None


def find_duplicate_by_linkedin(db: Session, linkedin_url: str) -> Optional[Candidate]:
    """Check if candidate with this LinkedIn profile exists (normalized URL match)."""
    if not linkedin_url:
        return None
    
    # Normalize URL: remove https://, trailing slashes, query params
    normalized = linkedin_url.strip('/').lower()
    if normalized.startswith('https://'):
        normalized = normalized[8:]
    if normalized.startswith('www.'):
        normalized = normalized[4:]
    normalized = normalized.split('?')[0]  # Remove query params
    
    # Find matching candidate
    existing = db.query(Candidate).filter(
        Candidate.linkedin_url.isnot(None)
    ).all()
    
    for candidate in existing:
        existing_normalized = candidate.linkedin_url.strip('/').lower()
        if existing_normalized.startswith('https://'):
            existing_normalized = existing_normalized[8:]
        if existing_normalized.startswith('www.'):
            existing_normalized = existing_normalized[4:]
        existing_normalized = existing_normalized.split('?')[0]
        
        if normalized == existing_normalized:
            return candidate
    
    return None


def find_duplicate_candidate(
    db: Session,
    *,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    phone_match_threshold: float = 0.8,
) -> Tuple[Optional[Candidate], Optional[str]]:
    """
    R-07: Multi-field dedup detection.
    
    Checks in priority order (email → phone → LinkedIn) to ensure
    deterministic matched_on reporting when multiple fields match.
    
    Returns: (candidate, matched_on_field) or (None, None) if no match
    """
    # Check email (highest confidence)
    if email:
        dup = find_duplicate_by_email(db, email)
        if dup:
            return dup, "email"
    
    # Check phone (medium confidence, fuzzy match)
    if phone:
        dup = find_duplicate_by_phone(db, phone, phone_match_threshold)
        if dup:
            return dup, "phone"
    
    # Check LinkedIn (lower confidence, requires exact URL match)
    if linkedin_url:
        dup = find_duplicate_by_linkedin(db, linkedin_url)
        if dup:
            return dup, "linkedin"
    
    return None, None


class MergeRecommendation:
    """Represents a recommended merge between two candidates."""
    
    def __init__(self, existing: Candidate, new_data: dict, confidence: float, reasons: list):
        self.existing = existing
        self.new_data = new_data
        self.confidence = confidence  # 0-1
        self.reasons = reasons  # ["email match", "phone fuzzy match", ...]
    
    def __repr__(self):
        return f"MergeRecommendation(existing_id={self.existing.candidateID}, confidence={self.confidence:.2f})"


def recommend_merge(
    db: Session,
    candidate_data: dict,
) -> Optional[MergeRecommendation]:
    """
    Analyze candidate data and recommend a merge if high-confidence match.
    
    Returns MergeRecommendation or None if no merge recommended.
    """
    email = candidate_data.get('candidateEmail')
    phone = candidate_data.get('candidateMobile')
    linkedin_url = candidate_data.get('linkedin_url')
    
    dup, matched_on = find_duplicate_candidate(
        db, email=email, phone=phone, linkedin_url=linkedin_url
    )
    
    if not dup:
        return None
    
    # Calculate confidence score
    confidence = 0.0
    reasons = []
    
    if matched_on == "email":
        confidence = 0.99  # Email is nearly certain
        reasons.append("Exact email match")
    elif matched_on == "phone":
        confidence = 0.85  # Phone is high confidence
        reasons.append("Fuzzy phone match")
    elif matched_on == "linkedin":
        confidence = 0.90  # LinkedIn is high confidence
        reasons.append("LinkedIn profile URL match")
    
    return MergeRecommendation(
        existing=dup,
        new_data=candidate_data,
        confidence=confidence,
        reasons=reasons,
    )
```

**Step 2.2: Update create_candidate_safe() to Use New Dedup**
```python
# In app/services/candidate_service.py, update create_candidate_safe():

def create_candidate_safe(
    db: Session,
    *,
    email: str,
    mobile: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    candidate_id: Optional[str] = None,
    plain_password: Optional[str] = None,
    **fields,
) -> Candidate:
    """R-07: the only sanctioned path to create a candidate."""
    from app.services.dedup_service import find_duplicate_candidate
    
    existing, matched_on = find_duplicate_candidate(
        db, 
        email=email, 
        mobile=mobile,  # <-- Phone checking now enabled
        linkedin_url=linkedin_url,  # <-- LinkedIn checking now enabled
    )
    if existing:
        raise DuplicateCandidateError(existing, matched_on)
    
    # ... rest of function unchanged
```

**Step 2.3: Add Tests (tests/unit/test_dedup_service.py)**
```python
import pytest
from app.services.dedup_service import (
    find_duplicate_by_email,
    find_duplicate_by_phone,
    find_duplicate_by_linkedin,
    _normalize_phone,
    _phone_match_ratio,
)


def test_email_dedup_exact_match():
    # Create candidate
    candidate = Candidate(candidateEmail="john@example.com", ...)
    db.add(candidate)
    db.commit()
    
    # Try to create duplicate
    dup = find_duplicate_by_email(db, "john@example.com")
    assert dup.candidateID == candidate.candidateID


def test_email_dedup_case_insensitive():
    candidate = Candidate(candidateEmail="John@Example.com", ...)
    db.add(candidate)
    db.commit()
    
    dup = find_duplicate_by_email(db, "john@example.com")
    assert dup is not None


def test_phone_fuzzy_match():
    candidate = Candidate(candidateMobile="(555) 123-4567", ...)
    db.add(candidate)
    db.commit()
    
    # Minor variation should match
    dup = find_duplicate_by_phone(db, "555-123-4567")
    assert dup is not None


def test_phone_no_false_positive():
    candidate = Candidate(candidateMobile="(555) 123-4567", ...)
    db.add(candidate)
    db.commit()
    
    # Different number should not match
    dup = find_duplicate_by_phone(db, "(555) 123-9999")
    assert dup is None


def test_linkedin_url_dedup():
    candidate = Candidate(
        linkedin_url="https://www.linkedin.com/in/johndoe",
        ...
    )
    db.add(candidate)
    db.commit()
    
    # Different URL format, same profile
    dup = find_duplicate_by_linkedin(db, "linkedin.com/in/johndoe/")
    assert dup is not None


def test_phone_normalize():
    assert _normalize_phone("(555) 123-4567") == "5551234567"
    assert _normalize_phone("+1-555.123.4567") == "15551234567"
    assert _normalize_phone(None) is None
```

**Checklist:**
- [ ] dedup_service.py created with all 3 matching functions
- [ ] create_candidate_safe() updated to use phone + LinkedIn checks
- [ ] Unit tests written and passing
- [ ] Integration test: Try creating duplicate via email/phone/LinkedIn, all rejected

**Effort:** 2 hours  
**Files Changed:** 3 (new service, updated candidate_service, new tests)  
**Risk:** LOW — Dedup is new, doesn't break existing code  

---

## FIX #3: Create Auto-Scoring Trigger Daemon (3 hours)

### Requirement
Scoring services exist but are never called automatically.  
Currently: Only called manually or by specific workflows.  
Need: Automatic scoring on candidate creation, post-resume-parse, and periodic batch.

### Implementation

**Step 3.1: Create Scoring Daemon (app/core/background_jobs.py)**
```python
"""
Auto-Scoring Daemon.

Ensures all candidates get scored automatically on:
1. Candidate creation
2. Resume parsing completion
3. Every 6 hours (batch job for missed candidates)
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.database import SessionLocal
from app.models.candidate import Candidate, CandidateStatus
from app.services.overall_scoring_service import score_candidate_overall
from app.services.abandonment_scoring_service import compute_drop_risk

logger = logging.getLogger(__name__)


def auto_score_on_creation(db: Session, candidate_id: str) -> None:
    """Score candidate immediately after creation."""
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.warning(f"Candidate {candidate_id} not found for scoring")
            return
        
        logger.info(f"Auto-scoring candidate {candidate_id} on creation")
        
        # Run all scoring services
        score_candidate_overall(db, candidate)
        compute_drop_risk(db, candidate)
        
        db.commit()
        logger.info(f"Auto-scoring complete for {candidate_id}")
    except Exception as e:
        logger.error(f"Error auto-scoring candidate {candidate_id}: {e}")
        db.rollback()


def auto_score_on_resume_parse(db: Session, candidate_id: str) -> None:
    """Score candidate after resume parsing completes."""
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            return
        
        logger.info(f"Auto-scoring candidate {candidate_id} post-resume-parse")
        score_candidate_overall(db, candidate)
        db.commit()
    except Exception as e:
        logger.error(f"Error auto-scoring post-parse for {candidate_id}: {e}")
        db.rollback()


def batch_auto_score_all() -> None:
    """Periodic batch: score any candidates that haven't been scored recently."""
    db = SessionLocal()
    try:
        # Find candidates without scores or with scores >24h old
        unscored = db.query(Candidate).filter(
            Candidate.overall_desire_score.is_(None)
        ).all()
        
        for candidate in unscored:
            try:
                logger.info(f"Batch auto-scoring candidate {candidate.candidateID}")
                score_candidate_overall(db, candidate)
            except Exception as e:
                logger.error(f"Error scoring {candidate.candidateID}: {e}")
        
        db.commit()
        logger.info(f"Batch auto-scoring complete: {len(unscored)} candidates scored")
    except Exception as e:
        logger.error(f"Error in batch auto-scoring: {e}")
        db.rollback()
    finally:
        db.close()


def start_scoring_daemon():
    """Start background scheduler for auto-scoring."""
    scheduler = BackgroundScheduler()
    
    # Batch job every 6 hours
    scheduler.add_job(
        batch_auto_score_all,
        'interval',
        hours=6,
        id='auto_score_batch',
        name='Auto-Score All Candidates Batch',
    )
    
    scheduler.start()
    logger.info("Auto-scoring daemon started")
    return scheduler
```

**Step 3.2: Wire Daemon to Application Startup (app/main.py)**
```python
# In FastAPI app startup event:
from app.core.background_jobs import start_scoring_daemon

@app.on_event("startup")
async def startup_event():
    # ... existing startup code ...
    start_scoring_daemon()
    logger.info("Auto-scoring daemon initialized")


@app.on_event("shutdown")
async def shutdown_event():
    # ... cleanup ...
    pass
```

**Step 3.3: Hook into create_candidate_safe() (app/services/candidate_service.py)**
```python
def create_candidate_safe(db: Session, *, email: str, ...) -> Candidate:
    # ... create candidate as before ...
    
    candidate = Candidate(...)
    db.add(candidate)
    db.flush()  # Ensure ID is available
    
    # Trigger auto-scoring
    try:
        from app.core.background_jobs import auto_score_on_creation
        # Run in background (don't block candidate creation)
        auto_score_on_creation(db, candidate.candidateID)
    except Exception as e:
        logger.warning(f"Auto-scoring failed for {candidate.candidateID}: {e}")
        # Don't fail candidate creation if scoring fails
    
    return candidate
```

**Step 3.4: Add Tests (tests/unit/test_auto_scoring.py)**
```python
def test_auto_score_on_creation():
    candidate = create_candidate_safe(db, email="test@example.com", ...)
    
    # Overall score should be computed
    assert candidate.overall_desire_score is not None
    assert 0 <= candidate.overall_desire_score <= 100


def test_batch_auto_score():
    # Create 5 candidates
    for i in range(5):
        create_candidate_safe(db, email=f"test{i}@example.com", ...)
    
    # Manually clear scores to simulate unscored candidates
    db.query(Candidate).update({'overall_desire_score': None})
    db.commit()
    
    # Run batch scoring
    from app.core.background_jobs import batch_auto_score_all
    batch_auto_score_all()
    
    # Verify all scored
    unscored = db.query(Candidate).filter(
        Candidate.overall_desire_score.is_(None)
    ).count()
    assert unscored == 0
```

**Checklist:**
- [ ] background_jobs.py created with daemon + batch job
- [ ] Daemon wired to app startup (main.py)
- [ ] create_candidate_safe() triggers auto-scoring
- [ ] Tests verify scoring runs automatically
- [ ] Verified: batch job runs every 6 hours
- [ ] Verified: no scoring failures block candidate creation

**Effort:** 3 hours  
**Files Changed:** 4 (new daemon, main.py, candidate_service, new tests)  
**Risk:** LOW — Daemon is separate, non-blocking  

---

## FIX #4: Create Sync Log Tables + Migration (1.5 hours)

### Requirement
Track ERP invoice sync and payroll sync status (currently missing)

### Implementation

**Step 4.1: Create Models (app/models/sync_log.py)**
```python
"""
ERP and Payroll Sync Tracking.

Enables audit trail of synchronization events with external systems.
"""
from sqlalchemy import Column, String, DateTime, Enum, func, ForeignKey, Integer
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base


class ERPSyncLog(Base):
    __tablename__ = "erp_sync_logs"
    
    id = Column(String(36), primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)
    
    # Sync Status: PENDING, IN_PROGRESS, SUCCESS, FAILED, RETRYING
    sync_status = Column(
        Enum("PENDING", "IN_PROGRESS", "SUCCESS", "FAILED", "RETRYING", name="erp_sync_status"),
        nullable=False,
        default="PENDING",
        server_default="PENDING",
    )
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    synced_at = Column(DateTime, nullable=True)
    last_error = Column(String(500), nullable=True)
    retry_count = Column(Integer, default=0)
    
    # ERP Reference
    erp_invoice_id = Column(String(100), nullable=True, unique=True)
    
    # Relationships
    invoice = relationship("Invoice", foreign_keys=[invoice_id])


class PayrollSyncLog(Base):
    __tablename__ = "payroll_sync_logs"
    
    id = Column(String(36), primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    employee_id = Column(String(50), ForeignKey("employees.id"), nullable=False, index=True)
    
    # Sync Status: PENDING, IN_PROGRESS, SUCCESS, FAILED, RETRYING
    sync_status = Column(
        Enum("PENDING", "IN_PROGRESS", "SUCCESS", "FAILED", "RETRYING", name="payroll_sync_status"),
        nullable=False,
        default="PENDING",
        server_default="PENDING",
    )
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    synced_at = Column(DateTime, nullable=True)
    last_error = Column(String(500), nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Payroll Period
    payroll_period_start = Column(DateTime, nullable=False)
    payroll_period_end = Column(DateTime, nullable=False)
    
    # Payroll System Reference
    payroll_record_id = Column(String(100), nullable=True, unique=True)
    
    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
```

**Step 4.2: Update __init__.py**
```python
# In app/models/__init__.py, add imports:
from app.models.sync_log import ERPSyncLog, PayrollSyncLog
```

**Step 4.3: Create Alembic Migration**
```bash
alembic revision --autogenerate -m "Add ERP and Payroll sync log tables"
```

Migration file should include:
```python
def upgrade():
    # ERP Sync Log table
    op.create_table(
        'erp_sync_logs',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('invoice_id', sa.String(36), nullable=False),
        sa.Column('sync_status', sa.Enum('PENDING', 'IN_PROGRESS', 'SUCCESS', 'FAILED', 'RETRYING'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.String(500), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('erp_invoice_id', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('erp_invoice_id'),
    )
    op.create_index('ix_erp_sync_logs_tenant_id', 'erp_sync_logs', ['tenant_id'])
    op.create_index('ix_erp_sync_logs_invoice_id', 'erp_sync_logs', ['invoice_id'])
    
    # Payroll Sync Log table
    op.create_table(
        'payroll_sync_logs',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('employee_id', sa.String(50), nullable=False),
        sa.Column('sync_status', sa.Enum('PENDING', 'IN_PROGRESS', 'SUCCESS', 'FAILED', 'RETRYING'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.String(500), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('payroll_period_start', sa.DateTime(), nullable=False),
        sa.Column('payroll_period_end', sa.DateTime(), nullable=False),
        sa.Column('payroll_record_id', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('payroll_record_id'),
    )
    op.create_index('ix_payroll_sync_logs_tenant_id', 'payroll_sync_logs', ['tenant_id'])
    op.create_index('ix_payroll_sync_logs_employee_id', 'payroll_sync_logs', ['employee_id'])

def downgrade():
    op.drop_table('payroll_sync_logs')
    op.drop_table('erp_sync_logs')
```

**Step 4.4: Create Service (app/services/sync_service.py)**
```python
"""
Sync Log Services.

Track and manage integration with ERP and payroll systems.
"""
from datetime import datetime
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.sync_log import ERPSyncLog, PayrollSyncLog


def create_erp_sync_log(db: Session, invoice_id: str, tenant_id: int = None) -> ERPSyncLog:
    """Create a new ERP sync log entry."""
    log = ERPSyncLog(
        id=str(uuid4()),
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        sync_status="PENDING",
    )
    db.add(log)
    db.commit()
    return log


def mark_erp_sync_complete(db: Session, sync_log_id: str, erp_invoice_id: str = None) -> ERPSyncLog:
    """Mark ERP sync as successful."""
    log = db.query(ERPSyncLog).filter(ERPSyncLog.id == sync_log_id).first()
    if log:
        log.sync_status = "SUCCESS"
        log.synced_at = datetime.utcnow()
        log.erp_invoice_id = erp_invoice_id
        db.commit()
    return log


def mark_erp_sync_failed(db: Session, sync_log_id: str, error: str) -> ERPSyncLog:
    """Mark ERP sync as failed."""
    log = db.query(ERPSyncLog).filter(ERPSyncLog.id == sync_log_id).first()
    if log:
        log.sync_status = "FAILED"
        log.last_error = error[:500]  # Truncate to 500 chars
        log.retry_count += 1
        db.commit()
    return log


# Similar functions for payroll sync...
```

**Checklist:**
- [ ] sync_log.py created with ERPSyncLog and PayrollSyncLog models
- [ ] Models added to __init__.py
- [ ] Alembic migration created and tested
- [ ] sync_service.py created with tracking functions
- [ ] Tested: Tables created, data can be inserted/queried

**Effort:** 1.5 hours  
**Files Changed:** 5 (new models, migration, service, __init__, test)  
**Risk:** LOW — New tables only, no impact on existing code  

---

## FIX #5: Add Missing Candidate Fields (30 min)

### Requirement
Add thunder_channel_user_id, overall_desire_score, consent_given, employment_type_confirmed  
Currently: Some fields missing for Thunder + scoring integration

### Implementation

**Step 5.1: Update Candidate Model (app/models/candidate.py)**
```python
# Add to Candidate class:

# Thunder Integration (HRMS-0410)
thunder_channel_user_id = Column(String(100), nullable=True, index=True)
# This ID from Thunder's conversation engine, enables tracking Thunder's engagement with candidate

# Overall Candidate Score (Denormalized from Desire Profiles for fast reads)
overall_desire_score = Column(Integer, nullable=True)
# 0-100 scale, updated by scoring services

# Consent Management (HRMS-P605)
consent_given = Column(Boolean, nullable=True)
# Has candidate given consent for communication? (Tri-state: NULL=not asked, True=yes, False=no)

# Employment Type Confirmation (HRMS-P606, R-03)
employment_type_confirmed = Column(Boolean, nullable=True, server_default="0")
# Has HR explicitly confirmed W2_FULLTIME status? (prevents UNKNOWN status from being used)
```

**Step 5.2: Create Migration**
```bash
alembic revision --autogenerate -m "Add Thunder + scoring fields to candidates"
```

**Step 5.3: Update create_candidate_safe()**
```python
def create_candidate_safe(db: Session, ..., thunder_channel_user_id: str = None, **fields) -> Candidate:
    # ...
    candidate = Candidate(
        candidateID=candidate_id,
        candidateEmail=email,
        candidateMobile=mobile,
        linkedin_url=linkedin_url,
        candidatePassword=get_password_hash(plain_password),
        thunder_channel_user_id=thunder_channel_user_id,  # <-- NEW
        consent_given=mobile is not None,  # Implicit consent if phone provided
        employment_type_confirmed=fields.get("employment_type_confirmed", False),
        **fields,
    )
    # ...
```

**Checklist:**
- [ ] 4 new fields added to Candidate model
- [ ] Migration created and tested
- [ ] create_candidate_safe() updated to populate new fields
- [ ] Tested: Fields can be read/written

**Effort:** 30 minutes  
**Files Changed:** 3 (model, migration, candidate_service)  
**Risk:** LOW — New fields only, backward compatible  

---

## IMPLEMENTATION ORDER & TIMELINE

| Fix | Effort | Dependencies | Start | Target |
|-----|--------|--------------|-------|--------|
| #1 R-01 enforcement | 15m | None | Now | +15m |
| #2 Dedup service | 2h | #1 | +15m | +2.25h |
| #3 Auto-scoring | 3h | #2 | +2.25h | +5.25h |
| #4 Sync tables | 1.5h | None (parallel) | Now | +1.5h |
| #5 Candidate fields | 30m | #3 | +5.25h | +6h |
| **Testing + Commit** | 1h | All | +6h | +7h |

**Total Estimated Time:** ~7 hours (1 day of focused work)

---

## SUCCESS CRITERIA

✅ All 6 critical fixes implemented  
✅ All tests passing (unit + integration)  
✅ R-01, R-07 enforcement verified at code + database level  
✅ Auto-scoring trigger verified running  
✅ Sync log tables verified working  
✅ All changes committed to git  
✅ Phase 2 audit report signed off  
✅ Phase 3 ready to kickoff  

---

## RISK MITIGATION

| Risk | Mitigation |
|------|------------|
| **Dedup causing false positives** | Fuzzy matching threshold tunable, extensive unit tests |
| **Auto-scoring degrading performance** | Background daemon, non-blocking, batch runs off-peak |
| **Migration failures** | Test on clean SQLite first, backup before running on production |
| **Database constraint violations** | CHECK constraint added carefully, existing data validated first |

---

**Status:** Ready to implement  
**Next Step:** Start FIX #1 (R-01 Database Enforcement)
