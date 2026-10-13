#!/usr/bin/env python
import sys
sys.path.insert(0, 'backend')

from app.core.database import SessionLocal
from app.api.v1.endpoints.auth import UnifiedLoginRequest, unified_login

request = UnifiedLoginRequest(email="superuser@blitzenx.com", password="Test@12345")
db = SessionLocal()

print("Testing unified_login() function...")
try:
    result = unified_login(request, db)
    print(f"✓ SUCCESS")
    print(f"Result type: {type(result)}")
except Exception as e:
    print(f"✗ ERROR: {type(e).__name__}")
    print(f"Message: {str(e)[:200]}")
    import traceback
    traceback.print_exc()

db.close()
