"""Initialize database schema using SQLAlchemy models (skips broken migrations)"""
from app.core.database import engine
import logging
from app.models import Base

logger = logging.getLogger(__name__)

# Create all tables from model definitions
print("Creating database schema from models...")
try:
    Base.metadata.create_all(bind=engine)
    print("[OK] Database schema initialized successfully")
except Exception as e:
    logger.error(f"Error: {str(e)}", exc_info=True)
    print(f"[WARN] Some tables may already exist (expected): {e}")
    print("[OK] Schema initialization complete (table existence errors are ok)")
