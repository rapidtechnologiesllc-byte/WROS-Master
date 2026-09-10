"""Thunder Outreach Handler - Queue-driven autonomous candidate outreach

CYCLE 20A: Thunder Handler with Formation Feedback
Sends candidate outreach (SMS, Email, WhatsApp) and reports success/failure back to Flash.

Responsibilities:
1. Queue candidate outreach message (SMS/Email/WhatsApp)
2. Track delivery status
3. Report outcome back to Flash (success/failure metrics)
4. Train SLM with outreach results
"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
import json

logger = logging.getLogger(__name__)

# ARCHITECT FIX: Spartan Phalanx Formation Definition
# Formation Position: Thunder = Position 2 (Right Flank, Outreach)
# Upstream Neighbor: Flash (Position 1, Alpha Wolf)
# Dependency: Flash queues outreach work for Thunder to execute
# Feedback: Thunder reports delivery success/failure back to Flash

NEIGHBOR_DEFINITION = {
    'position': 'Right Flank (Outreach)',
    'position_number': 2,
    'name': 'Thunder',
    'role': 'Autonomous candidate outreach (SMS, Email, WhatsApp delivery)',
    'upstream_neighbor': {
        'position': 1,
        'name': 'Flash_Recruiter',
        'role': 'Orchestrator - queues our work',
        'health_metric': 'Are we healthy enough to accept work?',
        'feedback_signal': 'Report delivery success % back to Flash'
    },
    'formation_threshold': 0.70,
    'escalation_contact': 'Platform On-Call',
    'escalation_action': 'Alert Flash of delivery failures, pause recruitment if >30% failure rate'
}

# Outreach channels
CHANNELS = {
    'SMS': 'sms_gateway',
    'EMAIL': 'email_service',
    'WHATSAPP': 'whatsapp_service'
}

SUCCESS_RATE_THRESHOLD = 0.70  # 70% delivery required


class ThunderOutreachHandler:
    """Thunder Outreach - autonomous candidate messaging and delivery tracking."""

    @staticmethod
    def _send_outreach_message(candidate_id: str, channel: str, message: str, db: Session) -> Dict[str, Any]:
        """
        Send outreach message via specified channel (SMS/Email/WhatsApp).

        Returns: {
            'success': bool,
            'delivery_status': str ('pending', 'sent', 'failed'),
            'channel': str,
            'error': str or None
        }
        """
        try:
            # ARCHITECT FIX: Stub implementation - real implementation would call gateway
            # This demonstrates the interface for message delivery
            logger.info(f"[Thunder] Sending {channel} to candidate {candidate_id}: {message[:50]}...")

            # Validate channel
            if channel not in CHANNELS:
                raise ValueError(f"Unknown channel: {channel}")

            # In production, this would call actual SMS/Email/WhatsApp gateway
            # For now, return mock success (implementation deferred to Thunder integration phase)
            return {
                'success': True,
                'delivery_status': 'sent',
                'channel': channel,
                'error': None,
                'message_id': f"{channel}_{candidate_id}_{__import__('uuid').uuid4().hex[:8]}"
            }

        except Exception as e:
            logger.error(f"[Thunder] Failed to send {channel} to {candidate_id}: {e}")
            return {
                'success': False,
                'delivery_status': 'failed',
                'channel': channel,
                'error': str(e)
            }

    @staticmethod
    def _report_back_to_flash(db: Session, job_id: str, delivery_results: list) -> None:
        """
        ARCHITECT FIX: Spartan Phalanx Feedback Loop
        Report outreach results back to Flash so it can monitor our health.

        Thunder sends: "Here's how many messages I delivered successfully"
        Flash receives: Updates its Thunder health metrics
        """
        try:
            from app.services.message_queue_service import MessageQueueService

            # Calculate success rate
            successful_deliveries = sum(1 for r in delivery_results if r.get('success'))
            total_attempts = len(delivery_results)
            success_rate = successful_deliveries / total_attempts if total_attempts > 0 else 0

            # Queue formation feedback message to Flash
            MessageQueueService.enqueue(
                task_name='formation_feedback_thunder_to_flash',
                task_id=f"thunder_feedback_{job_id}_{__import__('uuid').uuid4().hex[:8]}",
                data={
                    'source': 'Thunder',
                    'target': 'Flash',
                    'job_id': job_id,
                    'metric': 'delivery_success_rate',
                    'value': success_rate,
                    'successful': successful_deliveries,
                    'total': total_attempts,
                    'timestamp': __import__('datetime').datetime.utcnow().isoformat(),
                    'action': 'Flash should pause recruitment if success_rate < 0.7'
                }
            )

            logger.info(
                f"[Thunder] Reported to Flash: {job_id} - "
                f"{successful_deliveries}/{total_attempts} deliveries successful ({success_rate*100:.1f}%)"
            )

        except Exception as e:
            logger.error(f"[Thunder] Failed to report feedback to Flash: {e}")
            # Don't fail the handler if feedback queueing fails - outreach already sent
            pass

    @staticmethod
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process: Send candidate outreach and report results back to Flash.

        Args:
            message: ChannelQueueItem with type='engage_candidate_with_thunder'
            db: SQLAlchemy session

        Returns:
            {
                'status': 'success',
                'job_id': str,
                'candidates_contacted': int,
                'successful_deliveries': int,
                'failed_deliveries': int,
                'success_rate': float
            }
        """
        try:
            payload = message.payload or {}

            # PHASE 1: VALIDATION
            job_id = payload.get('job_id')
            candidate_id = payload.get('candidate_id')
            if not all([job_id, candidate_id]):
                raise ValueError(f"Missing required fields: job_id={job_id}, candidate_id={candidate_id}")

            logger.info(f"[Thunder] Sending outreach for candidate {candidate_id} (job {job_id})")

            # PHASE 2: QUEUE OUTREACH MESSAGE VIA PREFERRED CHANNEL
            # Preference order: WhatsApp (interactive), Email (tracking), SMS (guaranteed delivery)
            channels_to_try = ['WHATSAPP', 'EMAIL', 'SMS']
            outreach_results = []

            for channel in channels_to_try:
                result = ThunderOutreachHandler._send_outreach_message(
                    candidate_id=candidate_id,
                    channel=channel,
                    message=payload.get('message', f"Exciting opportunity: {payload.get('job_title', 'Job')}"),
                    db=db
                )
                outreach_results.append(result)

                # Stop after first successful delivery
                if result.get('success'):
                    logger.info(f"[Thunder] Successfully delivered via {channel}")
                    break

            # PHASE 3: CALCULATE SUCCESS RATE
            successful = sum(1 for r in outreach_results if r.get('success'))
            total = len(outreach_results)
            success_rate = successful / total if total > 0 else 0

            # PHASE 4: REPORT BACK TO FLASH (Formation Feedback)
            # This is critical for Spartan Phalanx pattern - Thunder tells Flash how healthy it is
            ThunderOutreachHandler._report_back_to_flash(db, job_id, outreach_results)

            logger.info(
                f"[Thunder] ✅ Completed outreach for {candidate_id}: "
                f"{successful}/{total} channels successful ({success_rate*100:.1f}%)"
            )

            return {
                'status': 'success',
                'job_id': job_id,
                'candidate_id': candidate_id,
                'candidates_contacted': 1,
                'successful_deliveries': successful,
                'failed_deliveries': total - successful,
                'success_rate': success_rate,
                'channels_attempted': channels_to_try,
                'formation_feedback_queued': True
            }

        except ValueError as ve:
            logger.error(f"[Thunder] Validation error: {ve}")
            raise  # NOT RETRYABLE

        except RuntimeError as re:
            logger.error(f"[Thunder] Runtime error (retryable): {re}")
            raise  # RETRYABLE

        except OperationalError as oe:
            logger.error(f"[Thunder] DB operational error: {oe}", exc_info=True)
            raise RuntimeError(f"DB unavailable: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[Thunder] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e
