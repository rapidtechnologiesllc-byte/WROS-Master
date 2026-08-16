"""Initialize RBAC template system with all modules, resources, and default role templates."""

from sqlalchemy.orm import Session
from app.models.rbac_template import Module, Resource, RoleTemplate, RoleTemplatePermission


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


DEFAULT_ROLE_TEMPLATES = {
    "CEO": {
        "display_name": "CEO",
        "description": "Full system access across all Business Units",
        "is_system": True,
        "modules": {
            "Executive": ["ceo_fy_progress:V,C,E,D", "executive_revenue:V,C,E,D", "cfo_agent:V,C,E,D", "partner_roi_agent:V,C,E,D", "ceo_dashboard:V,C,E,D", "bu_head_dashboard:V,C,E,D"],
            "Recruitment": ["candidates:V,C,E,D", "jobs:V,C,E,D", "submissions:V,C,E,D", "interviews:V,C,E,D", "offers:V,C,E,D", "intervention_queue:V,C,E,D", "rehire_approvals:V,C,E,D", "risk_dashboard:V,C,E,D", "thunder_analytics:V,C,E,D", "bulk_launch:V,C,E,D", "thunder_chat:V,C,E,D"],
            "Workforce": ["employees:V,C,E,D", "employee_conversion:V,C,E,D", "allocations:V,C,E,D", "htd_intake:V,C,E,D", "hm_candidate_review:V,C,E,D", "utilization_dashboard:V,C,E,D", "training_certification:V,C,E,D", "buddy_program:V,C,E,D"],
            "Project Management": ["projects:V,C,E,D", "resource_management:V,C,E,D", "core_pull:V,C,E,D"],
            "Finance": ["my_expenses:V,C,E,D", "timesheets:V,C,E,D", "invoices:V,C,E,D", "invoice_management:V,C,E,D", "revenue:V,C,E,D", "forecast:V,C,E,D", "forecast_vs_actual:V,C,E,D", "finance_operations:V,C,E,D"],
            "Sales": ["client_management:V,C,E,D", "opportunity_pipeline:V,C,E,D", "demand_confirmation:V,C,E,D", "troy_partner_dashboard:V,C,E,D"],
            "Admin": ["users_access_control:V,C,E,D", "locale_currency:V,C,E,D", "ai_configuration:V,C,E,D", "message_templates:V,C,E,D", "ticket_routing:V,C,E,D", "executive_signal:V,C,E,D", "error_log:V,C,E,D", "admin_settings:V,C,E,D", "business_units:V,C,E,D", "agent_state_dashboard:V,C,E,D"],
            "Analytics": ["bi_explorer:V,C,E,D"],
        }
    },
    "CFO": {
        "display_name": "CFO",
        "description": "Finance and reporting access",
        "is_system": True,
        "modules": {
            "Executive": ["cfo_agent:V,C,E,D"],
            "Finance": ["my_expenses:V,C,E,D", "timesheets:V", "invoices:V,C,E,D", "invoice_management:V,C,E,D", "revenue:V,C,E,D", "forecast:V,C,E,D", "forecast_vs_actual:V,C,E,D", "finance_operations:V,C,E,D"],
            "Analytics": ["bi_explorer:V"],
            "Admin": ["users_access_control:V"],
        }
    },
    "Admin": {
        "display_name": "Admin",
        "description": "System administration access",
        "is_system": True,
        "modules": {
            "Admin": ["users_access_control:V,C,E,D", "locale_currency:V,C,E,D", "ai_configuration:V,C,E,D", "message_templates:V,C,E,D", "ticket_routing:V,C,E,D", "executive_signal:V", "error_log:V", "admin_settings:V,C,E,D", "business_units:V,C,E,D", "agent_state_dashboard:V"],
            "Recruitment": ["candidates:V", "jobs:V"],
        }
    },
    "Super User": {
        "display_name": "Super User",
        "description": "Full system access",
        "is_system": True,
        "modules": {
            "Executive": ["ceo_fy_progress:V,C,E,D", "executive_revenue:V,C,E,D", "cfo_agent:V,C,E,D", "partner_roi_agent:V,C,E,D", "ceo_dashboard:V,C,E,D", "bu_head_dashboard:V,C,E,D"],
            "Recruitment": ["candidates:V,C,E,D", "jobs:V,C,E,D", "submissions:V,C,E,D", "interviews:V,C,E,D", "offers:V,C,E,D", "intervention_queue:V,C,E,D", "rehire_approvals:V,C,E,D", "risk_dashboard:V,C,E,D", "thunder_analytics:V,C,E,D", "bulk_launch:V,C,E,D", "thunder_chat:V,C,E,D"],
            "Workforce": ["employees:V,C,E,D", "employee_conversion:V,C,E,D", "allocations:V,C,E,D", "htd_intake:V,C,E,D", "hm_candidate_review:V,C,E,D", "utilization_dashboard:V,C,E,D", "training_certification:V,C,E,D", "buddy_program:V,C,E,D"],
            "Project Management": ["projects:V,C,E,D", "resource_management:V,C,E,D", "core_pull:V,C,E,D"],
            "Finance": ["my_expenses:V,C,E,D", "timesheets:V,C,E,D", "invoices:V,C,E,D", "invoice_management:V,C,E,D", "revenue:V,C,E,D", "forecast:V,C,E,D", "forecast_vs_actual:V,C,E,D", "finance_operations:V,C,E,D"],
            "Sales": ["client_management:V,C,E,D", "opportunity_pipeline:V,C,E,D", "demand_confirmation:V,C,E,D", "troy_partner_dashboard:V,C,E,D"],
            "Admin": ["users_access_control:V,C,E,D", "locale_currency:V,C,E,D", "ai_configuration:V,C,E,D", "message_templates:V,C,E,D", "ticket_routing:V,C,E,D", "executive_signal:V,C,E,D", "error_log:V,C,E,D", "admin_settings:V,C,E,D", "business_units:V,C,E,D", "agent_state_dashboard:V,C,E,D"],
            "Analytics": ["bi_explorer:V,C,E,D"],
        }
    },
    "Recruiter": {
        "display_name": "Recruiter",
        "description": "Recruitment management",
        "is_system": True,
        "modules": {
            "Recruitment": ["candidates:V,C,E", "jobs:V", "submissions:V,C,E", "interviews:V,C,E", "offers:V", "thunder_chat:V,C,E", "bulk_launch:V,C,E"],
        }
    },
    "HR Manager": {
        "display_name": "HR Manager",
        "description": "HR and employee management",
        "is_system": True,
        "modules": {
            "Recruitment": ["candidates:V", "jobs:V"],
            "Workforce": ["employees:V,C,E", "employee_conversion:V,C", "allocations:V", "htd_intake:V,C,E", "hm_candidate_review:V,C,E"],
            "Finance": ["timesheets:V", "my_expenses:V"],
        }
    },
}


def init_rbac_template_system(db: Session, tenant_id: int):
    """Initialize all modules, resources, and default role templates for a tenant."""

    # Create all modules and resources
    module_map = {}  # name -> Module object
    resource_map = {}  # "module:resource" -> Resource object

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

        module_map[module_name] = module

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
                db.flush()

            resource_map[f"{module_name}:{resource_data['name']}"] = resource

    db.commit()

    # Create default role templates
    for role_name, role_data in DEFAULT_ROLE_TEMPLATES.items():
        # Check if role template already exists
        role_template = db.query(RoleTemplate).filter(
            RoleTemplate.name == role_name,
            RoleTemplate.tenant_id == tenant_id
        ).first()

        if not role_template:
            role_template = RoleTemplate(
                name=role_name,
                display_name=role_data["display_name"],
                description=role_data.get("description"),
                is_system=role_data.get("is_system", False),
                tenant_id=tenant_id,
                created_by="system"
            )
            db.add(role_template)
            db.flush()

        # Assign permissions based on modules and resources
        for module_name, resources_with_perms in role_data.get("modules", {}).items():
            for resource_perm_str in resources_with_perms:
                # Format: "resource_name:V,C,E,D" or "resource_name:V"
                parts = resource_perm_str.split(":")
                resource_name = parts[0]
                perms = parts[1].split(",") if len(parts) > 1 else []

                resource_key = f"{module_name}:{resource_name}"
                if resource_key in resource_map:
                    resource = resource_map[resource_key]

                    # Check if permission already exists
                    perm = db.query(RoleTemplatePermission).filter(
                        RoleTemplatePermission.role_template_id == role_template.id,
                        RoleTemplatePermission.resource_id == resource.id
                    ).first()

                    if not perm:
                        perm = RoleTemplatePermission(
                            role_template_id=role_template.id,
                            resource_id=resource.id,
                            can_view="V" in perms,
                            can_create="C" in perms,
                            can_edit="E" in perms,
                            can_delete="D" in perms
                        )
                        db.add(perm)

    db.commit()
