#!/usr/bin/env python
"""
Setup script to create SLM tables
Run this once to initialize the database
"""

from app.core.database import engine
from app.models.admin import Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_tables():
    """Create all SLM tables"""
    try:
        logger.info("Creating SLM tables...")

        # Create all tables defined in admin.py models
        Base.metadata.create_all(bind=engine)

        logger.info("✓ Tables created successfully")
        logger.info("Tables created:")
        logger.info("  - slm_patterns")
        logger.info("  - slm_pattern_updates")
        logger.info("  - slm_question_logs")

    except Exception as e:
        logger.error(f"✗ Error creating tables: {e}")
        raise


if __name__ == "__main__":
    setup_tables()
