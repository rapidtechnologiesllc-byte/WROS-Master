#!/usr/bin/env python3
"""Create message_queue table in database"""

import sys
sys.path.insert(0, '.')

from app.core.database import engine
from app.models.base import Base
from app.models.message_queue import MessageQueue

# Create only the MessageQueue table
print("Creating message_queue table...")
Base.metadata.create_all(bind=engine, tables=[MessageQueue.__table__])
print("✓ message_queue table created successfully")
