"""End-to-end test: Create candidate and verify EMAIL + WHATSAPP queue"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

# Test user login first
print("=" * 60)
print("TEST 1: Authenticate Test User")
print("=" * 60)

login_response = requests.post(
    f"{BASE_URL}/auth/login",
    json={
        "email": "superuser@blitzenx.com",
        "password": "TestUser@123"
    }
)
print(f"Login Status: {login_response.status_code}")
if login_response.status_code == 200:
    token = login_response.json().get("access_token")
    print(f"Token obtained: {token[:20]}...")
else:
    print(f"Login failed: {login_response.text}")
    exit(1)

# Test candidate creation
print("\n" + "=" * 60)
print("TEST 2: Create Candidate (Queue EMAIL + WHATSAPP)")
print("=" * 60)

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

candidate_data = {
    "candidate_email": "testcandidate@example.com",
    "candidate_first_name": "Test",
    "candidate_last_name": "Candidate",
    "candidate_mobile": "+1234567890",
    "position": "Software Engineer",
    "department": "Engineering",
    "candidate_source": "Direct Application"
}

create_response = requests.post(
    f"{BASE_URL}/candidate/candidate-form/",
    json=candidate_data,
    headers=headers
)

print(f"Create Candidate Status: {create_response.status_code}")
print(f"Response: {json.dumps(create_response.json(), indent=2)}")

if create_response.status_code in [200, 201]:
    candidate_id = create_response.json().get("candidate_id")
    print(f"Candidate Created: {candidate_id}")
else:
    print(f"Creation failed: {create_response.text}")
    exit(1)

# Verify channel queue items
print("\n" + "=" * 60)
print("TEST 3: Verify Messages Queued in ChannelQueueItem")
print("=" * 60)

from app.core.database import SessionLocal
from app.models.channel_queue import ChannelQueueItem

db = SessionLocal()
queued_items = db.query(ChannelQueueItem).filter(
    ChannelQueueItem.recipient == "testcandidate@example.com"
).all()

print(f"Found {len(queued_items)} queued messages:")
for item in queued_items:
    print(f"\n  - Type: {item.channel_type}")
    print(f"    ID: {item.id}")
    print(f"    Status: {item.status}")
    print(f"    Recipient: {item.recipient}")
    print(f"    Message Type: {item.type}")

if len(queued_items) >= 2:
    print("\n✅ SUCCESS: EMAIL and WHATSAPP messages queued correctly!")
else:
    print(f"\n❌ FAILURE: Expected 2 messages, got {len(queued_items)}")

db.close()

# Test EMAIL processor
print("\n" + "=" * 60)
print("TEST 4: Process EMAIL Message")
print("=" * 60)

from app.workers.channel_processors import ChannelProcessors

email_item = db.query(ChannelQueueItem).filter(
    ChannelQueueItem.channel_type == "EMAIL",
    ChannelQueueItem.recipient == "testcandidate@example.com"
).first()

if email_item:
    db = SessionLocal()
    result = ChannelProcessors.process_email(email_item.id, email_item.payload, db)
    print(f"EMAIL Processor Result: {result}")

    updated = db.query(ChannelQueueItem).filter_by(id=email_item.id).first()
    print(f"EMAIL Status After Processing: {updated.status}")
    if updated.result:
        print(f"Delivery ID: {updated.result.get('delivery_id')}")
    db.close()

# Test WHATSAPP processor
print("\n" + "=" * 60)
print("TEST 5: Process WHATSAPP Message")
print("=" * 60)

db = SessionLocal()
whatsapp_item = db.query(ChannelQueueItem).filter(
    ChannelQueueItem.channel_type == "WHATSAPP",
    ChannelQueueItem.recipient == "testcandidate@example.com"
).first()

if whatsapp_item:
    result = ChannelProcessors.process_whatsapp(whatsapp_item.id, whatsapp_item.payload, db)
    print(f"WHATSAPP Processor Result: {result}")

    updated = db.query(ChannelQueueItem).filter_by(id=whatsapp_item.id).first()
    print(f"WHATSAPP Status After Processing: {updated.status}")
    if updated.result:
        print(f"Delivery ID: {updated.result.get('delivery_id')}")
    db.close()

print("\n" + "=" * 60)
print("END-TO-END TEST COMPLETE")
print("=" * 60)
