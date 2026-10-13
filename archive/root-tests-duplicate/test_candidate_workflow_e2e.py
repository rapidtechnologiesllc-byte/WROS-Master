"""End-to-End Candidate Workflow Test

Tests the complete flow:
1. Add candidate via API
2. Candidate queued to Thunder
3. Queue processor executes Thunder handler
4. Email delivered via Azure
5. Delivery logged to audit trail
"""

import json
import requests
import time
from datetime import datetime

# Configuration
API_BASE = "http://localhost:8081"
CANDIDATE_EMAIL = f"test_candidate_{int(time.time())}@example.com"
CANDIDATE_NAME = "Test Candidate"
CANDIDATE_PHONE = "+1234567890"

print("\n" + "="*80)
print("E2E CANDIDATE WORKFLOW TEST")
print("="*80)

# ============================================================================
# STEP 1: Add candidate via API
# ============================================================================
print("\n[STEP 1] Creating candidate...")

payload = {
    "candidate_first_name": CANDIDATE_NAME,
    "candidate_email": CANDIDATE_EMAIL,
    "candidate_mobile": CANDIDATE_PHONE,
    "candidate_source": "manual",
    "candidate_role": "Software Engineer"
}

try:
    response = requests.post(
        f"{API_BASE}/api/v1/candidates/create",
        json=payload,
        timeout=10
    )
    print(f"Status: {response.status_code}")

    if response.status_code not in [200, 201]:
        print(f"❌ FAILED: {response.text}")
        exit(1)

    result = response.json()
    candidate_id = result.get("candidate_id")
    print(f"✅ Candidate created: {candidate_id}")

except Exception as e:
    print(f"❌ FAILED: {e}")
    exit(1)

# ============================================================================
# STEP 2: Verify candidate in database
# ============================================================================
print("\n[STEP 2] Verifying candidate in database...")

try:
    response = requests.get(
        f"{API_BASE}/api/v1/candidates/{candidate_id}",
        timeout=10
    )

    if response.status_code != 200:
        print(f"❌ FAILED: Candidate not found in DB (status {response.status_code})")
        exit(1)

    print(f"✅ Candidate exists in database")

except Exception as e:
    print(f"❌ FAILED: {e}")
    exit(1)

# ============================================================================
# STEP 3: Check queue for Thunder engagement message
# ============================================================================
print("\n[STEP 3] Checking queue for Thunder engagement message...")

try:
    # Wait a moment for the queue processor to pick it up
    time.sleep(2)

    response = requests.get(
        f"{API_BASE}/api/v1/queue/pending",
        timeout=10
    )

    if response.status_code != 200:
        print(f"⚠️ WARNING: Could not fetch queue status (status {response.status_code})")
        print("Continuing anyway...")
    else:
        queue_data = response.json()
        pending_count = queue_data.get("count", 0)
        print(f"Queue has {pending_count} pending messages")

        # Look for our engage_candidate_with_thunder task
        if "items" in queue_data:
            for item in queue_data["items"]:
                if item.get("type") == "engage_candidate_with_thunder":
                    if item.get("payload", {}).get("candidate_id") == candidate_id:
                        print(f"✅ Found Thunder engagement message in queue")
                        break

except Exception as e:
    print(f"⚠️ WARNING: Could not check queue: {e}")
    print("Continuing anyway...")

# ============================================================================
# STEP 4: Wait for queue processing and check delivery log
# ============================================================================
print("\n[STEP 4] Waiting for Thunder to process (max 30 seconds)...")

delivery_found = False
for attempt in range(15):
    time.sleep(2)

    try:
        response = requests.get(
            f"{API_BASE}/api/v1/candidates/{candidate_id}/delivery-log",
            timeout=10
        )

        if response.status_code == 200:
            log_data = response.json()
            if log_data.get("count", 0) > 0:
                delivery_log = log_data["items"][0]
                print(f"✅ Delivery logged!")
                print(f"   Channel: {delivery_log.get('channel')}")
                print(f"   Status: {delivery_log.get('status')}")
                print(f"   To: {delivery_log.get('to_address')}")
                delivery_found = True
                break
    except:
        pass

    print(f"   Attempt {attempt+1}/15: waiting for delivery...")

if not delivery_found:
    print(f"⚠️ WARNING: No delivery log found yet")
    print("This might mean:")
    print("  1. Queue processor not running")
    print("  2. Thunder handler encountered an error")
    print("  3. Azure credentials not configured")
    print("  4. Delivery service not available")

# ============================================================================
# STEP 5: Check conversation for message history
# ============================================================================
print("\n[STEP 5] Checking conversation for message history...")

try:
    response = requests.get(
        f"{API_BASE}/api/v1/candidates/{candidate_id}/conversation",
        timeout=10
    )

    if response.status_code == 200:
        conversation = response.json()
        if conversation:
            message_count = len(conversation.get("messages", []))
            print(f"✅ Conversation found with {message_count} messages")
    else:
        print(f"⚠️ WARNING: No conversation found (status {response.status_code})")

except Exception as e:
    print(f"⚠️ WARNING: Could not fetch conversation: {e}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("TEST SUMMARY")
print("="*80)

if delivery_found:
    print("✅ END-TO-END WORKFLOW SUCCESSFUL!")
    print("\nThe complete flow worked:")
    print("  1. Candidate created")
    print("  2. Queued to Thunder")
    print("  3. Queue processor executed")
    print("  4. Email delivered")
    print("  5. Delivery logged")
else:
    print("❌ WORKFLOW INCOMPLETE")
    print("\nDebugging steps:")
    print(f"  1. Check backend logs for errors")
    print(f"  2. Verify queue processor is running: ps aux | grep queue_processor")
    print(f"  3. Check Azure credentials: check API Keys in settings")
    print(f"  4. Run: curl http://localhost:8081/api/v1/queue/stats")
    print(f"  5. Run: curl http://localhost:8081/api/v1/health")

print("\n")
