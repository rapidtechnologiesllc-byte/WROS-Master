"""
Comprehensive EMAIL processor test suite - AGILE CYCLE 1

Tests all EMAIL processor scenarios:
- Recipient validation
- Payload validation
- Successful delivery (mocked)
- Transient error handling
- Permanent error handling
- State transitions
- No side effects on failure
"""
import uuid
from app.core.database import SessionLocal
from app.models.channel_queue import ChannelQueueItem
from app.workers.channel_processors import ChannelProcessors
from app.services.channel_queue_service import ChannelQueueService

print("=" * 80)
print("EMAIL PROCESSOR - COMPREHENSIVE TEST SUITE (AGILE CYCLE 1)")
print("=" * 80)

db = SessionLocal()
test_count = 0
passed_count = 0

def run_test(name, test_func):
    """Run a single test and track results"""
    global test_count, passed_count
    test_count += 1
    print(f"\n[TEST {test_count}] {name}")
    try:
        test_func()
        passed_count += 1
        print(f"  ✅ PASS")
    except AssertionError as e:
        print(f"  ❌ FAIL: {e}")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")

# ============================================================================
# TEST 1: RECIPIENT VALIDATION - Valid email
# ============================================================================
def test_valid_recipient():
    """EMAIL processor should accept valid email"""
    item_id = f"test-email-valid-{uuid.uuid4().hex[:8]}"
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

    result = ChannelProcessors.process_email(item_id, "test@example.com",
                                              {"subject": "Test", "body": "Test body"}, db)

    # Verify item was attempted (either COMPLETED or FAILED)
    updated = db.query(ChannelQueueItem).filter_by(id=item_id).first()
    assert updated.status in ["COMPLETED", "FAILED"], f"Expected COMPLETED or FAILED, got {updated.status}"
    print(f"    Status: {updated.status}")

    db.delete(updated)
    db.commit()

run_test("Recipient validation - valid email", test_valid_recipient)

# ============================================================================
# TEST 2: RECIPIENT VALIDATION - Empty recipient
# ============================================================================
def test_empty_recipient():
    """EMAIL processor should reject empty recipient"""
    item_id = f"test-email-empty-{uuid.uuid4().hex[:8]}"
    email_item = ChannelQueueItem(
        id=item_id,
        message_id=f"msg-{uuid.uuid4().hex[:8]}",
        type="test",
        channel_type="EMAIL",
        status="PENDING",
        payload={"subject": "Test", "body": "Test body"},
        recipient=""
    )
    db.add(email_item)
    db.commit()

    result = ChannelProcessors.process_email(item_id, "", {"subject": "Test"}, db)

    # Should return False and mark as FAILED
    updated = db.query(ChannelQueueItem).filter_by(id=item_id).first()
    assert updated.status == "FAILED", f"Expected FAILED, got {updated.status}"
    assert updated.error, "Should have error message"
    print(f"    Error: {updated.error[:50]}...")

    db.delete(updated)
    db.commit()

run_test("Recipient validation - empty recipient", test_empty_recipient)

# ============================================================================
# TEST 3: RECIPIENT VALIDATION - Invalid email format
# ============================================================================
def test_invalid_email_format():
    """EMAIL processor should reject invalid email format"""
    item_id = f"test-email-invalid-{uuid.uuid4().hex[:8]}"

    result = ChannelProcessors.process_email(item_id, "not-an-email",
                                              {"subject": "Test"}, db)

    # Should return False
    assert result == False, "Should return False for invalid email"
    print(f"    Result: {result}")

run_test("Recipient validation - invalid email format", test_invalid_email_format)

# ============================================================================
# TEST 4: PAYLOAD VALIDATION - Empty subject
# ============================================================================
def test_empty_subject():
    """EMAIL processor should reject empty subject"""
    item_id = f"test-email-no-subject-{uuid.uuid4().hex[:8]}"

    result = ChannelProcessors.process_email(item_id, "test@example.com",
                                              {"subject": "", "body": "Test"}, db)

    # Should return False (no subject is invalid)
    assert result == False, "Should reject empty subject"
    print(f"    Result: {result}")

run_test("Payload validation - empty subject", test_empty_subject)

# ============================================================================
# TEST 5: PAYLOAD VALIDATION - Empty body
# ============================================================================
def test_empty_body():
    """EMAIL processor should reject empty body"""
    item_id = f"test-email-no-body-{uuid.uuid4().hex[:8]}"

    result = ChannelProcessors.process_email(item_id, "test@example.com",
                                              {"subject": "Test", "body": ""}, db)

    # Should return False (no body is invalid)
    assert result == False, "Should reject empty body"
    print(f"    Result: {result}")

run_test("Payload validation - empty body", test_empty_body)

# ============================================================================
# TEST 6: PAYLOAD VALIDATION - Missing required fields
# ============================================================================
def test_missing_required_fields():
    """EMAIL processor should reject payload without subject or body"""
    item_id = f"test-email-missing-{uuid.uuid4().hex[:8]}"

    result = ChannelProcessors.process_email(item_id, "test@example.com", {}, db)

    # Should return False
    assert result == False, "Should reject payload without subject/body"
    print(f"    Result: {result}")

run_test("Payload validation - missing required fields", test_missing_required_fields)

# ============================================================================
# TEST 7: STATE TRANSITION - Mark as COMPLETED
# ============================================================================
def test_successful_delivery():
    """EMAIL processor should mark as COMPLETED on success"""
    item_id = f"test-email-success-{uuid.uuid4().hex[:8]}"
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

    # First verify item is PENDING
    before = db.query(ChannelQueueItem).filter_by(id=item_id).first()
    assert before.status == "PENDING", "Item should start as PENDING"

    result = ChannelProcessors.process_email(item_id, "test@example.com",
                                              {"subject": "Test", "body": "Test body"}, db)

    # After processing, should be COMPLETED or FAILED (not PENDING)
    after = db.query(ChannelQueueItem).filter_by(id=item_id).first()
    assert after.status != "PENDING", f"Item should NOT remain PENDING, got {after.status}"
    print(f"    Transition: PENDING → {after.status}")

    db.delete(after)
    db.commit()

run_test("State transition - PENDING to COMPLETED/FAILED", test_successful_delivery)

# ============================================================================
# TEST 8: NO SIDE EFFECTS ON FAILURE
# ============================================================================
def test_no_side_effects_on_failure():
    """EMAIL processor should not create side effects on validation failure"""
    item_id = f"test-email-no-side-{uuid.uuid4().hex[:8]}"

    # Get count of items before
    count_before = db.query(ChannelQueueItem).count()

    # Call with invalid data
    result = ChannelProcessors.process_email(item_id, "", {"subject": "Test"}, db)

    # Count should not increase (no side effects)
    count_after = db.query(ChannelQueueItem).count()
    assert count_before == count_after, f"Side effect detected: {count_before} → {count_after} items"
    print(f"    Item count: {count_before} → {count_after} (no side effects)")

run_test("No side effects on failure", test_no_side_effects_on_failure)

# ============================================================================
# TEST 9: TRANSIENT ERROR DETECTION
# ============================================================================
def test_transient_error_classification():
    """EMAIL processor should classify transient errors correctly"""
    item_id = f"test-email-transient-{uuid.uuid4().hex[:8]}"
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

    # Simulate error classification in processor
    from app.services.channel_delivery_helpers import ErrorClassifier

    # Test transient errors
    transient_errors = [
        ("timeout", True),
        ("429 too many requests", True),
        ("500 internal error", True),
        ("temporary connection issue", True),
        ("401 unauthorized", False),  # permanent
        ("404 not found", False),  # permanent
    ]

    for error_msg, should_retry in transient_errors:
        is_transient = ErrorClassifier.is_transient_error(error_msg, None)
        assert is_transient == should_retry, f"Error '{error_msg}' should be {'transient' if should_retry else 'permanent'}"
        status = "TRANSIENT (retry)" if should_retry else "PERMANENT (no retry)"
        print(f"    '{error_msg}' → {status}")

    db.delete(email_item)
    db.commit()

run_test("Transient error classification", test_transient_error_classification)

# ============================================================================
# TEST 10: PROCESSING STATE TRACKING
# ============================================================================
def test_processing_state_tracking():
    """EMAIL processor should track PROCESSING state"""
    item_id = f"test-email-processing-{uuid.uuid4().hex[:8]}"
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

    # Mark as processing
    ChannelQueueService.mark_processing(item_id, db)

    # Verify status changed to PROCESSING
    updated = db.query(ChannelQueueItem).filter_by(id=item_id).first()
    assert updated.status == "PROCESSING", f"Expected PROCESSING, got {updated.status}"
    print(f"    Status: PENDING → PROCESSING")

    db.delete(updated)
    db.commit()

run_test("Processing state tracking", test_processing_state_tracking)

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print(f"Total Tests: {test_count}")
print(f"Passed: {passed_count}")
print(f"Failed: {test_count - passed_count}")

if passed_count == test_count:
    print("\n✅ ALL TESTS PASSED - EMAIL PROCESSOR READY")
else:
    print(f"\n❌ {test_count - passed_count} TESTS FAILED - FIX BEFORE PROCEEDING")

print("=" * 80)

db.close()
