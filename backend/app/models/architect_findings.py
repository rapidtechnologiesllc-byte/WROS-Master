"""Database model for storing architect findings"""

from sqlalchemy import Column, String, Integer, DateTime, Text, Float, Enum as SQLEnum
from datetime import datetime
import enum
from app.models.base import Base


class SeverityLevel(str, enum.Enum):
    """Issue severity levels"""
    CRITICAL_BLOCKING = "CRITICAL_BLOCKING"
    CRITICAL_DATA_LOSS = "CRITICAL_DATA_LOSS"
    CRITICAL_SECURITY = "CRITICAL_SECURITY"
    HIGH_CRASH = "HIGH_CRASH"
    HIGH_SILENT_FAIL = "HIGH_SILENT_FAIL"
    MEDIUM_RACE = "MEDIUM_RACE"
    MEDIUM_EDGE_CASE = "MEDIUM_EDGE_CASE"
    LOW_DEBT = "LOW_DEBT"
    LOW_STYLE = "LOW_STYLE"


class IssueType(str, enum.Enum):
    """Type of issue found"""
    SILENT_EXCEPTION = "silent_exception"
    MISSING_ERROR_HANDLER = "missing_error_handler"
    HARDCODED_DEPENDENCY = "hardcoded_dependency"
    QUEUE_ROUTING_WRONG = "queue_routing_wrong"
    RACE_CONDITION = "race_condition"
    MISSING_TRANSACTION = "missing_transaction"
    NO_VALIDATION = "no_validation"
    HARDCODED_VALUE = "hardcoded_value"
    MISSING_PERMISSION_CHECK = "missing_permission_check"
    DUPLICATE_INFRASTRUCTURE = "duplicate_infrastructure"
    WRONG_HTTP_METHOD = "wrong_http_method"


class ArchitectFinding(Base):
    """Stores architect findings for tracking and historical analysis"""
    __tablename__ = "architect_findings"

    id = Column(String(36), primary_key=True)
    cycle_number = Column(Integer, nullable=False)
    severity = Column(SQLEnum(SeverityLevel), nullable=False)
    issue_type = Column(SQLEnum(IssueType), nullable=False)
    title = Column(String(255), nullable=False)
    file = Column(String(512), nullable=False)
    line = Column(Integer, nullable=False)
    code_snippet = Column(Text, nullable=True)
    why_wrong = Column(Text, nullable=True)
    impact = Column(Text, nullable=True)
    fix = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)

    # Tracking
    discovered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    fixed = Column(String(36), nullable=True)  # Link to commit hash if fixed
    fixed_at = Column(DateTime, nullable=True)
    status = Column(String(50), default="open", nullable=False)  # open, in_progress, fixed, wontfix

    def to_dict(self):
        """Convert to dict"""
        return {
            "id": self.id,
            "cycle": self.cycle_number,
            "severity": self.severity.value,
            "issue_type": self.issue_type.value,
            "title": self.title,
            "file": self.file,
            "line": self.line,
            "code_snippet": self.code_snippet,
            "why_wrong": self.why_wrong,
            "impact": self.impact,
            "fix": self.fix,
            "category": self.category,
            "status": self.status,
        }


class ArchitectCycleSummary(Base):
    """Summary of architect analysis for each SDLC cycle"""
    __tablename__ = "architect_cycle_summaries"

    id = Column(String(36), primary_key=True)
    cycle_number = Column(Integer, nullable=False, unique=True)
    total_findings = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)

    # Recommendations
    next_focus = Column(Text, nullable=True)  # JSON list of recommendations
    blocking_fixes = Column(Text, nullable=True)  # JSON list of issues that block deployment

    # Metrics
    analysis_time_seconds = Column(Float, default=0)
    findings_resolved = Column(Integer, default=0)  # Issues fixed since last cycle

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        """Convert to dict"""
        return {
            "cycle": self.cycle_number,
            "total_findings": self.total_findings,
            "critical": self.critical_count,
            "high": self.high_count,
            "medium": self.medium_count,
            "low": self.low_count,
            "findings_resolved": self.findings_resolved,
        }
