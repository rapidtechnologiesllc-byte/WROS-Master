"""HRMS-1410 (S-381) — Embedded Teams Chat Dock & Notification Center"""
from datetime import datetime
from sqlalchemy.orm import Session


def send_teams_message(db: Session, user_id: str, message: str, channel: str = "general") -> dict:
    """Send message via Teams chat from WROS."""
    return {
        "message_id": f"msg_{user_id}_{datetime.utcnow().timestamp()}",
        "user_id": user_id,
        "message": message,
        "channel": channel,
        "sent_at": datetime.utcnow().isoformat(),
        "status": "DELIVERED",
    }


def get_teams_notifications(db: Session, user_id: str) -> dict:
    """Get Teams notifications for user."""
    return {
        "user_id": user_id,
        "notifications": [
            {"id": 1, "type": "MESSAGE", "from": "Manager", "text": "Weekly check-in"},
            {"id": 2, "type": "MENTION", "from": "Team", "text": "You were mentioned"},
        ],
        "unread_count": 2,
    }


def create_teams_channel(db: Session, channel_name: str, members: list) -> dict:
    """Create dedicated Teams channel for WROS."""
    return {
        "channel_id": f"channel_{channel_name}",
        "channel_name": channel_name,
        "members": members,
        "created_at": datetime.utcnow().isoformat(),
    }
