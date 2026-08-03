import fastapi

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.create_job import router as create_job_router
from app.api.v1.endpoints.candidates import router as candidates_router
from app.api.v1.endpoints.msgraph import router as msgraph_router
from app.api.v1.endpoints.onboarding import router as onboarding_router
from app.api.v1.endpoints.interviews import router as interviews_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.offer_letters import router as offer_letters_router
from app.api.v1.endpoints.newsletter import router as newsletter_router
from app.api.v1.endpoints.rbac import router as rbac_router
from app.api.v1.endpoints.checklists import router as checklists_router
from app.api.v1.endpoints.candidate_status import router as candidate_status_router
from app.api.v1.endpoints.ats import router as ats_router
from app.api.v1.endpoints.email import router as email_router
from app.api.v1.endpoints.candidate_history import router as candidate_history_router
from app.api.v1.endpoints.candidate_ownership import router as candidate_ownership_router
from app.api.v1.endpoints.preonboarding import router as preonboarding_router
from app.api.v1.endpoints.internal import router as internal_router
from app.api.v1.endpoints.hr_assignments import router as hr_assignments_router
from app.api.v1.endpoints.ai_agent import router as ai_agent_router
from app.api.v1.endpoints.mfa import router as mfa_router
from app.api.v1.endpoints.thunder import router as thunder_router
from app.api.v1.endpoints.resource_management import router as resource_management_router
from app.api.v1.endpoints.core_pull import router as core_pull_router
from app.api.v1.endpoints.demand_confirmation import router as demand_confirmation_router
from app.api.v1.endpoints.employees import router as employees_router
from app.api.v1.endpoints.submissions import router as submissions_router
from app.api.v1.endpoints.allocations import router as allocations_router
from app.api.v1.endpoints.timesheets import router as timesheets_router
from app.api.v1.endpoints.resource_forecast import router as resource_forecast_router
from app.api.v1.endpoints.invoices import router as invoices_router
from app.api.v1.endpoints.revenue import router as revenue_router
from app.api.v1.endpoints.tenants import router as tenants_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.employee_milestones import router as employee_milestones_router
from app.api.v1.endpoints.htd_intake_pause import router as htd_intake_pause_router
from app.api.v1.endpoints.notifications import router as notifications_router
from app.api.v1.endpoints.clients import router as clients_router
from app.api.v1.endpoints.public_chat import router as public_chat_router
from app.api.v1.endpoints.internal_ask_thunder import router as internal_ask_thunder_router
from app.api.v1.endpoints.whatsapp_webhook import router as whatsapp_webhook_router
from app.api.v1.endpoints.portal_messages import router as portal_messages_router
from app.api.v1.endpoints.ai_recruiter_assignment import router as ai_recruiter_assignment_router
from app.api.v1.endpoints.message_templates import router as message_templates_router
from app.api.v1.endpoints.conversation_search import router as conversation_search_router
from app.api.v1.endpoints.candidate_portal import router as candidate_portal_router
from app.api.v1.endpoints.sla_breach import router as sla_breach_router
from app.api.v1.endpoints.technical_scoring import router as technical_scoring_router
from app.api.v1.endpoints.abandonment_scoring import router as abandonment_scoring_router
from app.api.v1.endpoints.offer_readiness import router as offer_readiness_router
from app.api.v1.endpoints.candidate_journey import router as candidate_journey_router

router = fastapi.APIRouter()

router.include_router(router=auth_router)
router.include_router(router=rbac_router)
router.include_router(router=users_router)
router.include_router(router=create_job_router)
router.include_router(router=onboarding_router)
router.include_router(router=interviews_router)
router.include_router(router=candidates_router)
router.include_router(router=msgraph_router)
router.include_router(router=documents_router)
router.include_router(router=offer_letters_router)
router.include_router(router=newsletter_router)
router.include_router(router=checklists_router)
router.include_router(router=candidate_status_router)
router.include_router(router=ats_router)
router.include_router(router=email_router)
router.include_router(router=candidate_history_router)
router.include_router(router=candidate_ownership_router)
router.include_router(router=preonboarding_router)
router.include_router(router=internal_router)
router.include_router(router=hr_assignments_router)
router.include_router(router=ai_agent_router)
router.include_router(router=mfa_router)
router.include_router(router=thunder_router)
router.include_router(router=resource_management_router)
router.include_router(router=core_pull_router)
router.include_router(router=demand_confirmation_router)
router.include_router(router=employees_router)
router.include_router(router=submissions_router)
router.include_router(router=allocations_router)
router.include_router(router=timesheets_router)
router.include_router(router=resource_forecast_router)
router.include_router(router=invoices_router)
router.include_router(router=revenue_router)
router.include_router(router=tenants_router)
router.include_router(router=projects_router)
router.include_router(router=employee_milestones_router)
router.include_router(router=htd_intake_pause_router)
router.include_router(router=notifications_router)
router.include_router(router=clients_router)
router.include_router(router=public_chat_router)
router.include_router(router=internal_ask_thunder_router)
router.include_router(router=whatsapp_webhook_router)
router.include_router(router=portal_messages_router)
router.include_router(router=ai_recruiter_assignment_router)
router.include_router(router=message_templates_router)
router.include_router(router=conversation_search_router)
router.include_router(router=candidate_portal_router)
router.include_router(router=technical_scoring_router)
router.include_router(router=sla_breach_router)
router.include_router(router=abandonment_scoring_router)
router.include_router(router=offer_readiness_router)
router.include_router(router=candidate_journey_router)