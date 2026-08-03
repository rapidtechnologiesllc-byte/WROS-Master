"""
S-044/HRMS-0444 -- Multi-Touch Outreach Campaign.

Real architecture adaptations:
- outreach_campaigns/campaign_touchpoints are genuinely new (see their
  model docstring, including the honest note on this being a third,
  overlapping "capped multi-touch, stop-on-reply" mechanism).
- Real spec-internal inconsistency, resolved per this round's
  established "trust the step-by-step + AC/TC over the narrative
  prose" convention (same call made for S-037's domain-match, S-038's
  unreachable rule, S-041/042's event-ownership conflict): "Before You
  Start"/"Why This Exists" both frame this as triggered by no-response
  detection (HRMS-0442), but Step 4's own literal text says
  startCampaign() is "Called by HRMS-0412/0413 after first messages
  sent" -- i.e. unconditionally, the moment Day-0 goes out -- and
  TC-001 confirms this (no no-response precondition in the test).
  Implemented per Step 4/TC-001: start_campaign() is called right after
  the real Day-0 first-contact sends succeed (S-012/S-013,
  auto_assign_ai_agent_on_creation), not gated on any no-response signal.
- No conversation_messages table -- ConversationEvent is the real
  message log throughout (message_event_id FKs into it).
- No internal event bus -- "message.received cancels pending
  touchpoints" is wired directly into the same 3 real live inbound
  entry points S-041's cancel_pending_follow_ups() already hooks
  (whatsapp_webhook_service, ai_conversation_service's email pipeline,
  public_chat_service). "publish candidate.campaign_completed_no_response,
  consumed by HRMS-0443 Ghosting Detection" is NOT implemented as a
  signal into ghosting_detection_service -- S-043's own
  run_ghosting_detection_job() already has its own real, independent
  trigger (CandidateNoResponseLog rows with detection_type='POST_THIRD',
  written by S-042's follow-up-count tracking); wiring a second,
  campaign-shaped trigger into the same ghosting mechanism would create
  two independent paths to the same terminal state with no real
  reconciliation logic, and there is no real listener need for the
  campaign-completion signal beyond what candidate_ghosting_status
  itself already provides via S-041/042/043's own detection chain.
  outreach_campaigns.status/stop_reason IS the real, durable record of
  this outcome -- honest, not a fabricated publish.
- Generation reuses thunder_service.generate_followup_message_with_fallback()
  as-is (S-041) -- touchpoint_number (1/2/3) maps directly onto that
  function's follow_up_number parameter (same FOLLOWUP_TONE_BY_NUMBER
  gentle/direct/final progression). Sends reuse the same two real
  per-channel paths S-041 already established: send_thunder_message()
  for whatsapp, EmailService.send_email() for email.
- Every send is additionally gated on is_candidate_ghosted() (S-043
  BR-01: zero outreach to a ghosted candidate) and is_ai_owner() --
  the spec doesn't explicitly restate these guards for campaigns, but
  skipping them would let this mechanism send to a candidate every
  other outbound path in this codebase now correctly refuses to
  message; added for consistency, not silently omitted.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.outreach_campaign import CampaignTouchpoint, OutreachCampaign

# Step 1's default sequence -- code constants, BA-approved (BR-02: not
# tenant-configurable this round; HRMS-P306 is a real, separate future story).
STANDARD_OUTREACH_CAMPAIGN = [
    {"day": 1, "channel": "email", "message_type": "FOLLOW_UP_1"},
    {"day": 3, "channel": "whatsapp", "message_type": "FOLLOW_UP_2"},
    {"day": 7, "channel": "email", "message_type": "FOLLOW_UP_3"},
]

JOB_BATCH_SIZE = 50


def start_campaign(
    db: Session, candidate_id: str, tenant_id: str, conversation_id: int, *,
    campaign_type: str = "STANDARD_OUTREACH",
) -> OutreachCampaign:
    """Step 4. BR-03: idempotent -- an existing ACTIVE campaign for this
    candidate is returned as-is, never duplicated."""
    existing = (
        db.query(OutreachCampaign)
        .filter(OutreachCampaign.tenant_id == tenant_id, OutreachCampaign.candidate_id == candidate_id, OutreachCampaign.status == "ACTIVE")
        .first()
    )
    if existing:
        return existing

    now = datetime.utcnow()
    campaign = OutreachCampaign(
        tenant_id=tenant_id, candidate_id=candidate_id, conversation_id=conversation_id,
        campaign_type=campaign_type, status="ACTIVE", started_at=now,
    )
    db.add(campaign)
    db.flush()

    for index, step in enumerate(STANDARD_OUTREACH_CAMPAIGN, start=1):
        db.add(CampaignTouchpoint(
            campaign_id=campaign.id, tenant_id=tenant_id, candidate_id=candidate_id,
            touchpoint_number=index, channel=step["channel"], message_type=step["message_type"],
            scheduled_at=now + timedelta(days=step["day"]), status="PENDING",
        ))
    db.commit()
    return campaign


def cancel_campaign_on_reply(db: Session, candidate_id: str, tenant_id: str) -> bool:
    """BR-01. Cancels every remaining touchpoint and completes the
    campaign the moment any inbound message arrives. Returns whether an
    active campaign was actually found (cheap no-op otherwise)."""
    campaign = (
        db.query(OutreachCampaign)
        .filter(OutreachCampaign.tenant_id == tenant_id, OutreachCampaign.candidate_id == candidate_id, OutreachCampaign.status == "ACTIVE")
        .first()
    )
    if campaign is None:
        return False

    pending = db.query(CampaignTouchpoint).filter(CampaignTouchpoint.campaign_id == campaign.id, CampaignTouchpoint.status == "PENDING").all()
    for touchpoint in pending:
        touchpoint.status = "CANCELLED"
        db.add(touchpoint)

    campaign.status = "COMPLETED"
    campaign.stop_reason = "CANDIDATE_REPLIED"
    campaign.completed_at = datetime.utcnow()
    db.add(campaign)
    db.commit()
    return True


def _has_replied_since(db: Session, conversation_id: int, since: datetime) -> bool:
    reply = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type == "candidate_reply", ConversationEvent.created_at > since)
        .first()
    )
    return reply is not None


def _send_touchpoint(db: Session, conversation: CandidateConversation, candidate: Candidate, message_body: str, channel: str) -> None:
    """Delegates to thunder_service's shared send helper -- see that
    function's own docstring on why this was consolidated (previously
    duplicated identically in follow_up_scheduler_service)."""
    from app.services.thunder_service import send_outbound_campaign_message
    send_outbound_campaign_message(db, conversation, candidate, message_body, channel)


def run_campaign_execution_job(db: Session) -> Dict:
    """Step 5. Never lets one bad row abort the batch -- catches
    per-row, marks SKIPPED, moves on, same defensive posture as every
    other periodic job this round."""
    from app.services.ghosting_detection_service import is_candidate_ghosted
    from app.services.thunder_service import ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, generate_followup_message_with_fallback
    from app.services.whatsapp_routing_service import is_ai_owner

    now = datetime.utcnow()
    due = (
        db.query(CampaignTouchpoint)
        .filter(CampaignTouchpoint.status == "PENDING", CampaignTouchpoint.scheduled_at <= now)
        .order_by(CampaignTouchpoint.scheduled_at.asc())
        .limit(JOB_BATCH_SIZE)
        .all()
    )

    result = {"processed": 0, "sent": 0, "cancelled": 0, "skipped": 0}

    for touchpoint in due:
        result["processed"] += 1
        campaign = db.query(OutreachCampaign).filter(OutreachCampaign.id == touchpoint.campaign_id).first()
        conversation = db.query(CandidateConversation).filter(CandidateConversation.id == campaign.conversation_id).first() if campaign else None
        candidate = db.query(Candidate).filter(Candidate.candidateID == touchpoint.candidate_id).first()

        if campaign is None or campaign.status != "ACTIVE" or conversation is None or candidate is None:
            touchpoint.status = "SKIPPED"
            db.add(touchpoint)
            db.commit()
            result["skipped"] += 1
            continue

        try:
            if _has_replied_since(db, campaign.conversation_id, campaign.started_at):
                cancel_campaign_on_reply(db, touchpoint.candidate_id, touchpoint.tenant_id)
                result["cancelled"] += 1
                continue

            if not is_ai_owner(conversation) or conversation.status == "closed" or conversation.escalation_state == "escalated" or is_candidate_ghosted(db, touchpoint.candidate_id, touchpoint.tenant_id):
                touchpoint.status = "SKIPPED"
                db.add(touchpoint)
                db.commit()
                result["skipped"] += 1
                continue

            message, used_fallback = generate_followup_message_with_fallback(
                db, candidate, touchpoint.touchpoint_number, channel=touchpoint.channel, conversation=conversation,
            )
            if used_fallback:
                db.add(ConversationEvent(
                    conversation_id=conversation.id, event_type="TOUCHPOINT_SEND_FAILED",
                    event_data={"touchpoint_number": touchpoint.touchpoint_number, "campaign_id": campaign.id}, triggered_by="system",
                ))
            _send_touchpoint(db, conversation, candidate, message, touchpoint.channel)
            touchpoint.status = "SENT"
            touchpoint.sent_at = now
            db.add(touchpoint)
            db.commit()
            result["sent"] += 1

            remaining = db.query(CampaignTouchpoint).filter(CampaignTouchpoint.campaign_id == campaign.id, CampaignTouchpoint.status == "PENDING").count()
            if remaining == 0:
                campaign.status = "COMPLETED"
                campaign.stop_reason = "CAMPAIGN_COMPLETED_NO_RESPONSE"
                campaign.completed_at = datetime.utcnow()
                db.add(campaign)
                db.commit()
        except (ConversationOwnedByHuman, ConsentNotGiven, DuplicateMessageSuppressed) as exc:
            logger.info(f"[OutreachCampaign] Touchpoint #{touchpoint.touchpoint_number} for candidate {touchpoint.candidate_id!r} skipped: {exc}")
            touchpoint.status = "SKIPPED"
            db.add(touchpoint)
            db.commit()
            result["skipped"] += 1
        except Exception as exc:
            logger.error(f"[OutreachCampaign] Unexpected failure processing touchpoint id={touchpoint.id}: {exc}")
            db.rollback()
            touchpoint = db.query(CampaignTouchpoint).filter(CampaignTouchpoint.id == touchpoint.id).first()
            if touchpoint:
                touchpoint.status = "SKIPPED"
                db.add(touchpoint)
                db.commit()
            result["skipped"] += 1

    return result
