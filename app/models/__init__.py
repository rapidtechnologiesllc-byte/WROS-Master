"""
Models package initialization.
Exports all models for easy importing.
"""

from app.models.base import Base
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

__all__ = [
    # Base
    "Base",
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
]

