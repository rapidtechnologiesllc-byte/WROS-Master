"""
Logging configuration for the Onboarding Application.
Provides structured logging with different levels and formats.
"""
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
import os

from app.core.log_redaction import RedactingFilter

# Create logs directory if it doesn't exist
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Log retention period (in days)
LOG_RETENTION_DAYS = 7

def cleanup_old_logs(retention_days: int = LOG_RETENTION_DAYS, logger: "logging.Logger | None" = None):
    """
    Delete log files older than the specified retention period.

    Args:
        retention_days: Number of days to keep log files
        logger: logger to report through -- HRMS-0117 requires no raw
            console logging anywhere, this function included. Falls back
            to the module-level logger if none is passed.
    """
    log = logger or logging.getLogger("onboarding_app")
    try:
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        deleted_count = 0

        for log_file in LOGS_DIR.glob("*.log"):
            # Get file modification time
            file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)

            if file_mtime < cutoff_date:
                log_file.unlink()
                deleted_count += 1
                log.info(f"Deleted old log file: {log_file.name}")

        if deleted_count > 0:
            log.info(f"Cleaned up {deleted_count} old log file(s) older than {retention_days} days")

    except Exception as e:
        logger.error(f"Error cleaning up old logs: {str(e)}", exc_info=True)

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        """Format log record with colors."""
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{log_color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)

def setup_logging(
    level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = True
) -> logging.Logger:
    """
    Setup application logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("onboarding_app")
    logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # HRMS-0117 / B1 -- redact known secret patterns before any record
    # reaches a handler. Filter lives on the logger itself so it applies
    # no matter which handlers get added below (or later).
    logger.filters.clear()
    logger.addFilter(RedactingFilter())

    # Create formatters
    file_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = ColoredFormatter(
        fmt='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # File handler - daily rotating log
    if log_to_file:
        log_filename = LOGS_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Error log file - only errors and critical
        error_log_filename = LOGS_DIR / f"error_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = logging.FileHandler(error_log_filename, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        logger.addHandler(error_handler)

    # Cleanup old log files -- now that the logger has handlers, so this
    # itself goes through the structured/redacted path instead of print().
    cleanup_old_logs(logger=logger)

    return logger

def get_logger(name: str = "onboarding_app") -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

# Initialize default logger
logger = setup_logging()

# Example usage functions
def log_api_request(method: str, endpoint: str, user_id: str = None):
    """Log API request."""
    user_info = f"User: {user_id}" if user_id else "Anonymous"
    logger.info(f"API Request | {method} {endpoint} | {user_info}")

def log_api_response(method: str, endpoint: str, status_code: int, duration_ms: float = None):
    """Log API response."""
    duration_info = f"| {duration_ms:.2f}ms" if duration_ms else ""
    logger.info(f"API Response | {method} {endpoint} | Status: {status_code} {duration_info}")

def log_database_query(query_type: str, table: str, duration_ms: float = None):
    """Log database query."""
    duration_info = f"| {duration_ms:.2f}ms" if duration_ms else ""
    logger.debug(f"DB Query | {query_type} on {table} {duration_info}")

def log_error(error: Exception, context: str = ""):
    """Log error with context."""
    context_info = f"[{context}] " if context else ""
    logger.error(f"{context_info}{type(error).__name__}: {str(error)}", exc_info=True)

def log_security_event(event_type: str, user_id: str = None, details: str = ""):
    """Log security-related events."""
    user_info = f"User: {user_id}" if user_id else "Anonymous"
    logger.warning(f"SECURITY | {event_type} | {user_info} | {details}")
