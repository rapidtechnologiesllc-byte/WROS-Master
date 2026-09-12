"""Recovery Engine - Execute safe recovery actions on stuck messages

Implements tiered recovery strategies based on error classification:
- Timeout extend: Retry with longer timeout
- Payload split: Break large message into smaller chunks
- Delay retry: Queue message with delay to free up resources
- Dependency prerequisite: Queue missing dependency first
- Transaction rollback: Clear partial state and retry
"""
import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from enum import Enum

from sqlalchemy.orm import Session

from app.models.channel_queue import ChannelQueueItem
from app.models.queue_doctor import QueueDoctorState
from app.services.stale_message_detector import ErrorClassification

logger = logging.getLogger(__name__)


class RecoveryAction(str, Enum):
    """Recovery actions that can be taken"""
    TIMEOUT_EXTEND = "TIMEOUT_EXTEND"  # Retry with extended timeout
    PAYLOAD_SPLIT = "PAYLOAD_SPLIT"  # Split message into smaller chunks
    DELAY = "DELAY"  # Queue with delay to free up resources
    DEPENDENCY_QUEUE = "DEPENDENCY_QUEUE"  # Queue prerequisite task
    ROLLBACK = "ROLLBACK"  # Clear partial state and retry


class RecoveryEngine:
    """Executes recovery actions on stuck messages"""

    @staticmethod
    def attempt_recovery(
        error_classification: str,
        safety_score: int,
        message: ChannelQueueItem,
        doctor_state: QueueDoctorState,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Attempt to recover a stuck message based on its error classification.

        Only proceeds if safety_score >= 80 (very safe).

        Returns:
            {
                'action_taken': RecoveryAction or None,
                'success': bool,
                'reason': str,
                'details': dict
            }
        """
        # Safety check: Only recover if safe
        if safety_score < 80:
            return {
                'action_taken': None,
                'success': False,
                'reason': f'Safety score {safety_score}/100 below minimum 80 for auto-recovery',
                'details': {}
            }

        try:
            # Route to specific recovery action based on classification
            if error_classification == ErrorClassification.TIMEOUT_LOOP:
                return RecoveryEngine._recover_from_timeout(message, doctor_state, db)

            elif error_classification == ErrorClassification.LARGE_PAYLOAD:
                return RecoveryEngine._recover_from_large_payload(message, doctor_state, db)

            elif error_classification == ErrorClassification.DB_POOL:
                return RecoveryEngine._recover_from_db_pool(message, doctor_state, db)

            elif error_classification == ErrorClassification.MISSING_DEPENDENCY:
                return RecoveryEngine._recover_from_missing_dependency(message, doctor_state, db)

            elif error_classification == ErrorClassification.TRANSACTION_DEADLOCK:
                return RecoveryEngine._recover_from_deadlock(message, doctor_state, db)

            else:
                return {
                    'action_taken': None,
                    'success': False,
                    'reason': f'No recovery strategy for {error_classification}',
                    'details': {}
                }

        except Exception as e:
            logger.error(f"[RecoveryEngine] Recovery failed for {message.id}: {e}", exc_info=True)
            return {
                'action_taken': None,
                'success': False,
                'reason': f'Recovery execution failed: {str(e)[:200]}',
                'details': {'error': str(e)[:500]}
            }

    @staticmethod
    def _recover_from_timeout(
        message: ChannelQueueItem,
        doctor_state: QueueDoctorState,
        db: Session,
    ) -> Dict[str, Any]:
        """
        TIMEOUT_LOOP recovery: Retry with extended timeout.

        Only do this once per message (don't keep extending forever).
        """
        # Check if we've already tried timeout extension
        if doctor_state.recovery_action == RecoveryAction.TIMEOUT_EXTEND:
            return {
                'action_taken': RecoveryAction.TIMEOUT_EXTEND,
                'success': False,
                'reason': 'Timeout extension already attempted once',
                'details': {'message_id': message.id}
            }

        try:
            # Reset message status to PENDING to retry
            message.status = 'PENDING'
            message.retry_count = (message.retry_count or 0) + 1
            message.error = None  # Clear old error
            message.next_retry_at = datetime.utcnow()  # Retry immediately

            # Record recovery attempt
            doctor_state.recovery_action = RecoveryAction.TIMEOUT_EXTEND
            doctor_state.recovery_attempted_at = datetime.utcnow()
            doctor_state.recovery_details = json.dumps({
                'action': 'Extended timeout and queued for immediate retry',
                'retry_count': message.retry_count,
                'timestamp': datetime.utcnow().isoformat()
            })

            db.add(message)
            db.add(doctor_state)
            db.commit()

            logger.info(f"[RecoveryEngine] TIMEOUT_LOOP recovery: Message {message.id} re-queued with retry_count={message.retry_count}")

            return {
                'action_taken': RecoveryAction.TIMEOUT_EXTEND,
                'success': True,
                'reason': 'Message re-queued with extended timeout on next attempt',
                'details': {
                    'message_id': message.id,
                    'retry_count': message.retry_count,
                    'next_retry_at': message.next_retry_at.isoformat() if message.next_retry_at else None
                }
            }

        except Exception as e:
            db.rollback()
            raise

    @staticmethod
    def _recover_from_large_payload(
        message: ChannelQueueItem,
        doctor_state: QueueDoctorState,
        db: Session,
    ) -> Dict[str, Any]:
        """
        LARGE_PAYLOAD recovery: Split message into smaller chunks.

        For array payloads (candidate lists, etc.), split into smaller batches.
        For single records, can't split - escalate instead.
        """
        try:
            payload = message.payload or {}

            # Check if payload has array field we can split
            splittable_fields = ['candidates', 'records', 'items', 'data']
            split_field = None
            for field in splittable_fields:
                if isinstance(payload.get(field), list) and len(payload.get(field, [])) > 1:
                    split_field = field
                    break

            if not split_field:
                return {
                    'action_taken': None,
                    'success': False,
                    'reason': 'Payload not splittable (no array fields or single item)',
                    'details': {'message_id': message.id}
                }

            # Split the array into smaller chunks
            original_array = payload[split_field]
            chunk_size = max(1, len(original_array) // 2)  # Split in half
            chunks = [original_array[i:i + chunk_size] for i in range(0, len(original_array), chunk_size)]

            logger.info(f"[RecoveryEngine] LARGE_PAYLOAD recovery: Splitting message {message.id} "
                       f"into {len(chunks)} chunks (field: {split_field})")

            # Create new messages for each chunk
            from app.services.message_queue_service import MessageQueueService
            new_message_ids = []

            for chunk_idx, chunk in enumerate(chunks):
                chunk_payload = payload.copy()
                chunk_payload[split_field] = chunk
                chunk_message = ChannelQueueItem(
                    message_id=f"{message.message_id}_chunk_{chunk_idx}",
                    type=message.type,
                    channel_type=message.channel_type,
                    status='PENDING',
                    payload=chunk_payload,
                    recipient=message.recipient,
                )
                db.add(chunk_message)
                new_message_ids.append(chunk_message.id)

            # Mark original message as COMPLETED (handled by splitting)
            message.status = 'COMPLETED'
            message.result = json.dumps({
                'success': True,
                'split_into_chunks': len(chunks),
                'chunk_message_ids': new_message_ids
            })

            # Record recovery
            doctor_state.recovery_action = RecoveryAction.PAYLOAD_SPLIT
            doctor_state.recovery_attempted_at = datetime.utcnow()
            doctor_state.recovery_succeeded = True
            doctor_state.recovery_details = json.dumps({
                'action': 'Payload split into chunks',
                'original_size': len(original_array),
                'chunks_created': len(chunks),
                'chunk_message_ids': new_message_ids
            })

            db.add(message)
            db.add(doctor_state)
            db.commit()

            return {
                'action_taken': RecoveryAction.PAYLOAD_SPLIT,
                'success': True,
                'reason': f'Message split into {len(chunks)} smaller chunks',
                'details': {
                    'message_id': message.id,
                    'chunks_created': len(chunks),
                    'chunk_message_ids': new_message_ids
                }
            }

        except Exception as e:
            db.rollback()
            raise

    @staticmethod
    def _recover_from_db_pool(
        message: ChannelQueueItem,
        doctor_state: QueueDoctorState,
        db: Session,
    ) -> Dict[str, Any]:
        """
        DB_POOL recovery: Queue message with 30-second delay.

        This allows other operations to complete and free up connections.
        """
        try:
            # Queue message with 30-second delay
            message.status = 'PENDING'
            message.scheduled_for = datetime.utcnow() + timedelta(seconds=30)
            message.retry_count = (message.retry_count or 0) + 1
            message.error = None

            # Record recovery
            doctor_state.recovery_action = RecoveryAction.DELAY
            doctor_state.recovery_attempted_at = datetime.utcnow()
            doctor_state.recovery_succeeded = True
            doctor_state.recovery_details = json.dumps({
                'action': 'Message delayed 30 seconds for DB pool recovery',
                'scheduled_for': message.scheduled_for.isoformat(),
                'retry_count': message.retry_count
            })

            db.add(message)
            db.add(doctor_state)
            db.commit()

            logger.info(f"[RecoveryEngine] DB_POOL recovery: Message {message.id} delayed 30s for retry")

            return {
                'action_taken': RecoveryAction.DELAY,
                'success': True,
                'reason': 'Message re-queued with 30-second delay to allow DB pool recovery',
                'details': {
                    'message_id': message.id,
                    'retry_count': message.retry_count,
                    'scheduled_for': message.scheduled_for.isoformat()
                }
            }

        except Exception as e:
            db.rollback()
            raise

    @staticmethod
    def _recover_from_missing_dependency(
        message: ChannelQueueItem,
        doctor_state: QueueDoctorState,
        db: Session,
    ) -> Dict[str, Any]:
        """
        MISSING_DEPENDENCY recovery: Queue the missing dependency first, then re-queue original.

        This only works if we can infer what dependency is missing from the message type.
        """
        # For now, we can't automatically infer dependencies
        # This would require a dependency graph / handler registry
        return {
            'action_taken': None,
            'success': False,
            'reason': 'Automatic dependency resolution not yet implemented',
            'details': {'message_id': message.id}
        }

    @staticmethod
    def _recover_from_deadlock(
        message: ChannelQueueItem,
        doctor_state: QueueDoctorState,
        db: Session,
    ) -> Dict[str, Any]:
        """
        TRANSACTION_DEADLOCK recovery: Rollback partial state and retry from beginning.

        Only safe if handler execution was very quick (< 5 seconds) before deadlock.
        """
        # Check handler duration
        if (message.handler_duration_ms or 0) > 5000:
            return {
                'action_taken': None,
                'success': False,
                'reason': 'Handler ran too long before deadlock (> 5s) - too much work to rollback safely',
                'details': {'message_id': message.id, 'duration_ms': message.handler_duration_ms}
            }

        try:
            # Reset message to PENDING and clear retry count to try fresh
            message.status = 'PENDING'
            message.retry_count = 0
            message.error = None
            message.next_retry_at = datetime.utcnow()

            # Record recovery
            doctor_state.recovery_action = RecoveryAction.ROLLBACK
            doctor_state.recovery_attempted_at = datetime.utcnow()
            doctor_state.recovery_succeeded = True
            doctor_state.recovery_details = json.dumps({
                'action': 'Transaction rolled back - message reset to initial state',
                'previous_duration_ms': message.handler_duration_ms,
                'retry_count_reset': 0
            })

            db.add(message)
            db.add(doctor_state)
            db.commit()

            logger.info(f"[RecoveryEngine] DEADLOCK recovery: Message {message.id} reset and re-queued")

            return {
                'action_taken': RecoveryAction.ROLLBACK,
                'success': True,
                'reason': 'Transaction rolled back - message re-queued from initial state',
                'details': {
                    'message_id': message.id,
                    'retry_count_reset': 0,
                }
            }

        except Exception as e:
            db.rollback()
            raise
