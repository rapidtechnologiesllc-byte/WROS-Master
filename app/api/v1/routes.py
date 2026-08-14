import fastapi

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users import router as users_router
# from app.api.v1.endpoints.create_job import router as create_job_router  # DISABLED: requires GEMINI_API_KEY
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
# from app.api.v1.endpoints.ats import router as ats_router  # DISABLED: requires GEMINI_API_KEY
from app.api.v1.endpoints.email import router as email_router
from app.api.v1.endpoints.candidate_history import router as candidate_history_router
from app.api.v1.endpoints.candidate_ownership import router as candidate_ownership_router
from app.api.v1.endpoints.preonboarding import router as preonboarding_router
from app.api.v1.endpoints.internal import router as internal_router
from app.api.v1.endpoints.hr_assignments import router as hr_assignments_router
from app.api.v1.endpoints.ai_agent import router as ai_agent_router
from app.api.v1.endpoints.mfa import router as mfa_router
# from app.api.v1.endpoints.thunder import router as thunder_router  # DISABLED: incomplete implementation
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
from app.api.v1.endpoints.finance_operations import router as finance_operations_router
from app.api.v1.endpoints.tenants import router as tenants_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.employee_milestones import router as employee_milestones_router
from app.api.v1.endpoints.htd_intake_pause import router as htd_intake_pause_router
from app.api.v1.endpoints.notifications import router as notifications_router
from app.api.v1.endpoints.clients import router as clients_router
from app.api.v1.endpoints.opportunities import router as opportunities_router
from app.api.v1.endpoints.expenses import router as expenses_router
from app.api.v1.endpoints.partner_incentives import router as partner_incentives_router
from app.api.v1.endpoints.revenue_targets import router as revenue_targets_router
from app.api.v1.endpoints.forecast_and_leakage import router as forecast_and_leakage_router
from app.api.v1.endpoints.revenue_to_demand import router as revenue_to_demand_router
from app.api.v1.endpoints.cost_rate import router as cost_rate_router
# from app.api.v1.endpoints.public_chat import router as public_chat_router  # DISABLED: depends on incomplete Thunder
from app.api.v1.endpoints.flash import router as flash_router
from app.api.v1.endpoints.whatsapp_webhook import router as whatsapp_webhook_router
from app.api.v1.endpoints.portal_messages import router as portal_messages_router
from app.api.v1.endpoints.ai_recruiter_assignment import router as ai_recruiter_assignment_router
# from app.api.v1.endpoints.message_templates import router as message_templates_router  # DISABLED: depends on incomplete Thunder
from app.api.v1.endpoints.conversation_search import router as conversation_search_router
from app.api.v1.endpoints.candidate_portal import router as candidate_portal_router
from app.api.v1.endpoints.sla_breach import router as sla_breach_router
from app.api.v1.endpoints.technical_scoring import router as technical_scoring_router
from app.api.v1.endpoints.abandonment_scoring import router as abandonment_scoring_router
from app.api.v1.endpoints.offer_readiness import router as offer_readiness_router
from app.api.v1.endpoints.candidate_journey import router as candidate_journey_router
from app.api.v1.endpoints.drop_risk import router as drop_risk_router
from app.api.v1.endpoints.desire_intelligence import router as desire_intelligence_router
from app.api.v1.endpoints.activity_feed import router as activity_feed_router
from app.api.v1.endpoints.intervention_queue import router as intervention_queue_router
from app.api.v1.endpoints.risk_dashboard import router as risk_dashboard_router
from app.api.v1.endpoints.engagement_metrics import router as engagement_metrics_router
from app.api.v1.endpoints.thunder_analytics import router as thunder_analytics_router
from app.api.v1.endpoints.bulk_engagement import router as bulk_engagement_router
from app.api.v1.endpoints.event_log import router as event_log_router
from app.api.v1.endpoints.tasks import router as tasks_router
from app.api.v1.endpoints.tickets import router as tickets_router
from app.api.v1.endpoints.buddy_program import router as buddy_program_router
from app.api.v1.endpoints.executive_signal import router as executive_signal_router
from app.api.v1.endpoints.my_timesheet import router as my_timesheet_router
from app.api.v1.endpoints.error_log import router as error_log_router
from app.api.v1.endpoints.bu_context import router as bu_context_router
from app.api.v1.endpoints.system_config import router as system_config_router
from app.api.v1.endpoints.activity_timeline import router as activity_timeline_router
from app.api.v1.endpoints.agents import router as agents_router
from app.api.v1.endpoints.flash_interview import router as flash_interview_router
from app.api.v1.endpoints.hiring_workflow import router as hiring_workflow_router
from app.api.v1.endpoints.defect_reporting import router as defect_reporting_router
from app.api.v1.endpoints.agent_maturity import router as agent_maturity_router
from app.api.v1.endpoints.agent_operations import router as agent_operations_router
from app.api.v1.endpoints.agent_standups import router as agent_standups_router
from app.api.v1.endpoints.agent_standups_dashboard import router as agent_standups_dashboard_router
from app.api.v1.endpoints.agent_daily_standup import router as agent_daily_standup_router
from app.api.v1.endpoints.opportunity_tracker import router as opportunity_tracker_router
from app.api.v1.endpoints.htd_pipeline_accountability import router as htd_pipeline_accountability_router
from app.api.v1.endpoints.flash_orchestration import router as flash_orchestration_router
from app.api.v1.endpoints.business_metrics import router as business_metrics_router
from app.api.v1.endpoints.agent_state_dashboard import router as agent_state_dashboard_router
from app.api.v1.endpoints.role_based_dashboard import router as role_based_dashboard_router
from app.api.v1.endpoints.agent_kill_switch import router as agent_kill_switch_router
from app.api.v1.endpoints.spartan_phalanx import router as spartan_phalanx_router
from app.api.v1.endpoints.agent_performance_dashboard import router as agent_performance_dashboard_router
from app.api.v1.endpoints.employee_referrals import router as employee_referrals_router
from app.api.v1.endpoints.org_structure import router as org_structure_router
from app.api.v1.endpoints.work_orders import router as work_orders_router
# from app.api.v1.endpoints.training_dashboards import router as training_dashboards_router  # DISABLED: endpoint not found
# from app.api.v1.endpoints.bi_explorer import router as bi_explorer_router  # DISABLED: endpoint not found
from app.api.v1.endpoints.bu_head_dashboard import router as bu_head_dashboard_router

router = fastapi.APIRouter()

router.include_router(router=auth_router)
router.include_router(router=rbac_router)
router.include_router(router=org_structure_router)
router.include_router(router=users_router)
# router.include_router(router=create_job_router)  # DISABLED: requires GEMINI_API_KEY
router.include_router(router=onboarding_router)
router.include_router(router=interviews_router)
router.include_router(router=candidates_router)
router.include_router(router=msgraph_router)
router.include_router(router=documents_router)
router.include_router(router=offer_letters_router)
router.include_router(router=newsletter_router)
router.include_router(router=checklists_router)
router.include_router(router=candidate_status_router)
# router.include_router(router=ats_router)  # DISABLED: requires GEMINI_API_KEY
router.include_router(router=email_router)
router.include_router(router=candidate_history_router)
router.include_router(router=candidate_ownership_router)
router.include_router(router=preonboarding_router)
router.include_router(router=internal_router)
router.include_router(router=hr_assignments_router)
router.include_router(router=ai_agent_router)
router.include_router(router=mfa_router)
# router.include_router(router=thunder_router)  # DISABLED: incomplete implementation
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
router.include_router(router=finance_operations_router)
router.include_router(router=tenants_router)
router.include_router(router=projects_router)
router.include_router(router=employee_milestones_router)
router.include_router(router=htd_intake_pause_router)
router.include_router(router=notifications_router)
router.include_router(router=clients_router)
router.include_router(router=opportunities_router)
router.include_router(router=expenses_router)
router.include_router(router=partner_incentives_router)
router.include_router(router=revenue_targets_router)
router.include_router(router=forecast_and_leakage_router)
router.include_router(router=revenue_to_demand_router)
router.include_router(router=cost_rate_router)
# router.include_router(router=public_chat_router)  # DISABLED: depends on incomplete Thunder
router.include_router(router=flash_router)
router.include_router(router=whatsapp_webhook_router)
router.include_router(router=portal_messages_router)
router.include_router(router=ai_recruiter_assignment_router)
# router.include_router(router=message_templates_router)  # DISABLED: depends on incomplete Thunder
router.include_router(router=conversation_search_router)
router.include_router(router=candidate_portal_router)
router.include_router(router=technical_scoring_router)
router.include_router(router=sla_breach_router)
router.include_router(router=abandonment_scoring_router)
router.include_router(router=offer_readiness_router)
router.include_router(router=candidate_journey_router)
router.include_router(router=drop_risk_router)
router.include_router(router=desire_intelligence_router)
router.include_router(router=activity_feed_router)
router.include_router(router=intervention_queue_router)
router.include_router(router=risk_dashboard_router)
router.include_router(router=engagement_metrics_router)
router.include_router(router=thunder_analytics_router)
router.include_router(router=bulk_engagement_router)
router.include_router(router=event_log_router)
router.include_router(router=tasks_router)
router.include_router(router=tickets_router)
router.include_router(router=buddy_program_router)
router.include_router(router=executive_signal_router)
router.include_router(router=my_timesheet_router)
router.include_router(router=error_log_router)
router.include_router(router=bu_context_router)
router.include_router(router=system_config_router)
router.include_router(router=activity_timeline_router)
router.include_router(router=agents_router)
router.include_router(router=agent_operations_router)
router.include_router(router=agent_standups_router)
router.include_router(router=agent_standups_dashboard_router)
router.include_router(router=agent_daily_standup_router)
router.include_router(router=opportunity_tracker_router)
router.include_router(router=flash_interview_router)
router.include_router(router=hiring_workflow_router)
router.include_router(router=defect_reporting_router)
router.include_router(router=agent_maturity_router)
router.include_router(router=htd_pipeline_accountability_router)
router.include_router(router=flash_orchestration_router)
router.include_router(router=business_metrics_router)
router.include_router(router=agent_state_dashboard_router)
router.include_router(router=role_based_dashboard_router)
router.include_router(router=agent_kill_switch_router)
router.include_router(router=spartan_phalanx_router)
router.include_router(router=agent_performance_dashboard_router)
router.include_router(router=employee_referrals_router)
router.include_router(router=work_orders_router)
# router.include_router(router=training_dashboards_router)  # DISABLED: endpoint not found
# router.include_router(router=bi_explorer_router)  # DISABLED: endpoint not found
router.include_router(router=bu_head_dashboard_router)