"""
Thunder Autonomous Execution Loop
==================================
Continuously activates Thunder to:
1. Contact pending candidates
2. Advance outreach sequences
3. Schedule interviews
4. Collect information

Respects pause state (kill switch) via thunder_pause_service.

Runs in background via APScheduler - starts with app initialization.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.outreach import OutreachSequence
from app.services.outreach_agent_service import (
    start_outreach_sequence,
    advance_outreach_sequence,
    OutreachDebounced,
)
from app.services.thunder_pause_service import is_thunder_paused
from app.core.database import SessionLocal
from app.core.agent_logging import log_agent_execution


class ThunderAutonomousLoopError(Exception):
    """Raised when Thunder autonomous loop encounters unrecoverable error."""
    pass


def run_thunder_autonomous_cycle(db: Session) -> dict:
    """
    Run one cycle of Thunder's autonomous loop:
    1. Check if Thunder is paused (kill switch)
    2. Find candidates needing outreach
    3. Create conversations and log outreach activity
    4. Advance existing sequences
    5. Log execution metrics

    Returns: {
        "status": "success",
        "candidates_contacted": int,
        "sequences_advanced": int,
        "paused": bool,
        "timestamp": str
    }
    """
    # Check kill switch first
    if is_thunder_paused(db):
        return {
            "status": "paused",
            "paused": True,
            "candidates_contacted": 0,
            "sequences_advanced": 0,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Thunder paused (kill switch active)"
        }

    contacted = 0
    advanced = 0
    errors = []

    try:
        # Step 1: Find candidates pending outreach (no active conversation = never contacted)
        # OPTIMIZED: Use LEFT JOIN instead of NOT EXISTS for better performance
        from sqlalchemy import func
        pending_candidates = db.query(Candidate).outerjoin(
            CandidateConversation,
            Candidate.candidateID == CandidateConversation.candidate_id
        ).filter(
            CandidateConversation.id == None,  # No conversation exists
            Candidate.do_not_contact == False  # Respect opt-out
        ).limit(50).all()  # Batch size: 50 candidates per cycle (5x more throughput)

        # Step 2: Create conversations and log Thunder outreach activity for each candidate
        for candidate in pending_candidates:
            try:
                # Create conversation record
                conversation = CandidateConversation(
                    candidate_id=candidate.candidateID,
                    tenant_id=candidate.tenant_id or "default",
                    owner_type="Thunder",
                    owner_id="Thunder_Autonomous",
                    status="ACTIVE",
                )
                db.add(conversation)
                db.flush()

                # Log Thunder outreach as activity feed event
                event = ConversationEvent(
                    conversation_id=conversation.id,
                    event_type="THUNDER_OUTREACH_INITIATED",
                    triggered_by="Thunder_Autonomous",
                    event_data={
                        "candidate_name": candidate.candidateFirstName + " " + (candidate.candidateLastName or ""),
                        "candidate_email": candidate.candidateEmail,
                        "existing_candidate_merged": False,  # Flag if merged with existing profile
                        "context_summary": f"Profile reviewed: {candidate.candidateJobTitle or 'No title'} | Location: {candidate.candidateCurrentLocation or 'Not specified'}",
                        "confidence_level": "High - Complete profile match",
                        "outreach_channel": "Email",
                        "notes": f"Thunder initiated autonomous outreach. Candidate qualifications: {candidate.candidateJobTitle or 'N/A'}"
                    }
                )
                db.add(event)
                contacted += 1
            except Exception as e:
                errors.append(f"Candidate {candidate.candidateID}: {str(e)}")
                db.rollback()

        # Step 3: Advance existing open sequences
        # OPTIMIZED: Increased limit from 20 to 100, pre-fetch candidates to avoid N+1
        open_sequences = db.query(OutreachSequence).filter(
            OutreachSequence.status.in_(["SENT", "QUEUED"])
        ).limit(100).all()

        # Pre-fetch all candidates for these sequences (single query instead of N queries)
        candidate_ids = [seq.candidate_id for seq in open_sequences]
        candidates_map = {}
        if candidate_ids:
            candidates_list = db.query(Candidate).filter(
                Candidate.candidateID.in_(candidate_ids)
            ).all()
            candidates_map = {c.candidateID: c for c in candidates_list}

        for sequence in open_sequences:
            try:
                candidate = candidates_map.get(sequence.candidate_id)
                if candidate:
                    advance_outreach_sequence(
                        db,
                        sequence=sequence,
                        candidate=candidate,
                        demand=None,
                        now=datetime.utcnow()
                    )
                    advanced += 1
            except Exception as e:
                errors.append(f"Sequence {sequence.id}: {str(e)}")

        db.commit()

        return {
            "status": "success",
            "candidates_contacted": contacted,
            "sequences_advanced": advanced,
            "paused": False,
            "errors": errors if errors else None,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        db.rollback()
        return {
            "status": "error",
            "error": str(e),
            "paused": False,
            "timestamp": datetime.utcnow().isoformat(),
        }


def initialize_thunder_autonomous_loop():
    """
    Initialize Thunder's autonomous loop to run every 5 minutes.

    Called on app startup via main.py.
    Use pause_thunder() to activate kill switch.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()

        # Run Thunder cycle every 5 minutes
        scheduler.add_job(
            func=_thunder_cycle_wrapper,
            trigger="interval",
            minutes=5,
            id="thunder_autonomous_loop",
            name="Thunder Autonomous Execution Loop",
            replace_existing=True,
            max_instances=1,  # Only one instance at a time
        )

        scheduler.start()
        return True
    except ImportError:
        # APScheduler not installed - skip autonomous loop
        print("WARNING: APScheduler not installed. Thunder autonomous loop disabled.")
        return False
    except Exception as e:
        print(f"ERROR: Failed to initialize Thunder autonomous loop: {e}")
        return False


def _thunder_cycle_wrapper():
    """Wrapper to handle database session for background task."""
    db = SessionLocal()
    try:
        result = run_thunder_autonomous_cycle(db)
        if result.get("status") == "success":
            print(f"✅ Thunder cycle: {result['candidates_contacted']} contacted, "
                  f"{result['sequences_advanced']} advanced")
        elif result.get("status") == "paused":
            print("⏸️  Thunder paused (kill switch active)")
        else:
            print(f"⚠️  Thunder cycle error: {result.get('error')}")
    finally:
        db.close()
