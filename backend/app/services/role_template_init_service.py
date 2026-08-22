"""Initialize role template system with all modules, resources, and default role templates."""

from sqlalchemy.orm import Session
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission


MODULES_AND_RESOURCES = {
    "Executive": {
        "display_name": "Executive",
        "description": "Executive dashboards and reports",
        "resources": [
            {"name": "ceo_fy_progress", "display_name": "CEO FY Progress", "route": "/ceo-fy-progress"},
            {"name": "executive_revenue", "display_name": "Executive Revenue", "route": "/executive-revenue-dashboard"},
            {"name": "cfo_agent", "display_name": "CFO Agent", "route": "/cfo-dashboard"},
            {"name": "partner_roi_agent", "display_name": "Partner ROI Agent", "route": "/partner-roi"},
            {"name": "ceo_dashboard", "display_name": "CEO Dashboard", "route": "/ceo-dashboard"},
            {"name": "bu_head_dashboard", "display_name": "BU Head Dashboard", "route": "/bu-head-dashboard"},
        ]
    },
    "Recruitment": {
        "display_name": "Recruitment",
        "description": "Candidate recruitment and hiring",
        "resources": [
            {"name": "candidates", "display_name": "Candidates", "route": "/candidates"},
            {"name": "jobs", "display_name": "Jobs", "route": "/jobs"},
            {"name": "submissions", "display_name": "Submissions", "route": "/submissions"},
            {"name": "interviews", "display_name": "Interviews", "route": "/candidates"}, # via candidate details
            {"name": "offers", "display_name": "Offers", "route": "/offers-listing"},
            {"name": "intervention_queue", "display_name": "Intervention Queue", "route": "/recruiter/intervention-queue"},
            {"name": "rehire_approvals", "display_name": "Rehire Approvals", "route": "/recruiter/rehire-approvals"},
            {"name": "risk_dashboard", "display_name": "Risk Dashboard", "route": "/recruiter/risk-dashboard"},
            {"name": "thunder_analytics", "display_name": "Thunder Analytics", "route": "/recruiter/thunder-analytics"},
            {"name": "bulk_launch", "display_name": "Bulk Launch", "route": "/recruiter/bulk-launch"},
            {"name": "thunder_chat", "display_name": "Thunder Chat", "route": "/thunder"},
        ]
    },
    "Workforce": {
        "display_name": "Workforce",
        "description": "Employee management",
        "resources": [
            {"name": "employees", "display_name": "Employees", "route": "/employees"},
            {"name": "employee_conversion", "display_name": "Employee Conversion", "route": "/employee-conversion"},
            {"name": "allocations", "display_name": "Allocations", "route": "/allocations"},
            {"name": "htd_intake", "display_name": "HTD Intake", "route": "/htd-intake"},
            {"name": "hm_candidate_review", "display_name": "HM Candidate Review", "route": "/hm-candidate-review"},
            {"name": "utilization_dashboard", "display_name": "Utilization Dashboard", "route": "/utilization-dashboard"},
            {"name": "training_certification", "display_name": "Training & Certification", "route": "/training-certification"},
            {"name": "buddy_program", "display_name": "Buddy Program", "route": "/buddy-program"},
        ]
    },
    "Project Management": {
        "display_name": "Project Management",
        "description": "Project and resource management",
        "resources": [
            {"name": "projects", "display_name": "Projects", "route": "/projects"},
            {"name": "resource_management", "display_name": "Resource Management", "route": "/resource-management"},
            {"name": "core_pull", "display_name": "Core Pull", "route": "/core-pull"},
        ]
    },
    "Finance": {
        "display_name": "Finance",
        "description": "Financial management",
        "resources": [
            {"name": "my_expenses", "display_name": "My Expenses", "route": "/my-expenses"},
            {"name": "timesheets", "display_name": "Timesheets", "route": "/timesheets"},
            {"name": "invoices", "display_name": "Invoices", "route": "/invoices"},
            {"name": "invoice_management", "display_name": "Invoice Management", "route": "/invoice-management"},
            {"name": "revenue", "display_name": "Revenue", "route": "/revenue"},
            {"name": "forecast", "display_name": "Forecast", "route": "/forecast"},
            {"name": "forecast_vs_actual", "display_name": "Forecast vs Actual", "route": "/forecast-vs-actual"},
            {"name": "finance_operations", "display_name": "Finance Operations", "route": "/finance-operations"},
        ]
    },
    "Sales": {
        "display_name": "Sales",
        "description": "Sales and business development",
        "resources": [
            {"name": "client_management", "display_name": "Client Management", "route": "/client-management"},
            {"name": "opportunity_pipeline", "display_name": "Opportunity Pipeline", "route": "/opportunity-pipeline"},
            {"name": "demand_confirmation", "display_name": "Demand Confirmation", "route": "/demand-confirmation"},
            {"name": "troy_partner_dashboard", "display_name": "Troy Partner Dashboard", "route": "/troy-partner-dashboard"},
        ]
    },
    "Admin": {
        "display_name": "Admin",
        "description": "System administration",
        "resources": [
            {"name": "users_access_control", "display_name": "Users & Access Control", "route": "/admin/users-access-control"},
            {"name": "locale_currency", "display_name": "Locale & Currency", "route": "/settings/locale"},
            {"name": "ai_configuration", "display_name": "AI Configuration", "route": "/admin/ai-config"},
            {"name": "message_templates", "display_name": "Message Templates", "route": "/settings/templates"},
            {"name": "ticket_routing", "display_name": "Ticket Routing & SLA", "route": "/admin/ticket-routing"},
            {"name": "executive_signal", "display_name": "Executive Signal", "route": "/executive-signal"},
            {"name": "error_log", "display_name": "Error Log", "route": "/admin/error-log"},
            {"name": "admin_settings", "display_name": "Admin Settings", "route": "/admin/settings"},
            {"name": "business_units", "display_name": "Business Units", "route": "/admin/business-units"},
            {"name": "agent_state_dashboard", "display_name": "Agent State Dashboard", "route": "/admin/agent-state-dashboard"},
        ]
    },
    "Analytics": {
        "display_name": "Analytics",
        "description": "Analytics and reporting",
        "resources": [
            {"name": "bi_explorer", "display_name": "BI Explorer", "route": "/bi-explorer"},
        ]
    },
}




def init_role_template_system(db: Session, tenant_id: int):
    """Initialize all modules and resources for a tenant. NO hardcoded role templates."""

    # Create all modules and resources (user creates role templates via UI)
    for module_name, module_data in MODULES_AND_RESOURCES.items():
        # Check if module already exists
        module = db.query(Module).filter(
            Module.name == module_name,
            Module.tenant_id == tenant_id
        ).first()

        if not module:
            module = Module(
                name=module_name,
                display_name=module_data["display_name"],
                description=module_data.get("description"),
                tenant_id=tenant_id,
                enabled=True
            )
            db.add(module)
            db.flush()

        # Create resources for this module
        for resource_data in module_data.get("resources", []):
            resource = db.query(Resource).filter(
                Resource.module_id == module.id,
                Resource.name == resource_data["name"]
            ).first()

            if not resource:
                resource = Resource(
                    module_id=module.id,
                    name=resource_data["name"],
                    display_name=resource_data["display_name"],
                    route_path=resource_data.get("route"),
                    tenant_id=tenant_id,
                    enabled=True
                )
                db.add(resource)

    db.commit()
