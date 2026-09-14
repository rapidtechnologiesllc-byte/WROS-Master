"""Helper for safe ConversationEvent writes with error recovery (HIGH FIX #3)

Wraps all ConversationEvent creation in try/except to prevent handler crashes
if conversation_events table becomes unavailable or schema changes.
"""
import logging
from app.models.candidate_ai import ConversationEvent

logger = logging.getLogger(__name__)

def safe_create_conversation_event(db, conversation_id, event_type, event_data=None, 
                                   triggered_by="system", tenant_id=None):
    """Safely create a ConversationEvent with error recovery.
    
    HIGH FIX #3: Wraps event creation in try/except to prevent cascade failures
    if conversation_events table unavailable or schema mismatches.
    
    Args:
        db: Database session
        conversation_id: ID of the conversation
        event_type: Type of event (string)
        event_data: Optional JSON event data
        triggered_by: Who triggered the event (default: "system")
        tenant_id: Tenant ID (required for isolation)
    
    Returns:
        ConversationEvent if created, None if error occurred
    """
    if not tenant_id:
        logger.warning(f"safe_create_conversation_event: Missing tenant_id for event {event_type}")
        return None
        
    try:
        event = ConversationEvent(
            conversation_id=conversation_id,
            event_type=event_type,
            event_data=event_data,
            triggered_by=triggered_by,
            tenant_id=tenant_id
        )
        db.add(event)
        db.flush()  # Flush to detect schema issues early
        return event
    except Exception as e:
        # HIGH FIX #3: Log but don't crash - event logging is non-critical
        logger.error(
            f"Failed to create ConversationEvent {event_type} for conversation {conversation_id}: {e}",
            exc_info=True
        )
        try:
            db.rollback()
        except:
            pass
        return None
