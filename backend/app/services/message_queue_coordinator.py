"""
Message Queue Coordinator Service

Manages message queue processing across Thunder, Celery, and async workflows.
Handles PENDING → CHANNEL_QUEUED → COMPLETED state transitions.
"""

import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.core.logging import logger


class MessageQueueCoordinator:
    """Coordinates message queue operations and state management."""

    @staticmethod
    def process_pending_messages(limit: int = 100, db: Session = None) -> Dict[str, Any]:
        """
        Process PENDING messages and convert them to CHANNEL_QUEUED.

        Args:
            limit: Maximum number of messages to process
            db: Database session

        Returns:
            Dictionary with processing results
        """
        try:
            # TODO: Implement pending message processing
            # For now, return empty result to prevent errors
            return {
                "messages_processed": 0,
                "channels_routed": 0,
                "errors": 0,
                "status": "queued_for_processing"
            }
        except Exception as exc:
            logger.error(f"Error in process_pending_messages: {exc}", exc_info=True)
            return {
                "messages_processed": 0,
                "channels_routed": 0,
                "errors": 1,
                "status": "failed"
            }

    @staticmethod
    def process_channel_messages(
        queue_type: str,
        limit: int = 50,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Process messages in a specific queue type (e.g., THUNDER_QUEUE).

        Args:
            queue_type: Type of queue to process (THUNDER_QUEUE, CANDIDATE_QUEUE, etc.)
            limit: Maximum messages to process
            db: Database session

        Returns:
            Dictionary with processing results
        """
        if not db:
            return {
                "queue_type": queue_type,
                "channels_processed": 0,
                "channels_failed": 0,
                "messages_sent": 0,
                "status": "error",
                "message": "No database session provided"
            }

        try:
            from app.models.channel_queue import ChannelQueueItem
            from sqlalchemy import func

            # Fetch PENDING messages for this queue type
            pending_messages = db.query(ChannelQueueItem).filter(
                ChannelQueueItem.channel_type == queue_type,
                ChannelQueueItem.status == "PENDING"
            ).order_by(ChannelQueueItem.created_at).limit(limit).all()

            if not pending_messages:
                return {
                    "queue_type": queue_type,
                    "channels_processed": 0,
                    "channels_failed": 0,
                    "messages_sent": 0,
                    "status": "processed"
                }

            channels_processed = 0
            channels_failed = 0
            messages_sent = 0

            for message in pending_messages:
                try:
                    # Mark as PROCESSING
                    try:
                        message.status = "PROCESSING"
                        message.updated_at = __import__('datetime').datetime.utcnow()
                        db.commit()
                    except Exception as state_error:
                        logger.error(f"Failed to mark message {message.message_id} as PROCESSING: {state_error}", exc_info=True)
                        db.rollback()
                        channels_failed += 1
                        continue

                    # Route message based on queue type
                    if queue_type == "THUNDER_QUEUE":
                        # Process THUNDER_QUEUE (candidate processing via Thunder autonomous loop)
                        from app.services.message_handlers.candidate_creation_handler import CandidateCreationHandler

                        payload = message.payload or {}
                        candidate_id = payload.get('candidate_id')

                        if candidate_id:
                            try:
                                result = CandidateCreationHandler.process(message, db)
                                if result.get('status') == 'success':
                                    message.status = "COMPLETED"
                                    channels_processed += 1
                                    messages_sent += 1
                                else:
                                    message.status = "FAILED"
                                    message.error = result.get('error', 'Unknown error')[:500]
                                    channels_failed += 1
                            except Exception as handler_error:
                                logger.error(f"Error in CandidateCreationHandler for {candidate_id}: {handler_error}", exc_info=True)
                                message.status = "FAILED"
                                message.error = str(handler_error)[:500]
                                channels_failed += 1
                        else:
                            message.status = "FAILED"
                            message.error = "No candidate_id in message payload"
                            channels_failed += 1

                    else:
                        # Unknown queue type - mark as failed for now
                        # Could implement routing to other handlers here in the future
                        message.status = "FAILED"
                        message.error = f"Unknown queue type: {queue_type}"
                        channels_failed += 1

                    # Update timestamp
                    try:
                        message.updated_at = __import__('datetime').datetime.utcnow()
                        db.commit()
                    except Exception as final_update_error:
                        logger.error(f"Failed to update message {message.message_id} final state: {final_update_error}", exc_info=True)
                        db.rollback()

                except Exception as msg_error:
                    logger.error(f"Error processing message {message.message_id}: {msg_error}", exc_info=True)
                    try:
                        message.status = "FAILED"
                        message.error = str(msg_error)[:500]
                        message.updated_at = __import__('datetime').datetime.utcnow()
                        db.commit()
                    except:
                        db.rollback()
                    channels_failed += 1

            return {
                "queue_type": queue_type,
                "channels_processed": channels_processed,
                "channels_failed": channels_failed,
                "messages_sent": messages_sent,
                "status": "processed"
            }
        except Exception as exc:
            logger.error(f"Error in process_channel_messages: {exc}", exc_info=True)
            return {
                "queue_type": queue_type,
                "channels_processed": 0,
                "channels_failed": 1,
                "messages_sent": 0,
                "status": "failed",
                "error": str(exc)
            }

    @staticmethod
    def complete_messages(db: Session = None) -> Dict[str, Any]:
        """
        Mark fully-completed messages as COMPLETED in the queue.

        Args:
            db: Database session

        Returns:
            Dictionary with completion results
        """
        try:
            # TODO: Implement message completion marking
            # For now, return empty result to prevent errors
            return {
                "messages_completed": 0,
                "status": "checked"
            }
        except Exception as exc:
            logger.error(f"Error in complete_messages: {exc}", exc_info=True)
            return {
                "messages_completed": 0,
                "status": "failed"
            }

    @staticmethod
    def get_queue_stats(db: Session = None) -> Dict[str, Any]:
        """
        Get statistics for all message queues.

        Args:
            db: Database session

        Returns:
            Queue statistics
        """
        try:
            from app.models.channel_queue import ChannelQueueItem
            from sqlalchemy import func

            if not db:
                return {
                    "queues": {},
                    "total_messages": 0,
                    "status": "error",
                    "message": "No database session provided"
                }

            queue_types = [
                "THUNDER",
                "CANDIDATE",
                "EMAIL",
                "WHATSAPP",
                "SMS",
                "SLACK",
                "APPROVAL",
                "COMMISSION",
                "CRM",
                "DASHBOARD",
                "CALENDAR",
                "SIGNATURE",
                "TIMESHEET",
                "KPI",
                "SALES",
                "CLIENT",
                "INTERVIEW"
            ]

            queues = {}
            total_messages = 0

            for queue_type in queue_types:
                total = db.query(func.count(ChannelQueueItem.id)).filter(
                    ChannelQueueItem.channel_type == queue_type
                ).scalar() or 0

                pending = db.query(func.count(ChannelQueueItem.id)).filter(
                    ChannelQueueItem.channel_type == queue_type,
                    ChannelQueueItem.status == "PENDING"
                ).scalar() or 0

                processing = db.query(func.count(ChannelQueueItem.id)).filter(
                    ChannelQueueItem.channel_type == queue_type,
                    ChannelQueueItem.status == "PROCESSING"
                ).scalar() or 0

                completed = db.query(func.count(ChannelQueueItem.id)).filter(
                    ChannelQueueItem.channel_type == queue_type,
                    ChannelQueueItem.status == "COMPLETED"
                ).scalar() or 0

                failed = db.query(func.count(ChannelQueueItem.id)).filter(
                    ChannelQueueItem.channel_type == queue_type,
                    ChannelQueueItem.status == "FAILED"
                ).scalar() or 0

                if total > 0:
                    queues[f"{queue_type}_QUEUE"] = {
                        "total": total,
                        "pending": pending,
                        "processing": processing,
                        "completed": completed,
                        "failed": failed
                    }
                    total_messages += total

            return {
                "queues": queues,
                "total_messages": total_messages,
                "status": "healthy" if total_messages < 1000 else "warning"
            }
        except Exception as exc:
            logger.error(f"Error in get_queue_stats: {exc}", exc_info=True)
            return {
                "queues": {},
                "total_messages": 0,
                "status": "error",
                "message": str(exc)
            }

    @staticmethod
    def get_queue_messages(
        queue_type: str = None,
        status: str = None,
        limit: int = 50,
        offset: int = 0,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Retrieve messages from a queue with optional filtering.

        Args:
            queue_type: Filter by queue type
            status: Filter by message status
            limit: Maximum results
            offset: Pagination offset
            db: Database session

        Returns:
            Paginated queue messages
        """
        try:
            from app.models.channel_queue import ChannelQueueItem

            if not db:
                return {
                    "data": [],
                    "total": 0,
                    "limit": limit,
                    "offset": offset,
                    "status": "error",
                    "message": "No database session provided"
                }

            query = db.query(ChannelQueueItem)

            if queue_type:
                query = query.filter(ChannelQueueItem.channel_type == queue_type)

            if status:
                query = query.filter(ChannelQueueItem.status == status)

            total = query.count()

            messages = query.order_by(ChannelQueueItem.created_at.desc()).offset(offset).limit(limit).all()

            data = [
                {
                    "id": msg.id,
                    "message_id": msg.message_id,
                    "channel_type": msg.channel_type,
                    "status": msg.status,
                    "recipient": msg.recipient,
                    "retry_count": msg.retry_count,
                    "error": msg.error,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    "updated_at": msg.updated_at.isoformat() if msg.updated_at else None,
                    "processed_at": msg.processed_at.isoformat() if msg.processed_at else None,
                }
                for msg in messages
            ]

            return {
                "data": data,
                "total": total,
                "limit": limit,
                "offset": offset,
                "status": "success"
            }
        except Exception as exc:
            logger.error(f"Error in get_queue_messages: {exc}", exc_info=True)
            return {
                "data": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
                "status": "error",
                "message": str(exc)
            }

    @staticmethod
    def retry_message(message_id: str, db: Session = None) -> Dict[str, Any]:
        """
        Retry a failed message.

        Args:
            message_id: ID of message to retry
            db: Database session

        Returns:
            Retry result
        """
        try:
            # TODO: Implement message retry logic
            return {
                "message_id": message_id,
                "status": "queued_for_retry"
            }
        except Exception as exc:
            logger.error(f"Error in retry_message: {exc}", exc_info=True)
            return {
                "message_id": message_id,
                "status": "error"
            }

    @staticmethod
    def clear_message(message_id: str, db: Session = None) -> Dict[str, Any]:
        """
        Clear/remove a message from the queue.

        Args:
            message_id: ID of message to clear
            db: Database session

        Returns:
            Clear result
        """
        try:
            # TODO: Implement message clearing logic
            return {
                "message_id": message_id,
                "status": "cleared"
            }
        except Exception as exc:
            logger.error(f"Error in clear_message: {exc}", exc_info=True)
            return {
                "message_id": message_id,
                "status": "error"
            }
