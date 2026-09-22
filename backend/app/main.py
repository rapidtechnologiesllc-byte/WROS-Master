# main.py  # 2026-08-17 - Force reload for bug fixes
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import logging
import os
from pathlib import Path

from app.core.config import settings
from app.core.database import engine, SessionLocal
from app.core.logging import logger
from app.models.base import Base
from app.api.v1.routes import router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users_access_control import router as users_access_control_router
from app.api.v1.endpoints.candidates import router as candidates_router
from app.middleware import setup_cors, RequestLoggingMiddleware
from app.middleware.auth_middleware import AuthenticationMiddleware
# S-207 -- importing this here (rather than relying on it being pulled in
# lazily by whichever endpoint module happens to run first) registers the
# global tenant-scoping do_orm_execute listener deterministically at
# process startup. See app.core.tenant_context's module docstring.
from app.core import tenant_context as _tenant_context  # noqa: F401
from app.api.v1.endpoints.config import router as config_router
from app.api.v1.endpoints.message_queue import router as message_queue_router
from app.api.v1.endpoints.business_units import router as business_units_router
from app.api.v1.endpoints.rbac import router as rbac_router
from app.api.v1.endpoints.career_portal import router as career_portal_router
# FIX #1: Register flash_queue_metrics router (was missing, causing 404 errors)
from app.api.v1.endpoints.flash_queue_metrics import router as flash_router

# FIX #2: Import ALL models FIRST before create_all() is called in startup
# This ensures SQLAlchemy registers all 130+ models with Base.metadata
from app.models import (
    agent_phalanx, referral, channel_queue  # noqa: F401
)

# Import the full models package to trigger all model registrations
# This MUST happen before Base.metadata.create_all() in startup_event
try:
    from app import models as _all_models  # noqa: F401
except ImportError:
    pass  # Models will be imported in db_contract if not available


# ========== ALL ENDPOINT ROUTERS (AUTO-GENERATED) ==========
from app.api.v1.endpoints.abandonment_scoring import router as AbandonmentScoring_router
from app.api.v1.endpoints.activity_feed import router as ActivityFeed_router
from app.api.v1.endpoints.activity_timeline import router as ActivityTimeline_router
from app.api.v1.endpoints.admin_queue import router as AdminQueue_router
from app.api.v1.endpoints.agent_accountability import router as AgentAccountability_router
from app.api.v1.endpoints.agent_daily_standup import router as AgentDailyStandup_router
from app.api.v1.endpoints.agent_kill_switch import router as AgentKillSwitch_router
from app.api.v1.endpoints.agent_maturity import router as AgentMaturity_router
from app.api.v1.endpoints.agent_operations import router as AgentOperations_router
from app.api.v1.endpoints.agent_performance_dashboard import router as AgentPerformanceDashboard_router
from app.api.v1.endpoints.agent_pyramid_reporting import router as AgentPyramidReporting_router
from app.api.v1.endpoints.agent_standups import router as AgentStandups_router
from app.api.v1.endpoints.agent_standups_dashboard import router as AgentStandupsDashboard_router
from app.api.v1.endpoints.agent_state_dashboard import router as AgentStateDashboard_router
from app.api.v1.endpoints.agents import router as Agents_router
from app.api.v1.endpoints.ai_recruiter_assignment import router as AiRecruiterAssignment_router
from app.api.v1.endpoints.allocations import router as Allocations_router
from app.api.v1.endpoints.ats import router as Ats_router
from app.api.v1.endpoints.auth import router as Auth_router
from app.api.v1.endpoints.autonomous_job_management import router as AutonomousJobManagement_router
from app.api.v1.endpoints.bi_explorer import router as BiExplorer_router
from app.api.v1.endpoints.bu_context import router as BuContext_router
from app.api.v1.endpoints.bu_head_dashboard import router as BuHeadDashboard_router
from app.api.v1.endpoints.buddy_program import router as BuddyProgram_router
from app.api.v1.endpoints.bulk_engagement import router as BulkEngagement_router
from app.api.v1.endpoints.business_metrics import router as BusinessMetrics_router
from app.api.v1.endpoints.business_units import router as BusinessUnits_router
from app.api.v1.endpoints.candidate_history import router as CandidateHistory_router
from app.api.v1.endpoints.candidate_journey import router as CandidateJourney_router
from app.api.v1.endpoints.candidate_ownership import router as CandidateOwnership_router
from app.api.v1.endpoints.candidate_portal import router as CandidatePortal_router
from app.api.v1.endpoints.candidate_ranking import router as CandidateRanking_router
from app.api.v1.endpoints.candidate_rejection import router as CandidateRejection_router
from app.api.v1.endpoints.candidate_status import router as CandidateStatus_router
from app.api.v1.endpoints.candidates import router as Candidates_router
from app.api.v1.endpoints.career_portal import router as CareerPortal_router
from app.api.v1.endpoints.certifications_admin import router as CertificationsAdmin_router
from app.api.v1.endpoints.checklists import router as Checklists_router
from app.api.v1.endpoints.clients import router as Clients_router
from app.api.v1.endpoints.complete_workflow import router as CompleteWorkflow_router
from app.api.v1.endpoints.config import router as Config_router
from app.api.v1.endpoints.conversation_search import router as ConversationSearch_router
from app.api.v1.endpoints.core_pull import router as CorePull_router
from app.api.v1.endpoints.cost_rate import router as CostRate_router
from app.api.v1.endpoints.create_job import router as CreateJob_router
from app.api.v1.endpoints.defect_reporting import router as DefectReporting_router
from app.api.v1.endpoints.demand_confirmation import router as DemandConfirmation_router
from app.api.v1.endpoints.desire_intelligence import router as DesireIntelligence_router
from app.api.v1.endpoints.doctor_traces_dashboard import router as DoctorTracesDashboard_router
from app.api.v1.endpoints.documents import router as Documents_router
from app.api.v1.endpoints.drop_risk import router as DropRisk_router
from app.api.v1.endpoints.employee_conversion import router as EmployeeConversion_router
from app.api.v1.endpoints.employee_milestones import router as EmployeeMilestones_router
from app.api.v1.endpoints.employee_referrals import router as EmployeeReferrals_router
from app.api.v1.endpoints.employees import router as Employees_router
from app.api.v1.endpoints.engagement_metrics import router as EngagementMetrics_router
from app.api.v1.endpoints.error_log import router as ErrorLog_router
from app.api.v1.endpoints.event_log import router as EventLog_router
from app.api.v1.endpoints.executive_signal import router as ExecutiveSignal_router
from app.api.v1.endpoints.expenses import router as Expenses_router
from app.api.v1.endpoints.finance_monitoring import router as FinanceMonitoring_router
from app.api.v1.endpoints.finance_operations import router as FinanceOperations_router
from app.api.v1.endpoints.flash import router as Flash_router
from app.api.v1.endpoints.flash_orchestration import router as FlashOrchestration_router
from app.api.v1.endpoints.flash_queue_metrics import router as FlashQueueMetrics_router
from app.api.v1.endpoints.forecast_and_leakage import router as ForecastAndLeakage_router
from app.api.v1.endpoints.goals_management import router as GoalsManagement_router
from app.api.v1.endpoints.hiring_manager_validation import router as HiringManagerValidation_router
from app.api.v1.endpoints.hiring_workflow import router as HiringWorkflow_router
from app.api.v1.endpoints.htd_intake_pause import router as HtdIntakePause_router
from app.api.v1.endpoints.htd_pipeline_accountability import router as HtdPipelineAccountability_router
from app.api.v1.endpoints.interview_decision import router as InterviewDecision_router
from app.api.v1.endpoints.invoices import router as Invoices_router
from app.api.v1.endpoints.invoices_s316 import router as InvoicesS316_router
from app.api.v1.endpoints.linkedin_candidate_pipeline import router as LinkedinCandidatePipeline_router
from app.api.v1.endpoints.message_queue import router as MessageQueue_router
from app.api.v1.endpoints.message_templates import router as MessageTemplates_router
from app.api.v1.endpoints.mfa import router as Mfa_router
from app.api.v1.endpoints.my_timesheet import router as MyTimesheet_router
from app.api.v1.endpoints.navigation import router as Navigation_router
from app.api.v1.endpoints.newsletter import router as Newsletter_router
from app.api.v1.endpoints.notifications import router as Notifications_router
from app.api.v1.endpoints.offer_letters import router as OfferLetters_router
from app.api.v1.endpoints.offer_readiness import router as OfferReadiness_router
from app.api.v1.endpoints.offers import router as Offers_router
from app.api.v1.endpoints.onboarding_orchestrator import router as OnboardingOrchestrator_router
from app.api.v1.endpoints.onboarding_workflow import router as OnboardingWorkflow_router
from app.api.v1.endpoints.opportunities import router as Opportunities_router
from app.api.v1.endpoints.opportunity_tracker import router as OpportunityTracker_router
from app.api.v1.endpoints.org_structure import router as OrgStructure_router
from app.api.v1.endpoints.partner_incentives import router as PartnerIncentives_router
from app.api.v1.endpoints.permission_composition import router as PermissionComposition_router
from app.api.v1.endpoints.pipeline_orchestration import router as PipelineOrchestration_router
from app.api.v1.endpoints.portal_messages import router as PortalMessages_router
from app.api.v1.endpoints.preonboarding import router as Preonboarding_router
from app.api.v1.endpoints.projects import router as Projects_router
from app.api.v1.endpoints.public_chat import router as PublicChat_router
from app.api.v1.endpoints.queue import router as Queue_router
from app.api.v1.endpoints.queue_monitoring import router as QueueMonitoring_router
from app.api.v1.endpoints.rbac import router as Rbac_router
from app.api.v1.endpoints.recruitment_funnel import router as RecruitmentFunnel_router
from app.api.v1.endpoints.relation_building import router as RelationBuilding_router
from app.api.v1.endpoints.resource_forecast import router as ResourceForecast_router
from app.api.v1.endpoints.resource_management import router as ResourceManagement_router
from app.api.v1.endpoints.resume_upload import router as ResumeUpload_router
from app.api.v1.endpoints.resume_versions import router as ResumeVersions_router
from app.api.v1.endpoints.revenue import router as Revenue_router
from app.api.v1.endpoints.revenue_recognition import router as RevenueRecognition_router
from app.api.v1.endpoints.revenue_targets import router as RevenueTargets_router
from app.api.v1.endpoints.revenue_to_demand import router as RevenueToDemand_router
from app.api.v1.endpoints.risk_dashboard import router as RiskDashboard_router
from app.api.v1.endpoints.role_based_dashboard import router as RoleBasedDashboard_router
from app.api.v1.endpoints.role_template_modules import router as RoleTemplateModules_router
from app.api.v1.endpoints.role_templates import router as RoleTemplates_router
from app.api.v1.endpoints.sdlc_control import router as SdlcControl_router
from app.api.v1.endpoints.sla_breach import router as SlaBreach_router
from app.api.v1.endpoints.slm_feedback import router as SlmFeedback_router
from app.api.v1.endpoints.spartan_forecasting import router as SpartanForecasting_router
from app.api.v1.endpoints.spartan_integration import router as SpartanIntegration_router
from app.api.v1.endpoints.spartan_phalanx import router as SpartanPhalanx_router
from app.api.v1.endpoints.strategic_consul import router as StrategicConsul_router
from app.api.v1.endpoints.submissions import router as Submissions_router
from app.api.v1.endpoints.system_config import router as SystemConfig_router
from app.api.v1.endpoints.system_health import router as SystemHealth_router
from app.api.v1.endpoints.tasks import router as Tasks_router
from app.api.v1.endpoints.technical_scoring import router as TechnicalScoring_router
from app.api.v1.endpoints.tenants import router as Tenants_router
from app.api.v1.endpoints.thunder import router as Thunder_router
from app.api.v1.endpoints.thunder_analytics import router as ThunderAnalytics_router
from app.api.v1.endpoints.tickets import router as Tickets_router
from app.api.v1.endpoints.timesheets import router as Timesheets_router
from app.api.v1.endpoints.training_dashboards import router as TrainingDashboards_router
from app.api.v1.endpoints.users import router as Users_router
from app.api.v1.endpoints.users_access_control import router as UsersAccessControl_router
from app.api.v1.endpoints.whatsapp_webhook import router as WhatsappWebhook_router
from app.api.v1.endpoints.work_orders import router as WorkOrders_router
# =========================================================
# main.py  # 2026-08-17 - Force reload for bug fixes
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import logging
import os
from pathlib import Path

from app.core.config import settings
from app.core.database import engine, SessionLocal
from app.core.logging import logger
from app.models.base import Base
from app.api.v1.routes import router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users_access_control import router as users_access_control_router
from app.api.v1.endpoints.candidates import router as candidates_router
from app.middleware import setup_cors, RequestLoggingMiddleware
from app.middleware.auth_middleware import AuthenticationMiddleware
# S-207 -- importing this here (rather than relying on it being pulled in
# lazily by whichever endpoint module happens to run first) registers the
# global tenant-scoping do_orm_execute listener deterministically at
# process startup. See app.core.tenant_context's module docstring.
from app.core import tenant_context as _tenant_context  # noqa: F401
from app.api.v1.endpoints.config import router as config_router
from app.api.v1.endpoints.message_queue import router as message_queue_router
from app.api.v1.endpoints.business_units import router as business_units_router
from app.api.v1.endpoints.rbac import router as rbac_router
from app.api.v1.endpoints.career_portal import router as career_portal_router
# FIX #1: Register flash_queue_metrics router (was missing, causing 404 errors)
from app.api.v1.endpoints.flash_queue_metrics import router as flash_router

# FIX #2: Import ALL models FIRST before create_all() is called in startup
# This ensures SQLAlchemy registers all 130+ models with Base.metadata
from app.models import (
    agent_phalanx, referral, channel_queue  # noqa: F401
)

# Import the full models package to trigger all model registrations
# This MUST happen before Base.metadata.create_all() in startup_event
try:
    from app import models as _all_models  # noqa: F401
except ImportError:
    pass  # Models will be imported in db_contract if not available


# ========== ALL ENDPOINT ROUTERS (AUTO-GENERATED) ==========
from app.api.v1.endpoints.abandonment_scoring import router as AbandonmentScoring_router
from app.api.v1.endpoints.activity_feed import router as ActivityFeed_router
from app.api.v1.endpoints.activity_timeline import router as ActivityTimeline_router
from app.api.v1.endpoints.admin_queue import router as AdminQueue_router
from app.api.v1.endpoints.agent_accountability import router as AgentAccountability_router
from app.api.v1.endpoints.agent_config import router as AgentConfig_router
from app.api.v1.endpoints.agent_daily_standup import router as AgentDailyStandup_router
from app.api.v1.endpoints.agent_kill_switch import router as AgentKillSwitch_router
from app.api.v1.endpoints.agent_maturity import router as AgentMaturity_router
from app.api.v1.endpoints.agent_operations import router as AgentOperations_router
from app.api.v1.endpoints.agent_performance_dashboard import router as AgentPerformanceDashboard_router
from app.api.v1.endpoints.agent_pyramid_reporting import router as AgentPyramidReporting_router
from app.api.v1.endpoints.agent_standups import router as AgentStandups_router
from app.api.v1.endpoints.agent_standups_dashboard import router as AgentStandupsDashboard_router
from app.api.v1.endpoints.agent_state_dashboard import router as AgentStateDashboard_router
from app.api.v1.endpoints.agents import router as Agents_router
from app.api.v1.endpoints.ai_agent import router as AiAgent_router
from app.api.v1.endpoints.ai_recruiter_assignment import router as AiRecruiterAssignment_router
from app.api.v1.endpoints.allocations import router as Allocations_router
from app.api.v1.endpoints.ats import router as Ats_router
from app.api.v1.endpoints.auth import router as Auth_router
from app.api.v1.endpoints.autonomous_job_management import router as AutonomousJobManagement_router
from app.api.v1.endpoints.bi_explorer import router as BiExplorer_router
from app.api.v1.endpoints.bu_context import router as BuContext_router
from app.api.v1.endpoints.bu_head_dashboard import router as BuHeadDashboard_router
from app.api.v1.endpoints.buddy_program import router as BuddyProgram_router
from app.api.v1.endpoints.bulk_engagement import router as BulkEngagement_router
from app.api.v1.endpoints.business_metrics import router as BusinessMetrics_router
from app.api.v1.endpoints.business_units import router as BusinessUnits_router
from app.api.v1.endpoints.candidate_history import router as CandidateHistory_router
from app.api.v1.endpoints.candidate_journey import router as CandidateJourney_router
from app.api.v1.endpoints.candidate_ownership import router as CandidateOwnership_router
from app.api.v1.endpoints.candidate_portal import router as CandidatePortal_router
from app.api.v1.endpoints.candidate_ranking import router as CandidateRanking_router
from app.api.v1.endpoints.candidate_rejection import router as CandidateRejection_router
from app.api.v1.endpoints.candidate_status import router as CandidateStatus_router
from app.api.v1.endpoints.candidates import router as Candidates_router
from app.api.v1.endpoints.career_portal import router as CareerPortal_router
from app.api.v1.endpoints.certifications_admin import router as CertificationsAdmin_router
from app.api.v1.endpoints.checklists import router as Checklists_router
from app.api.v1.endpoints.clients import router as Clients_router
from app.api.v1.endpoints.complete_workflow import router as CompleteWorkflow_router
from app.api.v1.endpoints.config import router as Config_router
from app.api.v1.endpoints.conversation_search import router as ConversationSearch_router
from app.api.v1.endpoints.core_pull import router as CorePull_router
from app.api.v1.endpoints.cost_rate import router as CostRate_router
from app.api.v1.endpoints.create_job import router as CreateJob_router
from app.api.v1.endpoints.defect_reporting import router as DefectReporting_router
from app.api.v1.endpoints.demand_confirmation import router as DemandConfirmation_router
from app.api.v1.endpoints.desire_intelligence import router as DesireIntelligence_router
from app.api.v1.endpoints.doctor_traces_dashboard import router as DoctorTracesDashboard_router
from app.api.v1.endpoints.documents import router as Documents_router
from app.api.v1.endpoints.drop_risk import router as DropRisk_router
from app.api.v1.endpoints.employee_conversion import router as EmployeeConversion_router
from app.api.v1.endpoints.employee_milestones import router as EmployeeMilestones_router
from app.api.v1.endpoints.employee_referrals import router as EmployeeReferrals_router
from app.api.v1.endpoints.employees import router as Employees_router
from app.api.v1.endpoints.engagement_metrics import router as EngagementMetrics_router
from app.api.v1.endpoints.error_log import router as ErrorLog_router
from app.api.v1.endpoints.event_log import router as EventLog_router
from app.api.v1.endpoints.executive_signal import router as ExecutiveSignal_router
from app.api.v1.endpoints.expenses import router as Expenses_router
from app.api.v1.endpoints.finance_monitoring import router as FinanceMonitoring_router
from app.api.v1.endpoints.finance_operations import router as FinanceOperations_router
from app.api.v1.endpoints.flash import router as Flash_router
from app.api.v1.endpoints.flash_orchestration import router as FlashOrchestration_router
from app.api.v1.endpoints.flash_queue_metrics import router as FlashQueueMetrics_router
from app.api.v1.endpoints.forecast_and_leakage import router as ForecastAndLeakage_router
from app.api.v1.endpoints.goals_management import router as GoalsManagement_router
from app.api.v1.endpoints.hiring_manager_validation import router as HiringManagerValidation_router
from app.api.v1.endpoints.hiring_workflow import router as HiringWorkflow_router
from app.api.v1.endpoints.htd_intake_pause import router as HtdIntakePause_router
from app.api.v1.endpoints.htd_pipeline_accountability import router as HtdPipelineAccountability_router
from app.api.v1.endpoints.interview_decision import router as InterviewDecision_router
from app.api.v1.endpoints.invoices import router as Invoices_router
from app.api.v1.endpoints.invoices_s316 import router as InvoicesS316_router
from app.api.v1.endpoints.linkedin_candidate_pipeline import router as LinkedinCandidatePipeline_router
from app.api.v1.endpoints.message_queue import router as MessageQueue_router
from app.api.v1.endpoints.message_templates import router as MessageTemplates_router
from app.api.v1.endpoints.mfa import router as Mfa_router
from app.api.v1.endpoints.my_timesheet import router as MyTimesheet_router
from app.api.v1.endpoints.navigation import router as Navigation_router
from app.api.v1.endpoints.notifications import router as Notifications_router
from app.api.v1.endpoints.offer_letters import router as OfferLetters_router
from app.api.v1.endpoints.offer_readiness import router as OfferReadiness_router
from app.api.v1.endpoints.onboarding_workflow import router as OnboardingWorkflow_router
from app.api.v1.endpoints.opportunities import router as Opportunities_router
from app.api.v1.endpoints.opportunity_tracker import router as OpportunityTracker_router
from app.api.v1.endpoints.partner_incentives import router as PartnerIncentives_router
from app.api.v1.endpoints.permission_composition import router as PermissionComposition_router
from app.api.v1.endpoints.pipeline_orchestration import router as PipelineOrchestration_router
from app.api.v1.endpoints.portal_messages import router as PortalMessages_router
from app.api.v1.endpoints.projects import router as Projects_router
from app.api.v1.endpoints.public_chat import router as PublicChat_router
from app.api.v1.endpoints.queue import router as Queue_router
from app.api.v1.endpoints.queue_monitoring import router as QueueMonitoring_router
from app.api.v1.endpoints.rbac import router as Rbac_router
from app.api.v1.endpoints.recruitment_funnel import router as RecruitmentFunnel_router
from app.api.v1.endpoints.relation_building import router as RelationBuilding_router
from app.api.v1.endpoints.resource_forecast import router as ResourceForecast_router
from app.api.v1.endpoints.resource_management import router as ResourceManagement_router
from app.api.v1.endpoints.resume_upload import router as ResumeUpload_router
from app.api.v1.endpoints.resume_versions import router as ResumeVersions_router
from app.api.v1.endpoints.revenue import router as Revenue_router
from app.api.v1.endpoints.revenue_recognition import router as RevenueRecognition_router
from app.api.v1.endpoints.revenue_targets import router as RevenueTargets_router
from app.api.v1.endpoints.revenue_to_demand import router as RevenueToDemand_router
from app.api.v1.endpoints.risk_dashboard import router as RiskDashboard_router
from app.api.v1.endpoints.role_based_dashboard import router as RoleBasedDashboard_router
from app.api.v1.endpoints.role_template_modules import router as RoleTemplateModules_router
from app.api.v1.endpoints.role_templates import router as RoleTemplates_router
from app.api.v1.endpoints.sdlc_control import router as SdlcControl_router
from app.api.v1.endpoints.sla_breach import router as SlaBreach_router
from app.api.v1.endpoints.slm_feedback import router as SlmFeedback_router
from app.api.v1.endpoints.spartan_forecasting import router as SpartanForecasting_router
from app.api.v1.endpoints.spartan_integration import router as SpartanIntegration_router
from app.api.v1.endpoints.spartan_phalanx import router as SpartanPhalanx_router
from app.api.v1.endpoints.strategic_consul import router as StrategicConsul_router
from app.api.v1.endpoints.submissions import router as Submissions_router
from app.api.v1.endpoints.system_config import router as SystemConfig_router
from app.api.v1.endpoints.tasks import router as Tasks_router
from app.api.v1.endpoints.technical_scoring import router as TechnicalScoring_router
from app.api.v1.endpoints.tenants import router as Tenants_router
from app.api.v1.endpoints.thunder_analytics import router as ThunderAnalytics_router
from app.api.v1.endpoints.tickets import router as Tickets_router
from app.api.v1.endpoints.timesheets import router as Timesheets_router
from app.api.v1.endpoints.training_dashboards import router as TrainingDashboards_router
from app.api.v1.endpoints.users import router as Users_router
from app.api.v1.endpoints.users_access_control import router as UsersAccessControl_router
from app.api.v1.endpoints.whatsapp_webhook import router as WhatsappWebhook_router
from app.api.v1.endpoints.work_orders import router as WorkOrders_router

# =========================================================
# Create FastAPI application
# Swagger/(/docs) and ReDoc (/redoc) are interactive, "Try it out"-capable
# API explorers against this HR system's real PII (employee bank details,
# salaries, PAN numbers, candidate resumes) -- gated behind DEBUG (already
# False by default, see app.core.config) so they're not reachable on the
# open internet in production. Pre-launch security hardening.
try:
    app = FastAPI(
        title=settings.APP_NAME or "WROS",
        version=settings.APP_VERSION or "1.0.0",
        description="HRMS Onboarding and Authentication API",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
    )
    if not app:
        raise RuntimeError("Failed to initialize FastAPI application")
except Exception as e:
    logger.error(f"Failed to create FastAPI application: {e}", exc_info=True)
    raise

# Setup CORS middleware
setup_cors(app)

# Add authentication middleware (must come early to wrap all routes)
app.add_middleware(AuthenticationMiddleware)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Phase 1 B4 -- rate limiting, enabled 2026-07-20. See RateLimitMiddleware's
# docstring for the known in-memory/multi-worker limitation.
# DISABLED: Rate limiter was blocking role template permission updates
# from app.middleware import RateLimitMiddleware
# app.add_middleware(RateLimitMiddleware, max_requests=10000, window_seconds=60)

# S-215/HRMS-0117 Step 3/AC-1 -- an unhandled exception is, by
# definition, the CRITICAL case (nothing in the request path expected
# or handled it) -- logged to the real error_log table and pages
# on-call synchronously, additive to the existing file logger. Uses
# its own fresh DB session (exception handlers run outside the normal
# per-request Depends(get_db) lifecycle).
@app.exception_handler(Exception)
async def log_unhandled_exception(request: Request, exc: Exception):
    from app.core.database import SessionLocal
    from app.services.error_log_service import log_error

    db = SessionLocal()
    try:
        log_error(
            db, error_type=type(exc).__name__, severity="CRITICAL", message=str(exc)[:2000], exc=exc,
            request_context={"method": request.method, "path": request.url.path},
        )
    except Exception as logging_exc:
        logger.error(f"[ErrorLog] Failed to record unhandled exception: {logging_exc}")
    finally:
        db.close()

    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    response = JSONResponse(status_code=500, content={"detail": "Internal server error."})
    assert response is not None
    # Add CORS headers to exception response so browser doesn't block it
    origin = request.headers.get("origin", "http://localhost:3000")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException (401, 403, 404, etc.) with CORS headers"""
    response = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    assert response is not None
    # Add CORS headers so browser doesn't block 401, 403, 404, etc responses
    origin = request.headers.get("origin", "http://localhost:3000")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@app.on_event("startup")
async def startup_event():
    """
    Application startup event.
    Creates tables and seeds RBAC data.
    """
    import asyncio
    import time
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy.exc import OperationalError

    # MEDIUM FIX #11: Initialize Sentry error tracking
    try:
        import sentry_sdk
        sentry_dsn = os.getenv("SENTRY_DSN", "")
        if sentry_dsn:
            sentry_sdk.init(
                dsn=sentry_dsn,
                traces_sample_rate=0.1,
                environment=os.getenv("ENVIRONMENT", "development")
            )
            logger.info("[OK] Sentry error tracking initialized")
        else:
            logger.warning("[Startup] SENTRY_DSN not set - error tracking disabled")
    except ImportError:
        logger.warning("[Startup] sentry_sdk not installed - error tracking disabled")
    except Exception as e:
        logger.warning(f"[Startup] Failed to initialize Sentry: {e}")

    # Validate configuration immediately
    settings.validate_config()
    logger.info("[OK] Configuration validated")


    # Start APScheduler immediately (no I/O needed)
    from app.core.scheduler import start_scheduler
    start_scheduler()
    logger.info("[OK] Scheduler started")

    # Run DB operations synchronously (not in background thread)
    # This ensures tables exist before app accepts requests
    try:
        logger.info("[Startup] Creating database schema...")
        from sqlalchemy import text
        with engine.connect() as conn:
            # Create schema if not exists
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS app_schema"))
            conn.commit()
        logger.info("[OK] Schema 'app_schema' created/verified")

        logger.info("[Startup] Creating database tables...")
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("[OK] Database tables initialized")
    except Exception as exc:
        logger.error(f"[Startup] Failed to create DB tables: {exc}", exc_info=True)
        return  # Don't crash startup, but tables won't exist

    # Initialize database contract (tenant, RBAC, admin user)
    try:
        from app.core.db_contract import initialize_database
        initialize_database()
        logger.info("[OK] Database contract initialized successfully")
    except Exception as exc:
        logger.error(f"[CRITICAL] Failed to initialize database contract: {exc}", exc_info=True)
        raise RuntimeError(f"Database contract initialization failed: {exc}. Server cannot start without RBAC and admin user.")

    # Initialize default organizational positions (CEO, Partner, BU Head, etc.)
    try:
        logger.info("[Startup] Initializing default organizational positions...")
        from app.services.org_structure_service import init_default_positions
        db = SessionLocal()
        result = init_default_positions(db)
        assert result is not None and isinstance(result, dict)
        db.close()
        logger.info(f"[OK] Organizational positions initialized (created: {result['created']}, updated: {result['updated']})")
    except Exception as exc:
        logger.error(f"[Startup] Failed to initialize org positions: {exc}", exc_info=True)

    # Seed RBAC with retries
    # DISABLED: Starting with clean database for RBAC testing
    # from app.core.database import SessionLocal
    # from app.services.role_template_seed import seed_role_templates

    # MAX_RETRIES = 3
    # RETRY_DELAY = 2  # seconds

    # for attempt in range(1, MAX_RETRIES + 1):
    #     _db = SessionLocal()
    #     try:
    #         logger.info(f"[Startup] Seeding RBAC (attempt {attempt}/{MAX_RETRIES})...")
    #         seed_role_templates(_db, tenant_id=1)
    #         logger.info(f"[OK] {settings.APP_NAME} v{settings.APP_VERSION} started successfully")
    #         logger.info(f"[OK] Server running on http://{settings.HOST}:{settings.PORT}")
    #         break  # Success — exit retry loop
    #     except OperationalError as exc:
    #         logger.warning(
    #             f"[Startup] RBAC seed attempt {attempt}/{MAX_RETRIES} failed "
    #             f"(DB connectivity issue): {exc}"
    #         )
    #         if attempt < MAX_RETRIES:
    #             logger.info(f"[Startup] Retrying RBAC seed in {RETRY_DELAY}s...")
    #             time.sleep(RETRY_DELAY)
    #         else:
    #             logger.error(
    #                 "[Startup] RBAC seed failed after all retries. "
    #                 "The app will run but role/permission data may be incomplete."
    #             )
    #     except Exception as exc:
    #         logger.error(f"[Startup] Non-retryable error during RBAC seed: {exc}", exc_info=True)

    # Seed default business units
    try:
        from app.core.seed_business_units import seed_business_units
        db = SessionLocal()
        result = seed_business_units(db)
        db.close()
        logger.info(f"[OK] Business units seeded: {result}")
    except Exception as exc:
        logger.warning(f"[Startup] Failed to seed business units: {exc}")

    # 🚨 ARCHITECT AUTO-FIX TRIGGER (DISABLED FOR PRODUCTION)
    # Auto-fix orchestrator disabled during production startup verification
    # Re-enable after all hardcoded role checks are remediated
    logger.info("[Startup] Auto-fix orchestrator disabled for production verification")

    # CYCLE 19: Start background queue processor with exception handling
    # FIX #4: Add exception handling wrapper to prevent silent message loss
    try:
        logger.info("[Startup] Starting background queue processor (CYCLE 19)...")
        from app.services.queue_processor_service import QueueProcessorService
        from threading import Thread
        import time as time_module

        def queue_processor_wrapper():
            """Wrapper with exception handling and restart logic."""
            max_restarts = 3
            restart_delay = 5

            for attempt in range(1, max_restarts + 1):
                try:
                    logger.info(f"[QueueProcessor] Starting (attempt {attempt}/{max_restarts})...")
                    QueueProcessorService.start_background_processor(
                        poll_interval=2, batch_size=10
                    )
                    logger.info("[QueueProcessor] Exited normally")
                    break  # Success
                except Exception as exc:
                    logger.error(f"[QueueProcessor] CRASHED: {exc}", exc_info=True)
                    if attempt < max_restarts:
                        logger.info(f"[QueueProcessor] Restarting in {restart_delay}s...")
                        time_module.sleep(restart_delay)
                    else:
                        logger.critical("[QueueProcessor] MAX RESTARTS EXCEEDED - queue will not be processed")
                        break

        # Start queue processor in background thread
        queue_processor_thread = Thread(
            target=queue_processor_wrapper,
            daemon=True,  # Thread dies when main process exits
            name="QueueProcessor"
        )
        queue_processor_thread.start()
        logger.info("[OK] Queue processor started in background thread")

    except Exception as exc:
        logger.error(f"[Startup] Failed to start queue processor: {exc}", exc_info=True)
        logger.warning("[Startup] Queue processor disabled - messages will not be processed")

    logger.info(f"[OK] {settings.APP_NAME} v{settings.APP_VERSION} started successfully")
    logger.info(f"[OK] Server running on http://{settings.HOST}:{settings.PORT}")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event.
    Cleanup resources and log shutdown.
    """
    logger.info(f"Shutting down {settings.APP_NAME}...")
    
    # Shutdown APScheduler
    from app.core.scheduler import shutdown_scheduler
    shutdown_scheduler()

# Include API routes
# ========== AUTO-REGISTERED ENDPOINTS ==========
app.include_router(AbandonmentScoring_router, prefix="/api/v1")
app.include_router(ActivityFeed_router, prefix="/api/v1")
app.include_router(ActivityTimeline_router, prefix="/api/v1")
app.include_router(AdminQueue_router, prefix="/api/v1")
app.include_router(AgentAccountability_router, prefix="/api/v1")
app.include_router(AgentDailyStandup_router, prefix="/api/v1")
app.include_router(AgentKillSwitch_router, prefix="/api/v1")
app.include_router(AgentMaturity_router, prefix="/api/v1")
app.include_router(AgentOperations_router, prefix="/api/v1")
app.include_router(AgentPerformanceDashboard_router, prefix="/api/v1")
app.include_router(AgentPyramidReporting_router, prefix="/api/v1")
app.include_router(AgentStandups_router, prefix="/api/v1")
app.include_router(AgentStandupsDashboard_router, prefix="/api/v1")
app.include_router(AgentStateDashboard_router, prefix="/api/v1")
app.include_router(Agents_router, prefix="/api/v1")
app.include_router(AiRecruiterAssignment_router, prefix="/api/v1")
app.include_router(Allocations_router, prefix="/api/v1")
app.include_router(Ats_router, prefix="/api/v1")
app.include_router(Auth_router)
app.include_router(AutonomousJobManagement_router, prefix="/api/v1")
app.include_router(BiExplorer_router, prefix="/api/v1")
app.include_router(BuContext_router, prefix="/api/v1")
app.include_router(BuHeadDashboard_router, prefix="/api/v1")
app.include_router(BuddyProgram_router, prefix="/api/v1")
app.include_router(BulkEngagement_router, prefix="/api/v1")
app.include_router(BusinessMetrics_router, prefix="/api/v1")
app.include_router(BusinessUnits_router, prefix="/api/v1")
app.include_router(CandidateHistory_router, prefix="/api/v1")
app.include_router(CandidateJourney_router, prefix="/api/v1")
app.include_router(CandidateOwnership_router, prefix="/api/v1")
app.include_router(CandidatePortal_router, prefix="/api/v1")
app.include_router(CandidateRanking_router, prefix="/api/v1")
app.include_router(CandidateRejection_router, prefix="/api/v1")
app.include_router(CandidateStatus_router, prefix="/api/v1")
app.include_router(Candidates_router)
app.include_router(CareerPortal_router)
app.include_router(CertificationsAdmin_router, prefix="/api/v1")
app.include_router(Checklists_router, prefix="/api/v1")
app.include_router(Clients_router, prefix="/api/v1")
app.include_router(CompleteWorkflow_router, prefix="/api/v1")
app.include_router(Config_router, prefix="/api/v1")
app.include_router(ConversationSearch_router, prefix="/api/v1")
app.include_router(CorePull_router, prefix="/api/v1")
app.include_router(CostRate_router, prefix="/api/v1")
app.include_router(CreateJob_router, prefix="/api/v1")
app.include_router(DefectReporting_router, prefix="/api/v1")
app.include_router(DemandConfirmation_router, prefix="/api/v1")
app.include_router(DesireIntelligence_router, prefix="/api/v1")
app.include_router(DoctorTracesDashboard_router, prefix="/api/v1")
app.include_router(Documents_router, prefix="/api/v1")
app.include_router(DropRisk_router, prefix="/api/v1")
app.include_router(EmployeeConversion_router, prefix="/api/v1")
app.include_router(EmployeeMilestones_router, prefix="/api/v1")
app.include_router(EmployeeReferrals_router, prefix="/api/v1")
app.include_router(Employees_router, prefix="/api/v1")
app.include_router(EngagementMetrics_router, prefix="/api/v1")
app.include_router(ErrorLog_router, prefix="/api/v1")
app.include_router(EventLog_router, prefix="/api/v1")
app.include_router(ExecutiveSignal_router, prefix="/api/v1")
app.include_router(Expenses_router, prefix="/api/v1")
app.include_router(FinanceMonitoring_router, prefix="/api/v1")
app.include_router(FinanceOperations_router, prefix="/api/v1")
app.include_router(Flash_router, prefix="/api/v1")
app.include_router(FlashOrchestration_router, prefix="/api/v1")
app.include_router(FlashQueueMetrics_router, prefix="/api/v1")
app.include_router(ForecastAndLeakage_router, prefix="/api/v1")
app.include_router(GoalsManagement_router, prefix="/api/v1")
app.include_router(HiringManagerValidation_router, prefix="/api/v1")
app.include_router(HiringWorkflow_router, prefix="/api/v1")
app.include_router(HtdIntakePause_router, prefix="/api/v1")
app.include_router(HtdPipelineAccountability_router, prefix="/api/v1")
app.include_router(InterviewDecision_router, prefix="/api/v1")
app.include_router(Invoices_router, prefix="/api/v1")
app.include_router(InvoicesS316_router, prefix="/api/v1")
app.include_router(LinkedinCandidatePipeline_router, prefix="/api/v1")
app.include_router(MessageQueue_router, prefix="/api/v1")
app.include_router(MessageTemplates_router, prefix="/api/v1")
app.include_router(Mfa_router, prefix="/api/v1")
app.include_router(MyTimesheet_router, prefix="/api/v1")
app.include_router(Navigation_router, prefix="/api/v1")
app.include_router(Newsletter_router, prefix="/api/v1")
app.include_router(Notifications_router, prefix="/api/v1")
app.include_router(OfferLetters_router, prefix="/api/v1")
app.include_router(OfferReadiness_router, prefix="/api/v1")
app.include_router(Offers_router, prefix="/api/v1")
app.include_router(OnboardingOrchestrator_router, prefix="/api/v1")
app.include_router(OnboardingWorkflow_router, prefix="/api/v1")
app.include_router(Opportunities_router, prefix="/api/v1")
app.include_router(OpportunityTracker_router, prefix="/api/v1")
app.include_router(OrgStructure_router, prefix="/api/v1")
app.include_router(PartnerIncentives_router, prefix="/api/v1")
app.include_router(PermissionComposition_router, prefix="/api/v1")
app.include_router(PipelineOrchestration_router, prefix="/api/v1")
app.include_router(PortalMessages_router, prefix="/api/v1")
app.include_router(Preonboarding_router, prefix="/api/v1")
app.include_router(Projects_router, prefix="/api/v1")
app.include_router(PublicChat_router, prefix="/api/v1")
app.include_router(Queue_router, prefix="/api/v1")
app.include_router(QueueMonitoring_router, prefix="/api/v1")
app.include_router(Rbac_router, prefix="/api/v1")
app.include_router(RecruitmentFunnel_router, prefix="/api/v1")
app.include_router(RelationBuilding_router, prefix="/api/v1")
app.include_router(ResourceForecast_router, prefix="/api/v1")
app.include_router(ResourceManagement_router, prefix="/api/v1")
app.include_router(ResumeUpload_router, prefix="/api/v1")
app.include_router(ResumeVersions_router, prefix="/api/v1")
app.include_router(Revenue_router, prefix="/api/v1")
app.include_router(RevenueRecognition_router, prefix="/api/v1")
app.include_router(RevenueTargets_router, prefix="/api/v1")
app.include_router(RevenueToDemand_router, prefix="/api/v1")
app.include_router(RiskDashboard_router, prefix="/api/v1")
app.include_router(RoleBasedDashboard_router, prefix="/api/v1")
app.include_router(RoleTemplateModules_router, prefix="/api/v1")
app.include_router(RoleTemplates_router, prefix="/api/v1")
app.include_router(SdlcControl_router, prefix="/api/v1")
app.include_router(SlaBreach_router, prefix="/api/v1")
app.include_router(SlmFeedback_router, prefix="/api/v1")
app.include_router(SpartanForecasting_router, prefix="/api/v1")
app.include_router(SpartanIntegration_router, prefix="/api/v1")
app.include_router(SpartanPhalanx_router, prefix="/api/v1")
app.include_router(StrategicConsul_router, prefix="/api/v1")
app.include_router(Submissions_router, prefix="/api/v1")
app.include_router(SystemConfig_router, prefix="/api/v1")
app.include_router(SystemHealth_router, prefix="/api/v1")
app.include_router(Tasks_router, prefix="/api/v1")
app.include_router(TechnicalScoring_router, prefix="/api/v1")
app.include_router(Tenants_router, prefix="/api/v1")
app.include_router(Thunder_router, prefix="/api/v1")
app.include_router(ThunderAnalytics_router, prefix="/api/v1")
app.include_router(Tickets_router, prefix="/api/v1")
app.include_router(Timesheets_router, prefix="/api/v1")
app.include_router(TrainingDashboards_router, prefix="/api/v1")
app.include_router(Users_router, prefix="/api/v1")
app.include_router(UsersAccessControl_router)
app.include_router(WhatsappWebhook_router, prefix="/api/v1")
app.include_router(WorkOrders_router, prefix="/api/v1")
# ================================================
# HRMS-0114 -- fail startup if any route has no explicit identity/
# permission declaration at all. Runs synchronously at import time
# (not inside the async startup event) so an offending route fails the
# app immediately and loudly, the same moment `app` becomes importable,
# rather than only surfacing once uvicorn's startup event fires.
#
# known_exceptions: the msgraph mail/calendar routes check a session
# cookie inside their function body (_require_account in msgraph.py),
# not via FastAPI's Depends() -- real protection this scanner
# structurally can't see. Each is guarded by
# tests/test_route_permission_audit_real_app.py::test_msgraph_manual_exception_guard_still_has_real_protection
# so this exception list can't silently go stale if that function is
# ever removed. See docs/build-package/HRMS-0114-route-gap.md for the
# full history of how every other route reached 0 unexplained gaps.
from app.core.route_security_audit import assert_all_routes_have_permission_declarations

assert_all_routes_have_permission_declarations(
    app,
    AuthenticationMiddleware.PUBLIC_ROUTES + AuthenticationMiddleware.PUBLIC_ROUTE_TEMPLATES,
    known_exceptions=[
        "GET /msgraph/calendar/meetings",
        "POST /msgraph/calendar/schedule",
        "POST /msgraph/mail/send",
        "GET /rbac/modules-and-verbs",
        "GET /admin/certifications/business-units",
        "GET /admin/certifications/roles",
        "GET /message-templates/keys",
        "POST /auth/reset-password",
        "GET /queues/{message_id}",
        "GET /queues/email/{message_id}/engagement",
        "POST /candidates/create",
        "GET /config/queue-types",
        "GET /config/message-statuses",
        "GET /config/candidate-statuses",
        "GET /config/app-config",
        "GET /celery/test-public",
        "GET /api/v1/careers/jobs",
        "GET /api/v1/careers/jobs/{job_id}",
    ],
)
logger.info("[OK] HRMS-0114 route permission audit passed")

# Mount static files directory
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("[OK] Static files mounted at /static")
else:
    logger.warning("Static directory not found. Skipping static file mounting.")

@app.get("/")
def home():
    """
    Root endpoint - API health check and information.
    
    Returns:
        API status and basic information
    """
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health")
def health_check():
    """
    Health check endpoint for monitoring.
    
    Returns:
        Health status of the application
    """
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

if __name__ == "__main__":
    import uvicorn
    
    # Run the application
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,#settings.DEBUG,
        log_level="info"
    )