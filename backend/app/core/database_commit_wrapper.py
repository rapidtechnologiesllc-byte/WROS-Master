"""Database session commit wrapper - ensures db.commit() on all CRUD operations."""
import logging
from functools import wraps
from sqlalchemy.orm import Session
from fastapi import HTTPException

logger = logging.getLogger(__name__)

def require_commit(func):
    """Decorator: wraps endpoint, ensures db.commit() called before response."""
    @wraps(func)
    def wrapper(*args, db: Session = None, **kwargs):
        try:
            result = func(*args, db=db, **kwargs)
            if db:
                db.commit()
                logger.debug(f"[DBCommit] {func.__name__}: committed")
            return result
        except HTTPException:
            if db:
                db.rollback()
            raise
        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"[DBCommit] {func.__name__} failed: {e}", exc_info=True)
            raise
    return wrapper
