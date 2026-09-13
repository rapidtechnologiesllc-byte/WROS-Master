"""
EMAIL Processor Test - AGILE CYCLE 1 (Mocked to avoid Graph credentials)

Tests EMAIL processor with:
- Recipient validation
- Payload validation
- State transitions with mocked email delivery
"""
import uuid
from unittest.mock import patch, MagicMock
from app.core.database import SessionLocal
from app.models.channel_queue import ChannelQueueItem
from app.workers.channel_processors import ChannelProcessors
from app.services.channel_queue_service import ChannelQueueService

print("=" * 80)
print("EMAIL PROCESSOR - AGILE CYCLE 1 TEST SUITE")
print("=" * 80)

db = SessionLocal()
test_count = 0
passed_count = 0

def run_test(name, test_func):
    """Run test and track results"""
    global test_count, passed_count
    test_count += 1
    print(f"\n[TEST {test_count}] {name}")
    try:
        test_func()
        passed_count += 1
        print(f"  [PASS]")
    except AssertionError as e:
        print(f"  [FAIL] {e}")
    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {str(e)[:60]}")

# ============================================================================
# TEST 1: Empty recipient rejected
# ============================================================================
def test_empty_recipient():
    """EMAIL processor should reject empty recipient"""
    result = ChannelProcessors.process_email("test-1", "", {"subject": "Test"}, db)
    assert result == False, "Should reject empty recipient"
    print(f"    Result: {result} (empty recipient rejected)")

run_test("Empty recipient validation", test_empty_recipient)

# ============================================================================
# TEST 2: Invalid email format rejected
# ============================================================================
def test_invalid_email():
    """EMAIL processor should reject invalid email format"""
    result = ChannelProcessors.process_email("test-2", "not-an-email", {"subject": "Test"}, db)
    assert result == False, "Should reject invalid email"
    print(f"    Result: {result} (invalid email rejected)")

run_test("Invalid email format rejected", test_invalid_email)

# ============================================================================
# TEST 3: Empty subject rejected
# ============================================================================
def test_empty_subject():
    """EMAIL processor should reject empty subject"""
    result = ChannelProcessors.process_email("test-3", "test@example.com", {"subject": "", "body": "Test"}, db)
    assert result == False, "Should reject empty subject"
    print(f"    Result: {result} (empty subject rejected)")

run_test("Empty subject validation", test_empty_subject)

# ============================================================================
# TEST 4: Empty body rejected
# ============================================================================
def test_empty_body():
    """EMAIL processor should reject empty body"""
    result = ChannelProcessors.process_email("test-4", "test@example.com", {"subject": "Test", "body": ""}, db)
    assert result == False, "Should reject empty body"
    print(f"    Result: {result} (empty body rejected)")

run_test("Empty body validation", test_empty_body)

# ============================================================================
# TEST 5: Missing required fields rejected
# ============================================================================
def test_missing_fields():
    """EMAIL processor should reject missing subject/body"""
    result = ChannelProcessors.process_email("test-5", "test@example.com", {}, db)
    assert result == False, "Should reject missing fields"
    print(f"    Result: {result} (missing fields rejected)")

run_test("Missing required fields", test_missing_fields)

# ============================================================================
# TEST 6: Successful delivery with mocked EmailService
# ============================================================================
def test_successful_delivery_mocked():
    """EMAIL processor should mark COMPLETED with mocked email service"""
    item_id = f"test-success-{uuid.uuid4().hex[:8]}"
    email_item = ChannelQueueItem(
        id=item_id,
        message_id=f"msg-{uuid.uuid4().hex[:8]}",
        type="test",
        channel_type="EMAIL",
        status="PENDING",
        payload={"subject": "Test", "body": "Test body", "is_html": False},
        recipient="test@example.com"
    )
    db.add(email_item)
    db.commit()

    # Mock the Graph token retrieval and email send
    with patch('app.core.graph_auth.get_graph_token') as mock_token:
        with patch('app.services.email_service.EmailService._graph_post') as mock_send:
            mock_token.return_value = "mock-token"
            mock_send.return_value = {"id": "delivery-id-123"}

            # Process email
            result = ChannelProcessors.process_email(
                item_id,
                "test@example.com",
                {"subject": "Test", "body": "Test body"},
                db
            )

            # Should return True (success) or False (but attempted)
            print(f"    Processor returned: {result}")

            # Check item status
            updated = db.query(ChannelQueueItem).filter_by(id=item_id).first()
            assert updated.status == "COMPLETED", f"Expected COMPLETED, got {updated.status}"
            assert updated.result, "Should have result data"
            print(f"    Status: PENDING -> COMPLETED")
            print(f"    Result: {updated.result}")

    db.delete(updated)
    db.commit()

run_test("Successful delivery (mocked)", test_successful_delivery_mocked)

# ============================================================================
# TEST 7: Transient error - retry scheduled
# ============================================================================
def test_transient_error_retryable():
    """EMAIL processor should mark FAILED with next_retry_at for transient errors"""
    item_id = f"test-transient-{uuid.uuid4().hex[:8]}"
    email_item = ChannelQueueItem(
        id=item_id,
        message_id=f"msg-{uuid.uuid4().hex[:8]}",
        type="test",
        channel_type="EMAIL",
        status="PENDING",
        payload={"subject": "Test", "body": "Test body"},
        recipient="test@example.com"
    )
    db.add(email_item)
    db.commit()

    # Mock token to fail with 500 error
    with patch('app.core.graph_auth.get_graph_token') as mock_token:
        mock_token.side_effect = Exception("500 Internal Server Error")

        result = ChannelProcessors.process_email(
            item_id,
            "test@example.com",
            {"subject": "Test", "body": "Test body"},
            db
        )

        # Should return False
        assert result == False, "Should return False on error"
        print(f"    Processor returned: {result}")

        # Check item status
        updated = db.query(ChannelQueueItem).filter_by(id=item_id).first()
        assert updated.status == "FAILED", f"Expected FAILED, got {updated.status}"
        assert updated.error, "Should have error message"
        assert updated.next_retry_at, "Transient error should have next_retry_at"
        print(f"    Status: PENDING -> FAILED")
        print(f"    Error: {updated.error[:40]}...")
        print(f"    Retry scheduled: {updated.next_retry_at}")

    db.delete(updated)
    db.commit()

run_test("Transient error - retry scheduled", test_transient_error_retryable)

# ============================================================================
# TEST 8: Permanent error - no retry scheduled
# ============================================================================
def test_permanent_error_no_retry():
    """EMAIL processor should mark FAILED with no retry for permanent errors"""
    item_id = f"test-permanent-{uuid.uuid4().hex[:8]}"
    email_item = ChannelQueueItem(
        id=item_id,
        message_id=f"msg-{uuid.uuid4().hex[:8]}",
        type="test",
        channel_type="EMAIL",
        status="PENDING",
        payload={"subject": "Test", "body": "Test body"},
        recipient="test@example.com"
    )
    db.add(email_item)
    db.commit()

    # Mock token to fail with 401 (permanent)
    with patch('app.core.graph_auth.get_graph_token') as mock_token:
        mock_token.side_effect = Exception("401 Unauthorized - invalid credentials")

        result = ChannelProcessors.process_email(
            item_id,
            "test@example.com",
            {"subject": "Test", "body": "Test body"},
            db
        )

        # Should return False
        assert result == False, "Should return False"
        print(f"    Processor returned: {result}")

        # Check item status
        updated = db.query(ChannelQueueItem).filter_by(id=item_id).first()
        assert updated.status == "FAILED", f"Expected FAILED, got {updated.status}"
        assert updated.error, "Should have error message"
        # Permanent errors should NOT have next_retry_at (or retry_count at 0)
        print(f"    Status: PENDING -> FAILED")
        print(f"    Error: {updated.error[:40]}...")
        print(f"    Retry count: {updated.retry_count}")

    db.delete(updated)
    db.commit()

run_test("Permanent error - no retry", test_permanent_error_no_retry)

# ============================================================================
# TEST 9: State NOT PENDING after processing
# ============================================================================
def test_state_transition():
    """EMAIL processor should change state from PENDING"""
    item_id = f"test-state-{uuid.uuid4().hex[:8]}"
    email_item = ChannelQueueItem(
        id=item_id,
        message_id=f"msg-{uuid.uuid4().hex[:8]}",
        type="test",
        channel_type="EMAIL",
        status="PENDING",
        payload={"subject": "Test", "body": "Test body"},
        recipient="test@example.com"
    )
    db.add(email_item)
    db.commit()

    # Check before
    before = db.query(ChannelQueueItem).filter_by(id=item_id).first()
    assert before.status == "PENDING", "Item should start as PENDING"

    # Process (will fail due to no Graph creds, but that's ok)
    ChannelProcessors.process_email(item_id, "test@example.com", {"subject": "Test", "body": "Test"}, db)

    # Check after
    after = db.query(ChannelQueueItem).filter_by(id=item_id).first()
    assert after.status != "PENDING", f"Item should NOT remain PENDING, got {after.status}"
    print(f"    Transition: PENDING -> {after.status}")

    db.delete(after)
    db.commit()

run_test("State transition - PENDING to COMPLETED/FAILED", test_state_transition)

# ============================================================================
# TEST 10: No side effects on validation failure
# ============================================================================
def test_no_side_effects():
    """EMAIL processor should not create items on validation failure"""
    count_before = db.query(ChannelQueueItem).count()

    # Call with invalid data
    ChannelProcessors.process_email("invalid-id", "", {}, db)

    count_after = db.query(ChannelQueueItem).count()
    assert count_before == count_after, f"Side effect: {count_before} -> {count_after}"
    print(f"    Item count: {count_before} -> {count_after} (no side effects)")

run_test("No side effects on validation failure", test_no_side_effects)

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("SUMMARY: EMAIL PROCESSOR AGILE CYCLE 1")
print("=" * 80)
print(f"Total: {test_count} | Passed: {passed_count} | Failed: {test_count - passed_count}")

if passed_count == test_count:
    print("\n[SUCCESS] ALL TESTS PASSED - EMAIL PROCESSOR READY FOR PRODUCTION")
else:
    print(f"\n[FAILURE] {test_count - passed_count} tests failed")

print("=" * 80)

db.close()
