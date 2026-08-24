"""Create Spartan Phalanx tables."""

import sys
sys.path.insert(0, '.')

from app.core.database import engine
from app.models.base import Base
from app.models import agent_phalanx  # noqa: F401

print("Creating Spartan Phalanx tables...")

try:
    Base.metadata.create_all(engine)
    print("[OK] All phalanx tables created successfully!")
    print("Tables created:")
    print("  - agent_phalanx_formations")
    print("  - agents_in_formations")
    print("  - shield_watches")
    print("  - phalanx_alerts")
    print("  - formation_integrity")
except Exception as e:
    print(f"[ERROR] {e}")
    raise
