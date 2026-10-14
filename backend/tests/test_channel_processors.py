"""Unit tests for channel processors - EMAIL, WHATSAPP, SMS, etc."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from app.workers.channel_processors import ChannelProcessors
from app.services.channel_queue_service import ChannelQueueService
from app.models.channel_queue import ChannelQueueItem
from tests import factories


@pytest.fixture
def test_db(db):
    """The shared PostgreSQL test session (tests/conftest.py), with tenant 1 present."""
    factories.tenant(db)
    return db


class TestEmailProcessor:
    """Test EMAIL channel processor"""

    def test_email_with_valid_recipient(self, test_db: Session):
        """Email processor should fail gracefully when Microsoft Graph not configured"""
        item = ChannelQueueItem(
            tenant_id=1,
            id="test-email-001",
            message_id="msg-001",
            type="send_email",
            channel_type="EMAIL",
            status="PENDING",
            payload={
                "subject": "Test Subject",
                "body": "Test Body",
                "is_html": False,
            },
            recipient="test@example.com",
        )
        test_db.add(item)
        test_db.commit()

        # Email processor will fail due to missing Graph token, but shouldn't crash
        with patch('app.services.email_service.EmailService._get_token') as mock_token:
            mock_token.side_effect = Exception("Graph token not configured")
            result = ChannelProcessors.process_email(item.id, item.recipient, item.payload, test_db)

        # Should return False (failed)
        assert result is False

        # Check item is marked as failed
        updated = test_db.query(ChannelQueueItem).filter_by(id=item.id).first()
        assert updated.status == "FAILED"
        assert "not configured" in updated.error  # nothing was sent, and the item says why

    def test_email_is_completed_only_after_the_mailbox_sends_it(self, test_db: Session):
        item = ChannelQueueItem(tenant_id=1, id="test-email-ok", message_id="msg-ok", type="send_email",
                                channel_type="EMAIL", status="PENDING", recipient="ok@example.com",
                                payload={"subject": "Hi", "body": "<p>Hi</p>", "is_html": True})
        test_db.add(item)
        test_db.commit()
        with patch("app.services.email_service.EmailService.send_email", return_value={"status": "sent"}) as send:
            assert ChannelProcessors.process_email(item.id, item.recipient, item.payload, test_db) is True
        assert send.call_args.kwargs["to_email"] == "ok@example.com"
        assert test_db.query(ChannelQueueItem).filter_by(id=item.id).one().status == "COMPLETED"

    def test_email_missing_recipient(self, test_db: Session):
        """Email processor should reject messages with no recipient"""
        item = ChannelQueueItem(
            tenant_id=1,
            id="test-email-no-recipient",
            message_id="msg-002",
            type="send_email",
            channel_type="EMAIL",
            status="PENDING",
            payload={"subject": "Test", "body": "Test"},
            recipient=None,  # Missing recipient
        )
        test_db.add(item)
        test_db.commit()

        result = ChannelProcessors.process_email(item.id, item.recipient, item.payload, test_db)

        assert result is False
        updated = test_db.query(ChannelQueueItem).filter_by(id=item.id).first()
        assert updated.status == "FAILED"
        assert "No recipient" in updated.error


class TestWhatsAppProcessor:
    """Test WHATSAPP channel processor"""

    def test_whatsapp_not_implemented(self, test_db: Session):
        """WHATSAPP processor should fail with clear 'not implemented' message"""
        item = ChannelQueueItem(
            tenant_id=1,
            id="test-whatsapp-001",
            message_id="msg-003",
            type="send_whatsapp",
            channel_type="WHATSAPP",
            status="PENDING",
            payload={"message": "Test WhatsApp"},
            recipient="+1234567890",
        )
        test_db.add(item)
        test_db.commit()

        result = ChannelProcessors.process_whatsapp(item.id, item.recipient, item.payload, test_db)

        assert result is False
        updated = test_db.query(ChannelQueueItem).filter_by(id=item.id).first()
        assert updated.status == "FAILED"
        assert "not yet configured" in updated.error.lower()

    def test_whatsapp_missing_recipient(self, test_db: Session):
        """WHATSAPP processor should reject messages with no phone number"""
        item = ChannelQueueItem(
            tenant_id=1,
            id="test-whatsapp-no-phone",
            message_id="msg-004",
            type="send_whatsapp",
            channel_type="WHATSAPP",
            status="PENDING",
            payload={"message": "Test"},
            recipient=None,
        )
        test_db.add(item)
        test_db.commit()

        result = ChannelProcessors.process_whatsapp(item.id, item.recipient, item.payload, test_db)

        assert result is False
        updated = test_db.query(ChannelQueueItem).filter_by(id=item.id).first()
        assert "No WhatsApp number" in updated.error


class TestSMSProcessor:
    """Test SMS channel processor"""

    def test_sms_not_implemented(self, test_db: Session):
        """SMS processor should fail with 'not implemented' message"""
        item = ChannelQueueItem(
            tenant_id=1,
            id="test-sms-001",
            message_id="msg-005",
            type="send_sms",
            channel_type="SMS",
            status="PENDING",
            payload={"message": "Test SMS"},
            recipient="+1234567890",
        )
        test_db.add(item)
        test_db.commit()

        result = ChannelProcessors.process_sms(item.id, item.recipient, item.payload, test_db)

        assert result is False
        updated = test_db.query(ChannelQueueItem).filter_by(id=item.id).first()
        assert updated.status == "FAILED"
        assert "not yet configured" in updated.error.lower()


class TestChannelQueueService:
    """Test ChannelQueueService lifecycle management"""

    def test_mark_completed(self, test_db: Session):
        """Service should mark items as COMPLETED with result data"""
        item = ChannelQueueItem(
            tenant_id=1,
            id="test-complete",
            message_id="msg-100",
            type="test",
            channel_type="EMAIL",
            status="PROCESSING",
            payload={},
            recipient="test@example.com",
        )
        test_db.add(item)
        test_db.commit()

        result = ChannelQueueService.mark_completed(
            item.id,
            test_db,
            result={"delivery_id": "graph-12345"},
        )

        assert result is True
        updated = test_db.query(ChannelQueueItem).filter_by(id=item.id).first()
        assert updated.status == "COMPLETED"
        assert updated.result["delivery_id"] == "graph-12345"

    def test_mark_failed_transient(self, test_db: Session):
        """Service should mark transient errors for retry"""
        item = ChannelQueueItem(
            tenant_id=1,
            id="test-fail-transient",
            message_id="msg-101",
            type="test",
            channel_type="EMAIL",
            status="PROCESSING",
            payload={},
            recipient="test@example.com",
        )
        test_db.add(item)
        test_db.commit()

        result = ChannelQueueService.mark_failed(
            item.id,
            "Connection timeout",
            should_retry=True,
            db=test_db,
        )

        assert result is True
        updated = test_db.query(ChannelQueueItem).filter_by(id=item.id).first()
        assert updated.status == "FAILED"
        assert updated.retry_count == 1
        assert updated.next_retry_at is not None  # Should have retry scheduled

    def test_mark_failed_permanent(self, test_db: Session):
        """Service should not retry permanent errors"""
        item = ChannelQueueItem(
            tenant_id=1,
            id="test-fail-permanent",
            message_id="msg-102",
            type="test",
            channel_type="EMAIL",
            status="PROCESSING",
            payload={},
            recipient="test@example.com",
        )
        test_db.add(item)
        test_db.commit()

        result = ChannelQueueService.mark_failed(
            item.id,
            "Invalid email address",
            should_retry=False,
            db=test_db,
        )

        assert result is True
        updated = test_db.query(ChannelQueueItem).filter_by(id=item.id).first()
        assert updated.status == "FAILED"
        assert updated.next_retry_at is None  # No retry scheduled


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
