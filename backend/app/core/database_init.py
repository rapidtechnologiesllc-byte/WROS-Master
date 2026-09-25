"""Database initialization - creates schema and tables on startup."""

import logging
from app.core.database import engine
from app.models.base import Base

logger = logging.getLogger(__name__)


def initialize_database():
    """Initialize database: create all tables from SQLAlchemy models."""
    try:
        logger.info("[DB-INIT] Creating database schema...")
        Base.metadata.create_all(bind=engine)
        logger.info("[DB-INIT] Database schema created successfully")
    except Exception as e:
        logger.error(f"[DB-INIT ERROR] Failed to initialize database: {e}", exc_info=True)
        raise
