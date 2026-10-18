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
    # Pipeline & Submissions: one screen, a tab per resource (CEO 2026-10-17); manual conversion
    # stays at /employee-conversion
    "submissions": "/pipeline",
    "convert-to-employee": "/pipeline",
    "offer-letters": "/offers-listing",
    # Recruiter Watch: intervention queue + risk + Thunder analytics, a tab each
    "intervention-queue": "/recruiter/watch",
    "risk-dashboard": "/recruiter/watch",
    "thunder-analytics": "/recruiter/watch",
    # Hiring Manager Review: candidate review + rehire approvals, a tab each
    "candidate-review": "/hm-review",
    "rehire-approval": "/hm-review",
    # Workforce
    # bench / Staff Aug / Core: where every employee stands (CEO 2026-10-14)
    "workforce-overview": "/workforce",
    "employees": "/employees",
    "timesheets": "/timesheets",
    "buddy-program": "/buddy-program",
    "htd-intake": "/htd-intake",
    "resource-forecast": "/demand-vs-bench",  # Demand vs Bench (forecast + bench matches tabs)
    "utilization-dashboard": "/workforce",  # a tab of Workforce Overview
    # Sales & Delivery
    "clients": "/client-management",
    "opportunities": "/opportunity-pipeline",
    "demand-confirmation": "/demand-confirmation",
    "projects": "/projects",
    "core-pull": "/core-pull",
    # Finance
    "invoices": "/invoices",
    "revenue": "/pnl",  # partner & org P&L
    "finance-operations": "/pnl",  # a tab of P&L
    "sales-ops": "/revenue",  # revenue leakage & reconciliation
    "forecasts": "/forecast-vs-actual",  # its API (/forecast-vs-actual) checks forecasts
    # Leadership (CEO / CFO / BU Head dashboards are each person's Home, not menu items)
    # FY goal tree (Org > Location > Partner > BU) + executive revenue
    "goals": "/executive-revenue-dashboard",
    "executive-signal": "/executive-signal",
    "partner-dashboard": "/partner-dashboard",
    "bi-explorer": "/bi-explorer",
    # AI Operations
    # Agent Health: agent state + weekly recap, a tab each
    "admin-agent-state": "/admin/agent-health",
    "admin-weekly-recap": "/admin/agent-health",
    "message-queue": "/admin/messagequeue",
    "slm-dashboard": "/admin/slm-dashboard",
    "slm-training-data": "/admin/slm-training",
    "ai-config": "/admin/ai-config",
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
}

# Menu labels where title-casing the resource name reads wrong
NAV_LABELS = {
    "dashboard": "Home",
    "my-tasks": "My Tasks",
    "submissions": "Pipeline & Submissions",
    "convert-to-employee": "Pipeline & Submissions",
    "offer-letters": "Offers",
    "intervention-queue": "Recruiter Watch",
    "risk-dashboard": "Recruiter Watch",
    "thunder-analytics": "Recruiter Watch",
    "candidate-review": "Hiring Manager Review",
    "rehire-approval": "Hiring Manager Review",
    "workforce-overview": "Workforce Overview",
    "htd-intake": "HTD Intake",
    "resource-forecast": "Demand vs Bench",
    "utilization-dashboard": "Workforce Overview",
    "revenue": "P&L",
    "finance-operations": "P&L",
    "sales-ops": "Revenue Health",
    "forecasts": "Forecast vs Actual",
    "goals": "Goals & Revenue",
    "bi-explorer": "BI Explorer",
    "admin-agent-state": "Agent Health",
    "slm-dashboard": "SLM Dashboard",
    "admin-weekly-recap": "Agent Health",
    "slm-training-data": "SLM Training Data",
    "ai-config": "AI Config",
    "users-access-control": "Users & Access",
    "locale-currency": "Locale & Currency",
    "api-keys": "API Keys",
    "error-logs": "Error Logs",
}

# Not menu items, on purpose: allocations (Employees > Allocations tab; /allocations redirects there)
# and ask-thunder (the /thunder candidate-chat test simulator, reachable by URL for QA).

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
