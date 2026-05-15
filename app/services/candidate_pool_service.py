"""
Candidate Pool Service
======================
Central service for all pool ownership transitions.

All four state-changing helpers write a CandidateHistory event automatically,
so the audit trail is always up to date.

Usage in endpoints:
    from app.services.candidate_pool_service import (
        set_bu_owned, set_org_pool, get_ownership, expire_bu_ownerships
    )
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate_ownership import CandidateOwnership, POOL_BU, POOL_ORG
from app.models.candidate_history import CandidateHistory


# ── constants ─────────────────────────────────────────────────────────────────

BU_OWNERSHIP_DAYS = 90   # how long BU owns a candidate after offer release


# ── helpers ───────────────────────────────────────────────────────────────────

def _log_history(
    candidate_id: str,
    event_type: str,
    note: str,
    db: Session,
    performed_by_id: Optional[str] = None,
    performed_by_name: Optional[str] = None,
) -> None:
    """Write a CandidateHistory row for an ownership transition."""
    db.add(CandidateHistory(
        candidateID=candidate_id,
        event_type=event_type,
        note=note,
        performed_by_id=performed_by_id,
        performed_by_name=performed_by_name,
        event_at=datetime.utcnow(),
    ))


def _upsert_ownership(
    candidate_id: str,
    db: Session,
    pool_status: str,
    owned_by_bu_id: Optional[int],
    owned_by_bu_name: Optional[str],
    ownership_reason: str,
    bu_owned_since: Optional[datetime],
    bu_ownership_expires_at: Optional[datetime],
) -> CandidateOwnership:
    """Create or update the single ownership row for a candidate."""
    row = (
        db.query(CandidateOwnership)
        .filter(CandidateOwnership.candidateID == candidate_id)
        .first()
    )
    if row is None:
        row = CandidateOwnership(candidateID=candidate_id)
        db.add(row)

    row.pool_status            = pool_status
    row.owned_by_bu_id         = owned_by_bu_id
    row.owned_by_bu_name       = owned_by_bu_name
    row.ownership_reason       = ownership_reason
    row.bu_owned_since         = bu_owned_since
    row.bu_ownership_expires_at = bu_ownership_expires_at
    return row


# ── public API ────────────────────────────────────────────────────────────────

def get_ownership(candidate_id: str, db: Session) -> Optional[CandidateOwnership]:
    """Return the current ownership row, or None if not yet created."""
    return (
        db.query(CandidateOwnership)
        .filter(CandidateOwnership.candidateID == candidate_id)
        .first()
    )


def set_bu_owned(
    candidate_id: str,
    bu_id: int,
    bu_name: str,
    reason: str,
    db: Session,
    expires_at: Optional[datetime] = None,
    performed_by_id: Optional[str] = None,
    performed_by_name: Optional[str] = None,
) -> CandidateOwnership:
    """
    Transition a candidate to BU Owned.

    Args:
        candidate_id:       Candidate's ID.
        bu_id:              BusinessUnit.id of the owning BU.
        bu_name:            Display name of the BU (snapshot).
        reason:             Human-readable reason string.
        db:                 SQLAlchemy session.
        expires_at:         Optional expiry datetime (set when offer is released).
        performed_by_id:    User who triggered the transition.
        performed_by_name:  Display name of that user.

    Returns:
        Updated CandidateOwnership row.
    """
    row = _upsert_ownership(
        candidate_id=candidate_id,
        db=db,
        pool_status=POOL_BU,
        owned_by_bu_id=bu_id,
        owned_by_bu_name=bu_name,
        ownership_reason=reason,
        bu_owned_since=datetime.utcnow(),
        bu_ownership_expires_at=expires_at,
    )
    _log_history(
        candidate_id=candidate_id,
        event_type="Custom",
        note=f"Pool → BU Owned by '{bu_name}'. Reason: {reason}",
        db=db,
        performed_by_id=performed_by_id,
        performed_by_name=performed_by_name,
    )
    logger.info(
        f"candidate_pool — '{candidate_id}' → BU Owned by BU #{bu_id} ({bu_name}). {reason}"
    )
    return row


def set_org_pool(
    candidate_id: str,
    reason: str,
    db: Session,
    performed_by_id: Optional[str] = None,
    performed_by_name: Optional[str] = None,
) -> CandidateOwnership:
    """
    Transition a candidate back to the Org Pool.

    Args:
        candidate_id:       Candidate's ID.
        reason:             Human-readable reason string.
        db:                 SQLAlchemy session.
        performed_by_id:    User who triggered the transition.
        performed_by_name:  Display name of that user.

    Returns:
        Updated CandidateOwnership row.
    """
    row = _upsert_ownership(
        candidate_id=candidate_id,
        db=db,
        pool_status=POOL_ORG,
        owned_by_bu_id=None,
        owned_by_bu_name=None,
        ownership_reason=reason,
        bu_owned_since=None,
        bu_ownership_expires_at=None,
    )
    _log_history(
        candidate_id=candidate_id,
        event_type="Custom",
        note=f"Pool → Org Pool. Reason: {reason}",
        db=db,
        performed_by_id=performed_by_id,
        performed_by_name=performed_by_name,
    )
    logger.info(f"candidate_pool — '{candidate_id}' → Org Pool. {reason}")
    return row


def set_bu_owned_with_expiry(
    candidate_id: str,
    bu_id: int,
    bu_name: str,
    reason: str,
    db: Session,
    performed_by_id: Optional[str] = None,
    performed_by_name: Optional[str] = None,
) -> CandidateOwnership:
    """
    Transition a candidate to BU Owned with the 90-day expiry clock.
    Use this when an offer is released (BU selected the candidate).
    """
    expires_at = datetime.utcnow() + timedelta(days=BU_OWNERSHIP_DAYS)
    row = set_bu_owned(
        candidate_id=candidate_id,
        bu_id=bu_id,
        bu_name=bu_name,
        reason=reason,
        db=db,
        expires_at=expires_at,
        performed_by_id=performed_by_id,
        performed_by_name=performed_by_name,
    )
    logger.info(
        f"candidate_pool — '{candidate_id}' BU ownership expires at {expires_at.isoformat()}"
    )
    return row


# ── scheduler function ────────────────────────────────────────────────────────

def expire_bu_ownerships(db: Session) -> int:
    """
    Move all BU-owned candidates whose `bu_ownership_expires_at` is in the past
    back to the Org Pool.

    Called daily by APScheduler.

    Returns:
        Number of candidates transitioned.
    """
    now = datetime.utcnow()
    expired_rows = (
        db.query(CandidateOwnership)
        .filter(
            CandidateOwnership.pool_status == POOL_BU,
            CandidateOwnership.bu_ownership_expires_at != None,
            CandidateOwnership.bu_ownership_expires_at <= now,
        )
        .all()
    )

    count = 0
    for row in expired_rows:
        set_org_pool(
            candidate_id=row.candidateID,
            reason=f"90-day BU ownership lock expired (was owned by '{row.owned_by_bu_name}')",
            db=db,
            performed_by_id="system",
            performed_by_name="Scheduler",
        )
        count += 1

    if count:
        db.commit()
        logger.info(f"candidate_pool — scheduler expired {count} BU ownership(s)")

    return count
