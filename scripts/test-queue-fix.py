#!/usr/bin/env python
"""
Test the message queue fix directly by:
1. Creating a candidate via API
2. Checking if it was logged to ChannelQueueItem in database
3. Verifying dashboard can see it
"""
import os
import sys
import json
import requests
from datetime import datetime

# Setup environment
os.environ['DATABASE_URL'] = 'postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/wros_dev'
os.environ['ENVIRONMENT'] = 'development'

API_URL = "http://localhost:8080/api/v1"

print("=" * 70)
print("MESSAGE QUEUE FIX VERIFICATION TEST")
print("=" * 70)
print()

# Step 1: Create a test candidate
print("[1/3] Creating test candidate...")
timestamp = int(datetime.now().timestamp() * 1000)
candidate_payload = {
    "candidate_email": f"test_queue_{timestamp}@test.com",
    "candidate_first_name": "QueueTest",
    "candidate_last_name": f"Candidate{timestamp}",
    "candidate_mobile": "5551234567",
    "candidate_current_location": "Test City, USA",
}

try:
    response = requests.post(
        f"{API_URL}/candidates/create",
        json=candidate_payload,
        timeout=10
    )

    if response.status_code not in [200, 201]:
        print(f"FAIL: Expected 200/201, got {response.status_code}")
        print(f"Response: {response.text}")
        sys.exit(1)

    data = response.json()
    candidate_id = data.get("candidate_id")

    if not candidate_id:
        print(f"FAIL: No candidate_id in response")
        sys.exit(1)

    print(f"OK Created candidate: {candidate_id}")
    print(f"   Email: {candidate_payload['candidate_email']}")

except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)

# Step 2: Check database directly for ChannelQueueItem
print()
print("[2/3] Checking database for queued message...")

try:
    from app.core.database import SessionLocal
    from app.models.channel_queue import ChannelQueueItem

    db = SessionLocal()

    # Look for our candidate in the queue
    queue_item = db.query(ChannelQueueItem).filter(
        ChannelQueueItem.message_id == candidate_id
    ).first()

    if queue_item:
        print(f"OK Message found in ChannelQueueItem!")
        print(f"   ID: {queue_item.id}")
        print(f"   Message ID: {queue_item.message_id}")
        print(f"   Channel Type: {queue_item.channel_type}")
        print(f"   Status: {queue_item.status}")
        print(f"   Type: {queue_item.type}")
    else:
        print(f"FAIL: Message NOT found in ChannelQueueItem")
        print(f"   Searched for message_id: {candidate_id}")
        print()
        print("Checking what IS in the queue...")
        all_items = db.query(ChannelQueueItem).limit(5).all()
        if all_items:
            print(f"   Found {len(all_items)} items in queue:")
            for item in all_items:
                print(f"     - {item.id}: {item.channel_type} (status: {item.status})")
        else:
            print(f"   Queue is completely empty")

    db.close()

except Exception as e:
    print(f"FAIL: Database error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 3: Check API can retrieve queue types
print()
print("[3/3] Checking dashboard API...")

try:
    response = requests.get(
        f"{API_URL}/config/queue-types",
        timeout=5
    )

    if response.status_code == 200:
        data = response.json()
        queue_types = data.get("queue_types", [])
        print(f"OK Queue types from API: {queue_types}")

        if "CANDIDATE_QUEUE" in queue_types:
            print(f"   Found CANDIDATE_QUEUE (this means data is in database)")
        else:
            print(f"   WARNING: CANDIDATE_QUEUE not in types")
    else:
        print(f"FAIL: API returned {response.status_code}")

except Exception as e:
    print(f"FAIL: {e}")

print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)
print()
print("If message was found in ChannelQueueItem, the fix IS WORKING!")
print("If message was NOT found, check backend logs for database errors.")
