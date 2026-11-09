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
    # Recruiter Watch (intervention queue, risk, Thunder analytics) is a tab each of the Recruitment Dashboard
    # (CEO 2026-11-09)
    "intervention-queue": "/recruitment-dashboard",
    "risk-dashboard": "/recruitment-dashboard",
    "thunder-analytics": "/recruitment-dashboard",
    # Hiring Manager Review: candidate review + rehire approvals, a tab each
    "candidate-review": "/hm-review",
    "rehire-approval": "/hm-review",
    # Workforce
    # bench / Staff Aug / Core: where every employee stands (CEO 2026-10-14)
    "workforce-overview": "/workforce",
    "employees": "/employees",
    "timesheets": "/timesheets",
    # Buddy Program, HTD Intake and Demand vs Bench are tabs of Workforce Overview (CEO 2026-11-09)
    "buddy-program": "/workforce",
    "htd-intake": "/workforce",
    "resource-forecast": "/workforce",
    "utilization-dashboard": "/workforce",  # a tab of Workforce Overview
    # Sales & Delivery
    "clients": "/client-management",
    "opportunities": "/opportunity-pipeline",
    "projects": "/projects",
    "core-pull": "/core-pull",
    # Finance
    "invoices": "/invoices",
    "revenue": "/pnl",  # partner & org P&L
    "finance-operations": "/pnl",  # a tab of P&L
    "sales-ops": "/pnl",  # Revenue Health: a tab of P&L
    "forecasts": "/pnl",  # Forecast vs Actual: a tab of P&L
    # Leadership (CEO / CFO / BU Head dashboards are each person's Home, not menu items)
    # FY goal tree (Org > Location > Partner > BU) + executive revenue
    "goals": "/executive-revenue-dashboard",
    "executive-signal": "/executive-signal",
    "partner-dashboard": "/partner-dashboard",
    "bi-explorer": "/bi-explorer",
    # System (CEO 2026-11-09): health, error logs, agent health, message queue, SLM learning and AI config, a tab each
    "admin-agent-state": "/admin/system",
    "admin-weekly-recap": "/admin/system",
    "message-queue": "/admin/system",
    "slm-dashboard": "/admin/system",
    "slm-training-data": "/admin/system",
    "ai-config": "/admin/system",
    # Admin & Settings
    "users-access-control": "/admin/users-access-control/users",
    "role-templates": "/admin/users-access-control/role-templates",
    "business-units": "/admin/users-access-control/business-units",
    "delivery-centers": "/admin/users-access-control/delivery-centers",
    "organizational-hierarchy": "/admin/users-access-control/organizational-hierarchy",
    # Templates & Checklists: messages, checklists, email templates and certifications, a tab each
    "certifications": "/checklist-templates",
    "checklists": "/checklist-templates",
    "locale-currency": "/settings/locale",
    "bulk-launch": "/recruiter/bulk-launch",
    "api-keys": "/api-keys",
    "error-logs": "/admin/system",
    "system-health": "/admin/system",
    "ticket-routing": "/admin/ticket-routing",
}

# Menu labels where title-casing the resource name reads wrong
NAV_LABELS = {
    "dashboard": "Home",
    # Line Type: Core is called Direct everywhere (CEO 2026-11-03)
    "core-pull": "Direct Pull",
    "core-certification": "Direct Certification",
    "my-tasks": "My Tasks",
    "submissions": "Pipeline & Submissions",
    "convert-to-employee": "Pipeline & Submissions",
    "offer-letters": "Offers",
    "intervention-queue": "Recruitment Dashboard",
    "risk-dashboard": "Recruitment Dashboard",
    "thunder-analytics": "Recruitment Dashboard",
    "candidate-review": "Hiring Manager Review",
    "rehire-approval": "Hiring Manager Review",
    "workforce-overview": "Workforce Overview",
    "buddy-program": "Workforce Overview",
    "htd-intake": "Workforce Overview",
    "resource-forecast": "Workforce Overview",
    "utilization-dashboard": "Workforce Overview",
    "revenue": "P&L",
    "finance-operations": "P&L",
    "sales-ops": "P&L",
    "forecasts": "P&L",
    "goals": "Goals & Revenue",
    "bi-explorer": "BI Explorer",
    "admin-agent-state": "System",
    "slm-dashboard": "System",
    "admin-weekly-recap": "System",
    "slm-training-data": "System",
    "ai-config": "System",
    "message-queue": "System",
    "system-health": "System",
    "certifications": "Templates & Checklists",
    "users-access-control": "Users & Access",
    "checklists": "Templates & Checklists",
    "locale-currency": "Locale & Currency",
    "api-keys": "API Keys",
    "error-logs": "System",
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
    "invoices": [{"key": "sub-vendors", "label": "Sub-vendors", "route": "/sub-vendors"}],
    # LinkedIn Pipeline is a tab of Candidates (CEO 2026-11-09)
    "candidates": [{"key": "recruitment-dashboard", "label": "Recruitment Dashboard", "route": "/recruitment-dashboard"}],
    # My Performance (CEO 2026-10-24): everyone who has My Tasks; its self-service endpoints check
    # my-tasks too (app/api/v1/endpoints/performance.py)
    "my-tasks": [{"key": "my-performance", "label": "My Performance", "route": "/my-performance"}],
}

# Off the menu: reached as a tab of another screen, or from a task (core-pull: each conflict is a decision task for
# the business unit's leader, CEO 2026-11-09)
# candidate-review / rehire-approval: Hiring Manager Review opens from My Tasks; ticket-routing: retired from the menu
NAV_TAB_RESOURCES = {"role-templates", "business-units", "delivery-centers", "organizational-hierarchy", "core-pull",
                     "candidate-review", "rehire-approval", "ticket-routing"}
