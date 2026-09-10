"""
Thunder Autonomous Execution Loop
==================================
Continuously activates Thunder to:
1. Contact pending candidates
2. Advance outreach sequences
3. Schedule interviews
import logging
4. Collect information

Respects pause state (kill switch) via thunder_pause_service.

Runs in background via APScheduler - starts with app initialization.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.outreach import OutreachSequence
from app.core.logging import logger
from app.services.outreach_agent_service import (
    start_outreach_sequence,
    advance_outreach_sequence,
    OutreachDebounced,
)
from app.services.thunder_pause_service import is_thunder_paused
from app.core.database import SessionLocal
from app.core.agent_logging import log_agent_execution

logger = logging.getLogger(__name__)

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

    # Get system admin user for tenant_id (required by FK constraint)
    from app.models.user import Users
    system_admin = db.query(Users).filter(
        Users.UserRole == "Super User"
    ).first()

    if not system_admin:
        # Fallback to first admin user if no super user found
        system_admin = db.query(Users).filter(
            Users.UserRole.ilike("%admin%")
        ).first()

    if not system_admin:
        return {
            "status": "error",
            "error": "No system admin user found for tenant_id",
            "candidates_contacted": 0,
            "sequences_advanced": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }

    tenant_user_id = system_admin.UserID
    contacted = 0
    advanced = 0
    errors = []

    try:
        # Step 1: Find candidates pending outreach
        # First: Get new candidates from CANDIDATE_QUEUE (just created)
        # Then: Get all candidates without active conversations

        from app.models.message_queue import MessageQueue

        queue_candidates = []
        try:
            # Fetch candidates from completed CANDIDATE_QUEUE messages
            completed_queue_messages = db.query(MessageQueue).filter(
                MessageQueue.queue_type == "CANDIDATE_QUEUE",
                MessageQueue.status == "COMPLETED",
                MessageQueue.type.in_(["create_candidate", "update_candidate"])
            ).limit(10).all()

            if completed_queue_messages:
                for msg in completed_queue_messages:
                    if msg and msg.resource_id:
                        try:
                            candidate = db.query(Candidate).filter(
                                Candidate.candidateID == msg.resource_id
                            ).first()
                            if candidate:
                                queue_candidates.append(candidate)
                                # Mark message as processed by Thunder
                                msg.status = "PROCESSED_BY_THUNDER"
                                try:
                                    db.commit()
                                except Exception as commit_err:
                                    logger.error(f"Error committing queue message status: {commit_err}", exc_info=True)
                                    db.rollback()
                        except Exception as e:
                            logger.error(f"Error processing queue message {msg.id}: {e}", exc_info=True)
                            continue
        except Exception as e:
            logger.warning(f"Error fetching candidates from CANDIDATE_QUEUE: {e}", exc_info=True)
            # Continue with normal flow if queue fetch fails

        # Step 2: Find all candidates pending outreach (no active conversation = never contacted)
        # Query: all candidates without an existing CandidateConversation record
        pending_candidates = db.query(Candidate).filter(
            ~db.query(CandidateConversation).filter(
                CandidateConversation.candidate_id == Candidate.candidateID
            ).exists()
        ).limit(10).all()  # Limit to 10 per cycle to avoid overwhelming

        # Combine queue candidates with pending candidates (remove duplicates)
        all_candidates = list(set(queue_candidates + pending_candidates))[:10]

        # Step 3: Create conversations and log Thunder outreach activity for each candidate
        if all_candidates:
            for candidate in all_candidates:
                try:
                    # Check if conversation already exists for this candidate
                    existing_conversation = db.query(CandidateConversation).filter(
                        CandidateConversation.candidate_id == candidate.candidateID
                    ).first()

                    if existing_conversation:
                        logger.debug(f"Conversation already exists for candidate {candidate.candidateID}, skipping")
                        continue

                    # Create conversation record only if not already exists
                    existing = db.query(CandidateConversation).filter(
                        CandidateConversation.candidate_id == candidate.candidateID
                    ).first()

                    if not existing:
                        conversation = CandidateConversation(
                            candidate_id=candidate.candidateID,
                            tenant_id=tenant_user_id,
                            owner_type="Thunder",
                            owner_id="Thunder_Autonomous",
                            status="ACTIVE",
                        )
                        db.add(conversation)
                        db.flush()
                    else:
                        conversation = existing

                    # Log Thunder outreach as activity feed event - check if not already exists
                    existing_event = db.query(ConversationEvent).filter(
                        ConversationEvent.conversation_id == conversation.id,
                        ConversationEvent.event_type == "THUNDER_OUTREACH_INITIATED"
                    ).first()

                    if not existing_event:
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
                    logger.error(f"Error: {str(e)}", exc_info=True)
                    errors.append(f"Candidate {candidate.candidateID}: {str(e)}")
                    db.rollback()

        # Step 4: Advance existing open sequences
        open_sequences = db.query(OutreachSequence).filter(
            OutreachSequence.status.in_(["SENT", "QUEUED"])
        ).limit(20).all()

        if open_sequences:
            for sequence in open_sequences:
                try:
                    candidate = db.query(Candidate).filter(
                        Candidate.candidateID == sequence.candidate_id
                    ).first()
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
                    logger.error(f"Error: {str(e)}", exc_info=True)
                    errors.append(f"Sequence {sequence.id}: {str(e)}")

            db.commit()

        # PHASE 3B: AUTONOMOUS PROGRESSION (Qualify → Screen → Interview → Offer → Onboard)
        from app.services.thunder_autonomous_progression_service import ThunderAutonomousProgression

        progression_stats = {
            "qualified": 0,
            "screened": 0,
            "interviewed": 0,
            "offers_generated": 0,
            "onboarded": 0,
        }

        try:
            # Find engaged candidates for progression
            engaged_candidates = db.query(Candidate).filter(
                Candidate.candidate_status == "ENGAGED"
            ).limit(10).all()

            for candidate in engaged_candidates:
                # Stage 1: Qualify
                qual_result = ThunderAutonomousProgression.attempt_qualify_candidate(db, candidate.candidateID)
                if qual_result["status"] == "progressed":
                    progression_stats["qualified"] += 1

                    # Stage 2: Screen
                    screen_result = ThunderAutonomousProgression.attempt_screen_candidate(db, candidate.candidateID)
                    if screen_result["status"] == "screened":
                        progression_stats["screened"] += 1
                        job_id = screen_result.get("job_id")

                        # Stage 3: Interview
                        interview_result = ThunderAutonomousProgression.attempt_schedule_interview(db, candidate.candidateID, job_id)
                        if interview_result["status"] == "scheduled":
                            progression_stats["interviewed"] += 1

                        # Stage 4: Offer (check after some time passes)
                        offer_result = ThunderAutonomousProgression.attempt_generate_offer(db, candidate.candidateID, job_id)
                        if offer_result["status"] == "generated":
                            progression_stats["offers_generated"] += 1

                        # Stage 5: Onboard
                        onboard_result = ThunderAutonomousProgression.attempt_onboard_candidate(db, candidate.candidateID)
                        if onboard_result["status"] == "onboarded":
                            progression_stats["onboarded"] += 1

        except Exception as e:
            logger.error(f"Phase 3B progression error: {e}", exc_info=True)
            errors.append(f"Phase 3B: {str(e)}")

        return {
            "status": "success",
            "candidates_contacted": contacted,
            "sequences_advanced": advanced,
            "phase_3b": progression_stats,
            "paused": False,
            "errors": errors if errors else None,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
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
        logger.error(f"Error: {str(e)}", exc_info=True)
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
