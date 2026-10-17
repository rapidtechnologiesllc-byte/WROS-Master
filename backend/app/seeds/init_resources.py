"""
Menu metadata for the permission catalogue: which resource is a screen (route), what the menu calls it,
and which screens are tabs or extra pages. The catalogue itself (modules, resources, their order) is
app.contracts.api_contract.MODULES_AND_RESOURCES; the database is initialised from it by
app.core.db_contract only (CLAUDE.md: one startup initializer, no seed scripts).
"""
from app.contracts import MODULES_AND_RESOURCES as CONTRACT_MODULES_AND_RESOURCES

MODULES_AND_RESOURCES = CONTRACT_MODULES_AND_RESOURCES

# Resource -> frontend page. A resource listed here is a screen and appears in the menu
# (navigation.py) gated by <resource>.can_view; a resource NOT listed here is permission-only
# and never becomes a menu item. Every route must exist in frontend/src/routes/Approutes.jsx
# or AdminRoutes.jsx. Each screen's own API checks the same resource (tests/test_navigation_rebuild.py).
RESOURCE_ROUTES = {
    # Personal
    "dashboard": "/",  # Home: the role's dashboard (authority.home_dashboard)
    "my-tasks": "/my-tasks",
    "my-timesheet": "/my-timesheet",
    "my-expenses": "/my-expenses",
    "my-referrals": "/my-referrals",
    # Recruitment
    "candidates": "/candidates",
    "jobs": "/jobs",
    "submissions": "/submissions",
    # the hiring pipeline (screen -> ... -> bench -> client); manual conversion stays at /employee-conversion
    "convert-to-employee": "/hiring-pipeline",
    "offer-letters": "/offers-listing",
    "intervention-queue": "/recruiter/intervention-queue",
    "risk-dashboard": "/recruiter/risk-dashboard",
    "thunder-analytics": "/recruiter/thunder-analytics",
    "candidate-review": "/hm-candidate-review",
    "rehire-approval": "/recruiter/rehire-approvals",
    # Workforce
    # bench / Staff Aug / Core: where every employee stands (CEO 2026-10-14)
    "workforce-overview": "/workforce",
    "employees": "/employees",
    "allocations": "/allocations",
    "timesheets": "/timesheets",
    "buddy-program": "/buddy-program",
    "htd-intake": "/htd-intake",
    "resource-forecast": "/forecast",
    "utilization-dashboard": "/utilization-dashboard",
    # Sales & Delivery
    "clients": "/client-management",
    "opportunities": "/opportunity-pipeline",
    "demand-confirmation": "/demand-confirmation",
    "projects": "/projects",
    "core-pull": "/core-pull",
    # Finance
    "invoices": "/invoices",
    "revenue": "/pnl",  # partner & org P&L
    "finance-operations": "/finance-operations",
    "sales-ops": "/revenue",  # revenue leakage & reconciliation
    "forecasts": "/forecast",
    # Leadership
    "ceo-dashboard": "/ceo-fy-progress",
    "cfo-dashboard": "/cfo-dashboard",
    "bu-head-dashboard": "/bu-head-dashboard",
    # FY goal tree (Org > Location > Partner > BU) + executive revenue
    "goals": "/executive-revenue-dashboard",
    "executive-signal": "/executive-signal",
    "partner-dashboard": "/partner-dashboard",
    "bi-explorer": "/bi-explorer",
    # AI Operations
    "admin-agent-state": "/admin/agent-state-dashboard",
    "admin-weekly-recap": "/admin/weekly-recap",
    "message-queue": "/admin/messagequeue",
    "slm-dashboard": "/admin/slm-dashboard",
    "slm-training-data": "/admin/slm-training",
    "ai-config": "/admin/ai-config",
    "ask-thunder": "/thunder",
    # Admin & Settings
    "users-access-control": "/admin/users-access-control/users",
    "role-templates": "/admin/users-access-control/role-templates",
    "business-units": "/admin/users-access-control/business-units",
    "delivery-centers": "/admin/users-access-control/delivery-centers",
    "organizational-hierarchy": "/admin/users-access-control/organizational-hierarchy",
    "certifications": "/admin/certifications",
    "checklists": "/checklist-templates",
    "locale-currency": "/settings/locale",
    "bulk-launch": "/recruiter/bulk-launch",
    "api-keys": "/api-keys",
    "error-logs": "/admin/error-log",
    "system-health": "/system-health",
    "ticket-routing": "/admin/ticket-routing",
    # Executive Dashboards (duplicates of the Leadership items)
    "ceo-dashboard-view": "/ceo-fy-progress",
    "cfo-dashboard-view": "/cfo-dashboard",
    "partner-dashboard-view": "/partner-dashboard",
    "bu-head-dashboard-view": "/bu-head-dashboard",
}

# Menu labels where title-casing the resource name reads wrong
NAV_LABELS = {
    "dashboard": "Home",
    "my-tasks": "My Tasks",
    "convert-to-employee": "Hiring Pipeline",
    "offer-letters": "Offers",
    "candidate-review": "HM Candidate Review",
    "rehire-approval": "Rehire Approvals",
    "workforce-overview": "Workforce Overview",
    "htd-intake": "HTD Intake",
    "utilization-dashboard": "Utilization & Bench Cost",
    "revenue": "P&L",
    "sales-ops": "Revenue Health",
    "forecasts": "Forecasts",
    "ceo-dashboard": "CEO Dashboard",
    "cfo-dashboard": "CFO Dashboard",
    "bu-head-dashboard": "BU Head Dashboard",
    "goals": "Goals & Revenue",
    "bi-explorer": "BI Explorer",
    "admin-agent-state": "Agent State",
    "slm-dashboard": "SLM Dashboard",
    "admin-weekly-recap": "Weekly Recap",
    "slm-training-data": "SLM Training Data",
    "ai-config": "AI Config",
    "users-access-control": "Users & Access",
    "locale-currency": "Locale & Currency",
    "api-keys": "API Keys",
    "error-logs": "Error Logs",
}

# Resources whose page is a tab of another page (Users & Access Control):
# they keep their route (deep links, permissions) but are not menu items.
# Extra screens governed by an existing resource's permission (no resource of their
# own): shown in the menu right after that resource for every role that can view it.
# The LinkedIn pipeline's endpoints all check "candidates", so its page does too --
# CEO, CFO, partners and BU heads see it under Recruitment, not only recruiters.
RESOURCE_EXTRA_PAGES = {
    "candidates": [{"key": "linkedin-pipeline", "label": "LinkedIn Pipeline", "route": "/linkedin-pipeline"}],
}

NAV_TAB_RESOURCES = {"role-templates", "business-units", "delivery-centers", "organizational-hierarchy"}
