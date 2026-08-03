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
from app.models.outreach import OutreachSequence
from app.models.partner_intent import PartnerIntentProfile
from app.models.buddy_program import BuddyProgramRecord, BuddyKPIScore
from app.models.performance_store import EmployeePerformanceEvent
from app.models.employee_milestone import EmployeeMilestone
from app.models.htd_intake_pause import HtdIntakeStatus, HtdMonthlyMetric, HtdPauseLogEntry
from app.models.htd_phase_gate import HTDPhaseGate
from app.models.message_template import MessageTemplate
from app.models.sla_breach import CandidateSLABreach
from app.models.candidate_memory import CandidateMemory, CandidateMemoryFact
from app.models.candidate_field_skip import CandidateFieldSkip
from app.models.candidate_resume_parsed import CandidateResumeParsed
from app.models.candidate_skill_tag import CandidateSkillTag
from app.models.prompt_execution_log import PromptExecutionLog
from app.models.candidate_sentiment_log import CandidateSentimentLog
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_job_flag import CandidateJobFlag
from app.models.follow_up_schedule import FollowUpSchedule
from app.models.candidate_no_response_log import CandidateNoResponseLog
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.outreach_campaign import OutreachCampaign, CampaignTouchpoint
from app.models.candidate_abandonment_score import CandidateAbandonmentScore
from app.models.candidate_availability_slot import CandidateAvailabilitySlot
from app.models.interview_reminder import InterviewReminder
from app.models.offer_faq_entry import OfferFAQEntry
from app.models.preboarding_document import PreboardingDocument
from app.models.candidate_joining_score import CandidateJoiningScore

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
    "OutreachSequence",
    "PartnerIntentProfile",
    "BuddyProgramRecord",
    "BuddyKPIScore",
    "EmployeePerformanceEvent",
    "HTDPhaseGate",
    "MessageTemplate",
    "CandidateSLABreach",
    "CandidateMemory",
    "CandidateMemoryFact",
    "CandidateFieldSkip",
    "CandidateResumeParsed",
    "CandidateSkillTag",
    "PromptExecutionLog",
    "CandidateSentimentLog",
    "CandidateJobScore",
    "CandidateJobFlag",
    "FollowUpSchedule",
    "CandidateNoResponseLog",
    "CandidateGhostingStatus",
    "OutreachCampaign",
    "CampaignTouchpoint",
    "CandidateAbandonmentScore",
    "CandidateAvailabilitySlot",
    "InterviewReminder",
    "OfferFAQEntry",
    "PreboardingDocument",
    "CandidateJoiningScore",
]

