"""
SMS Processor Test - AGILE CYCLE 3

Tests SMS processor with:
- Recipient validation (phone format)
- Payload validation (message content)
- Mock delivery
- State transitions
"""
import uuid
from app.core.database import SessionLocal
from app.models.channel_queue import ChannelQueueItem
from app.workers.channel_processors import ChannelProcessors

print("=" * 80)
print("SMS PROCESSOR - AGILE CYCLE 3 TEST SUITE")
print("=" * 80)

db = SessionLocal()
test_count = 0
passed_count = 0

def run_test(name, test_func):
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
    result = ChannelProcessors.process_sms("test-1", "", {"message": "Test"}, db)
    assert result == False, "Should reject empty recipient"
    print(f"    Result: {result} (empty rejected)")

run_test("Empty recipient validation", test_empty_recipient)

# ============================================================================
# TEST 2: Invalid phone format rejected
# ============================================================================
def test_invalid_phone():
    result = ChannelProcessors.process_sms("test-2", "invalid", {"message": "Test"}, db)
    assert result == False, "Should reject invalid phone"
    print(f"    Result: {result} (invalid rejected)")

run_test("Invalid phone format rejected", test_invalid_phone)

# ============================================================================
# TEST 3: Valid phone accepted
# ============================================================================
def test_valid_phone():
    result = ChannelProcessors.process_sms("test-3", "+1234567890", {"message": "Hello"}, db)
    assert result == True, "Should accept valid phone"
    print(f"    Result: {result} (valid accepted)")

run_test("Valid phone format accepted", test_valid_phone)

# ============================================================================
# TEST 4: Empty message rejected
# ============================================================================
def test_empty_message():
    result = ChannelProcessors.process_sms("test-4", "+1234567890", {"message": ""}, db)
    assert result == False, "Should reject empty message"
    print(f"    Result: {result} (empty rejected)")

run_test("Empty message validation", test_empty_message)

# ============================================================================
# TEST 5: Missing message field rejected
# ============================================================================
def test_missing_message():
    result = ChannelProcessors.process_sms("test-5", "+1234567890", {}, db)
    assert result == False, "Should reject missing message"
    print(f"    Result: {result} (missing rejected)")

run_test("Missing message field", test_missing_message)

# ============================================================================
# TEST 6: Successful delivery
# ============================================================================
def test_successful_delivery():
    item_id = f"test-success-{uuid.uuid4().hex[:8]}"
    sms_item = ChannelQueueItem(
        id=item_id,
        message_id=f"msg-{uuid.uuid4().hex[:8]}",
        type="test",
        channel_type="SMS",
        status="PENDING",
        payload={"message": "Test SMS"},
        recipient="+1234567890"
    )
    db.add(sms_item)
    db.commit()

    result = ChannelProcessors.process_sms(item_id, "+1234567890", {"message": "Test SMS"}, db)
    assert result == True, "Should return True"

    updated = db.query(ChannelQueueItem).filter_by(id=item_id).first()
    assert updated.status == "COMPLETED", f"Expected COMPLETED, got {updated.status}"
    print(f"    Status: PENDING -> COMPLETED")
    print(f"    Delivery ID: {updated.result.get('delivery_id')}")

    db.delete(updated)
    db.commit()

run_test("Successful delivery", test_successful_delivery)

# ============================================================================
# TEST 7: State transition
# ============================================================================
def test_state_transition():
    item_id = f"test-state-{uuid.uuid4().hex[:8]}"
    sms_item = ChannelQueueItem(
        id=item_id,
        message_id=f"msg-{uuid.uuid4().hex[:8]}",
        type="test",
        channel_type="SMS",
        status="PENDING",
        payload={"message": "Test"},
        recipient="+1234567890"
    )
    db.add(sms_item)
    db.commit()

    before = db.query(ChannelQueueItem).filter_by(id=item_id).first()
    assert before.status == "PENDING"

    ChannelProcessors.process_sms(item_id, "+1234567890", {"message": "Test"}, db)

    after = db.query(ChannelQueueItem).filter_by(id=item_id).first()
    assert after.status != "PENDING", f"Should not remain PENDING, got {after.status}"
    print(f"    Transition: PENDING -> {after.status}")

    db.delete(after)
    db.commit()

run_test("State transition", test_state_transition)

# ============================================================================
# TEST 8: No side effects
# ============================================================================
def test_no_side_effects():
    count_before = db.query(ChannelQueueItem).count()
    ChannelProcessors.process_sms("invalid-id", "", {}, db)
    count_after = db.query(ChannelQueueItem).count()
    assert count_before == count_after, f"Side effect: {count_before} -> {count_after}"
    print(f"    Item count: {count_before} -> {count_after} (stable)")

run_test("No side effects", test_no_side_effects)

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("SUMMARY: SMS PROCESSOR AGILE CYCLE 3")
print("=" * 80)
print(f"Total: {test_count} | Passed: {passed_count} | Failed: {test_count - passed_count}")

if passed_count == test_count:
    print("\n[SUCCESS] SMS PROCESSOR READY")
else:
    print(f"\n[FAILURE] {test_count - passed_count} failed")

print("=" * 80)

db.close()
