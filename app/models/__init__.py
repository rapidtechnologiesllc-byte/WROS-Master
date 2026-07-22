"""
Models package initialization.
Exports all models for easy importing.
"""

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.audit_log import AuditLog
from app.models.consent import ConsentRecord
from app.models.user import (
    Users,
    Jobs,
    CandidateAssignment,
    InterviewPanel,
    PanelMember,
    Interview,
    InterviewFeedback
)
from app.models.candidate import (
    Candidate,
    CandidateInfoForm,
    CandidateEducationForm,
    CandidateExperienceForm,
    CandidateAadharForm,
    CandidatePanForm,
    CandidateStatus,
    CandidateJobApplication,
)
from app.models.document import CandidateDocument
from app.models.offer_letter import OfferLetter
from app.models.newsletter import Newsletter, NewsletterSubscriber
from app.models.rbac import Role, RoleAttribute, Permission, RolePermission, BusinessUnit, Department
from app.models.employee import (
    Employee,
    EmployeeEmploymentHistory,
    EmployeeDocuments,
    EmployeeEngineHistory,
)
from app.models.client import Client, ClientContact, ClientHistory
from app.models.demand import Demand, DemandHistory
from app.models.submission import Submission, SubmissionViolation
from app.models.interview_pipeline import DemandInterviewPanel, SubmissionInterview
from app.models.employee_allocation import EmployeeAllocation
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.notification import Notification
from app.models.opportunity import Opportunity
from app.models.timesheet_dispute import TimesheetDispute
from app.models.sub_vendor import SubVendorAccount, SubVendorRequest, SubVendorUser, ClarificationQA
from app.models.sub_vendor_submission import SubVendorSubmission, SubVendorViolation, SubVendorDedupRejection
from app.models.project import Project, ProjectMilestone
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.revenue_leakage import RevenueLeakageFlag, ReconciliationAlert
from app.models.timesheet_anomaly import TimesheetAnomalyFlag
from app.models.checklist import (
    ChecklistTemplate,
    ChecklistTemplateItem,
    CandidateChecklist,
    CandidateChecklistItem,
)
from app.models.ats import ATSScore
from app.models.candidate_history import CandidateHistory
from app.models.candidate_ownership import CandidateOwnership
from app.models.internal_note import InternalNote
from app.models.hr_assignment import HRAssignment
from app.models.candidate_ai import (
    CandidateConversation,
    CandidateAIAssignment,
    ConversationEvent,
)
from app.models.orchestration import ConflictRule, OrchestrationEvent
from app.models.sourcing import DemandGapScore, SourcingAlert, SourcingSearchRun, StagedCandidate

__all__ = [
    # Base
    "Base",
    # Tenant (HRMS-0109)
    "Tenant",
    # Audit Log (HRMS-0110)
    "AuditLog",
    # Consent (Phase 1 B6)
    "ConsentRecord",
    # User models
    "Users",
    "Jobs",
    "CandidateAssignment",
    "InterviewPanel",
    "PanelMember",
    "Interview",
    "InterviewFeedback",
    # Candidate models
    "Candidate",
    "CandidateInfoForm",
    "CandidateEducationForm",
    "CandidateExperienceForm",
    "CandidateAadharForm",
    "CandidatePanForm",
    "CandidateStatus",
    "CandidateJobApplication",
    "CandidateDocument",
    # Offer Letter
    "OfferLetter",
    # Newsletter
    "Newsletter",
    "NewsletterSubscriber",
    # RBAC
    "Role",
    "RoleAttribute",
    "Permission",
    "RolePermission",
    "BusinessUnit",
    "Department",
    # Employee (HRMS-0101 / 0101-REV, Phase 2 Domain 3)
    "Employee",
    "EmployeeEmploymentHistory",
    "EmployeeDocuments",
    "EmployeeEngineHistory",
    # Client (HRMS-0102, Phase 2 Domain 4)
    "Client",
    "ClientContact",
    "ClientHistory",
    # Demand (HRMS-0103, Phase 2 Domain 2/4)
    "Demand",
    "DemandHistory",
    # Submission (HRMS-0711, Phase 2 Domain 2)
    "Submission",
    "SubmissionViolation",
    # Interview pipeline (HRMS-0706, Phase 2 Domain 2)
    "DemandInterviewPanel",
    "SubmissionInterview",
    # Employee Allocation (HRMS-0507, minimal slice)
    "EmployeeAllocation",
    # Timesheet (HRMS-0901/0902, Phase 2 Domain 4)
    "Timesheet",
    "TimesheetEntry",
    # Notification Engine (HRMS-0113)
    "Notification",
    # Opportunity (HRMS-0207, Phase 2 Domain 4)
    "Opportunity",
    # Timesheet Dispute (HRMS-0904, Phase 2 Domain 4)
    "TimesheetDispute",
    # Sub-Vendor Portal (HRMS-P801/P804, Phase 2 Domain 5)
    "SubVendorAccount",
    "SubVendorRequest",
    "SubVendorUser",
    "ClarificationQA",
    "SubVendorSubmission",
    "SubVendorViolation",
    "SubVendorDedupRejection",
    # Project (HRMS-0801/0804, Phase 2 Domain 4)
    "Project",
    "ProjectMilestone",
    # Invoice (HRMS-0907, Phase 2 Domain 4)
    "Invoice",
    "InvoiceLineItem",
    # Revenue Leakage + Reconciliation (HRMS-0906/0903, Phase 2 Domain 4)
    "RevenueLeakageFlag",
    "ReconciliationAlert",
    # Timesheet Anomaly Detection (HRMS-0910, Phase 2 Domain 4)
    "TimesheetAnomalyFlag",
    # Checklist
    "ChecklistTemplate",
    "ChecklistTemplateItem",
    "CandidateChecklist",
    "CandidateChecklistItem",
    # ATS
    "ATSScore",
    # Candidate History
    "CandidateHistory",
    # Candidate Pool Ownership
    "CandidateOwnership",
    # Internal HR Notes
    "InternalNote",
    # HR Assignments
    "HRAssignment",
    # AI Agentic Hiring
    "CandidateConversation",
    "CandidateAIAssignment",
    "ConversationEvent",
    "ConflictRule",
    "OrchestrationEvent",
    "DemandGapScore",
    "SourcingAlert",
    "SourcingSearchRun",
    "StagedCandidate",
]

