#!/usr/bin/env python
"""Check message queue status for specific message ID"""
import sys
sys.path.insert(0, 'C:\dev\WROS-Master\backend')

from app.core.database import SessionLocal
from app.models.channel_queue import ChannelQueueItem

db = SessionLocal()
message_id = 'f0e23fe2-15d5-4dbe-b6f9-3af3db1a1548'

message = db.query(ChannelQueueItem).filter(
    ChannelQueueItem.id == message_id
).first()

if message:
    print(f"Message ID: {message.id}")
    print(f"Status: {message.status}")
    print(f"Type: {message.type}")
    print(f"Channel: {message.channel_type}")
    print(f"Created at: {message.created_at}")
    print(f"Started at: {message.started_at}")
    print(f"Completed at: {message.completed_at}")
    print(f"Retry count: {message.retry_count}")
    print(f"Error: {message.error}")
    print(f"Next retry at: {message.next_retry_at}")
    
    if message.status == "PROCESSING":
        from datetime import datetime, timedelta
        elapsed = datetime.utcnow() - message.started_at if message.started_at else None
        print(f"\n⚠️  STUCK IN PROCESSING")
        print(f"   Elapsed time: {elapsed}")
        if elapsed and elapsed > timedelta(minutes=5):
            print(f"   >>> EXCEEDS 5-minute threshold! Should be recovered by monitor")
else:
    print(f"Message {message_id} not found in queue")

db.close()
