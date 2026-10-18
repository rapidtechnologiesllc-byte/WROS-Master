"""Left-navigation rebuild (CEO decisions 2026-10-17, #406).

1. Access preservation: for every seeded role template, the menu routes it reaches today differ from
   the routes it reached before the rebuild (the menu as of f122237, frozen below) only by the
   intended removals/additions. Grants are not touched by the rebuild, so "after" is the live
   navigation endpoint on a role holding exactly the grants the role held before.
2. Regrouping keeps grants: a resource the contract moves to another module keeps its row (and
   every grant on it); a resource dropped from the contract is disabled, its grants kept.
3. Every menu item's screen API checks the item's own resource (no nav-only gates).
"""
import ast
import pathlib
import uuid

import pytest
from sqlalchemy.orm import Session

from app.api.v1.endpoints.navigation import get_user_navigation
from app.contracts.api_contract import MODULES_AND_RESOURCES
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.models.tenant import Tenant
from app.models.user import Users

ENDPOINTS = pathlib.Path(__file__).resolve().parent.parent / "app" / "api" / "v1" / "endpoints"

# ---------------------------------------------------------------------------------------------
# The menu before the rebuild (backend/app/seeds/init_resources.py at f122237): resource -> route.
# ---------------------------------------------------------------------------------------------
BEFORE_ROUTES = {
    "dashboard": "/", "my-tasks": "/my-tasks", "my-timesheet": "/my-timesheet", "my-expenses": "/my-expenses",
    "my-referrals": "/my-referrals", "candidates": "/candidates", "jobs": "/jobs", "submissions": "/submissions",
    "offer-letters": "/offers-listing", "intervention-queue": "/recruiter/intervention-queue",
    "rehire-approval": "/recruiter/rehire-approvals", "thunder-analytics": "/recruiter/thunder-analytics",
    "checklists": "/checklist-templates", "candidate-review": "/hm-candidate-review",
    "risk-dashboard": "/recruiter/risk-dashboard", "bulk-launch": "/recruiter/bulk-launch",
    "employees": "/employees", "allocations": "/allocations", "timesheets": "/timesheets",
    "htd-intake": "/htd-intake", "buddy-program": "/buddy-program", "convert-to-employee": "/hiring-pipeline",
    "utilization-dashboard": "/utilization-dashboard", "resource-forecast": "/forecast",
    "workforce-overview": "/workforce", "clients": "/client-management", "opportunities": "/opportunity-pipeline",
    "sales-ops": "/revenue", "demand-confirmation": "/demand-confirmation", "projects": "/projects",
    "core-pull": "/core-pull", "invoices": "/invoices", "forecasts": "/forecast",
    "finance-operations": "/finance-operations", "revenue": "/pnl", "bi-explorer": "/bi-explorer",
    "api-keys": "/api-keys", "error-logs": "/admin/error-log", "system-health": "/system-health",
    "slm-training-data": "/admin/slm-training", "message-queue": "/admin/messagequeue",
    "ticket-routing": "/admin/ticket-routing", "ai-config": "/admin/ai-config", "locale-currency": "/settings/locale",
    "ceo-dashboard": "/ceo-fy-progress", "goals": "/executive-revenue-dashboard", "cfo-dashboard": "/cfo-dashboard",
    "partner-dashboard": "/partner-dashboard", "executive-signal": "/executive-signal",
    "admin-agent-state": "/admin/agent-state-dashboard", "admin-weekly-recap": "/admin/weekly-recap",
    "bu-head-dashboard": "/bu-head-dashboard", "users-access-control": "/admin/users-access-control/users",
    "certifications": "/admin/certifications", "ceo-dashboard-view": "/ceo-fy-progress",
    "cfo-dashboard-view": "/cfo-dashboard", "partner-dashboard-view": "/partner-dashboard",
    "bu-head-dashboard-view": "/bu-head-dashboard", "ask-thunder": "/thunder", "slm-dashboard": "/admin/slm-dashboard",
}
BEFORE_EXTRA = {"candidates": "/linkedin-pipeline"}

# Every resource the contract had before the rebuild (system roles are seeded with all of them).
BEFORE_RESOURCES = set(BEFORE_ROUTES) | {
    "ask-flash", "notifications", "activity-feed", "interviews", "flash-missions", "onboarding", "pipeline-management",
    "resources", "budget", "schedule", "work-orders", "expenses", "payroll", "reports", "invoice-management",
    "executive-revenue-dashboard", "analytics", "configuration", "agents", "newsletters", "admin-settings",
    "role-templates", "business-units", "delivery-centers", "organizational-hierarchy", "org-roles",
}

# The leadership role templates as seeded before the rebuild (db_contract.LEADERSHIP_ROLES at f122237).
BEFORE_LEADERSHIP = {
    "Partner": {"activity-feed", "allocations", "analytics", "ask-flash", "ask-thunder", "bu-head-dashboard",
                "bu-head-dashboard-view", "business-units", "candidates", "clients", "dashboard", "delivery-centers",
                "demand-confirmation", "employees", "executive-revenue-dashboard", "forecasts", "goals", "interviews",
                "invoices", "jobs", "my-expenses", "my-referrals", "my-tasks", "my-timesheet", "notifications",
                "offer-letters", "opportunities", "organizational-hierarchy", "partner-dashboard",
                "partner-dashboard-view", "pipeline-management", "projects", "resource-forecast", "resources",
                "revenue", "submissions", "utilization-dashboard", "workforce-overview"},
    "BU Head": {"activity-feed", "allocations", "ask-flash", "ask-thunder", "bu-head-dashboard",
                "bu-head-dashboard-view", "business-units", "candidates", "clients", "dashboard", "delivery-centers",
                "demand-confirmation", "employees", "forecasts", "goals", "interviews", "invoices", "jobs",
                "my-expenses", "my-referrals", "my-tasks", "my-timesheet", "notifications", "offer-letters",
                "onboarding", "opportunities", "organizational-hierarchy", "pipeline-management", "projects",
                "resource-forecast", "resources", "revenue", "submissions", "timesheets", "utilization-dashboard",
                "workforce-overview"},
    "Finance Manager": {"activity-feed", "allocations", "analytics", "ask-flash", "business-units", "clients",
                        "dashboard", "employees", "executive-revenue-dashboard", "expenses", "finance-operations",
                        "forecasts", "invoice-management", "invoices", "my-expenses", "my-referrals", "my-tasks",
                        "my-timesheet", "notifications", "opportunities", "payroll", "pipeline-management",
                        "projects", "reports", "revenue", "timesheets"},
    "Sales": {"activity-feed", "ask-flash", "business-units", "clients", "dashboard", "demand-confirmation", "jobs",
              "my-expenses", "my-referrals", "my-tasks", "my-timesheet", "notifications", "opportunities",
              "pipeline-management", "projects"},
    "Employee": {"activity-feed", "ask-flash", "dashboard", "my-expenses", "my-referrals", "my-tasks",
                 "my-timesheet", "notifications"},
}
SYSTEM_ROLES = ("Super Admin", "Admin", "Manager", "User", "Ops")
SEEDED_ROLES = {**{name: BEFORE_RESOURCES for name in SYSTEM_ROLES}, **BEFORE_LEADERSHIP}

# The intended menu changes (CEO decisions 1 and 4). Nothing else may change for anyone.
# Decision 1: the named CEO / CFO / BU Head dashboards are each person's Home ("/"), the Executive
# Dashboards module duplicated them, "Forecasts" duplicated Resource Forecast's /forecast, Allocations is
# the Employees > Allocations tab, Ask Thunder is a QA simulator. "Forecasts" now opens Forecast vs Actual
# (its API checks forecasts), so a role holding only forecasts swaps /forecast for /forecast-vs-actual.
INTENDED_REMOVALS = {"/ceo-fy-progress", "/cfo-dashboard", "/bu-head-dashboard", "/allocations", "/thunder"}
INTENDED_ADDITIONS = {"/forecast-vs-actual": "forecasts"}  # route -> resource whose view grant adds it
# Decision 3: merged screens. The old route redirects to the merged screen's tab; every role that
# reached any of the parts reaches the merged screen (its tabs follow the same permissions).
ROUTE_MOVES = {
    "/submissions": "/pipeline", "/hiring-pipeline": "/pipeline",
    "/recruiter/intervention-queue": "/recruiter/watch", "/recruiter/risk-dashboard": "/recruiter/watch",
    "/recruiter/thunder-analytics": "/recruiter/watch",
    "/hm-candidate-review": "/hm-review", "/recruiter/rehire-approvals": "/hm-review",
    "/utilization-dashboard": "/workforce",
}


def _expected_after(grants):
    before = {BEFORE_ROUTES[r] for r in grants if r in BEFORE_ROUTES}
    before |= {route for r, route in BEFORE_EXTRA.items() if r in grants}
    moved = {ROUTE_MOVES.get(route, route) for route in before}
    added = {route for route, resource in INTENDED_ADDITIONS.items() if resource in grants}
    removed = set(INTENDED_REMOVALS)
    if "resource-forecast" not in grants:  # /forecast was only reachable through the Forecasts duplicate
        removed.add("/forecast")
    return before, (moved - {ROUTE_MOVES.get(r, r) for r in removed}) | added


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _uid():
    return uuid.uuid4().hex[:8]


def _tenant(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()


def _contract_resource(db, name):
    """The canonical row the permission service resolves for a contract resource (created if missing)."""
    module_name = next(m for m, names in MODULES_AND_RESOURCES.items() if name in names)
    module = db.query(Module).filter_by(name=module_name).first()
    if module is None:
        module = Module(tenant_id=1, name=module_name, display_name=module_name, enabled=True)
        db.add(module)
        db.flush()
    resource = db.query(Resource).filter_by(module_id=module.id, name=name).first()
    if resource is None:
        resource = Resource(tenant_id=1, module_id=module.id, name=name, display_name=name, enabled=True)
        db.add(resource)
        db.flush()
    return resource


def _user_with(db, view_resources, job_title=None, **role_fields):
    """A user whose role template grants view on exactly these resources (those still in the contract)."""
    _tenant(db)
    role = RoleTemplate(tenant_id=1, name=f"nav-{_uid()}", display_name="Nav", hierarchy_level=5,
                        enabled=True, **{"org_level_access": False, **role_fields})
    db.add(role)
    db.flush()
    in_contract = {r for names in MODULES_AND_RESOURCES.values() for r in names}
    for name in sorted(set(view_resources) & in_contract):
        db.add(RoleTemplatePermission(role_template_id=role.id, resource_id=_contract_resource(db, name).id,
                                      tenant_id=1, can_view=True))
    user = Users(UserID=f"U-{_uid()}", UserName="Nav User", UserEmail=f"n{_uid()}@x.com", UserPassword="x",
                 UserRole="x", tenant_id=1, role_template_id=role.id, job_title=job_title)
    db.add(user)
    db.flush()
    return user


def _menu(db, user):
    return get_user_navigation(db=db, current_user=user)["data"]["groups"]


def _routes(db, user):
    return {item["route"] for group in _menu(db, user) for item in group["items"]}


@pytest.mark.parametrize("role_name", sorted(SEEDED_ROLES))
def test_every_seeded_role_keeps_its_screens_except_the_intended_removals(db, role_name):
    grants = SEEDED_ROLES[role_name]
    before, expected = _expected_after(grants)
    after = _routes(db, _user_with(db, grants))
    assert after == expected, (f"{role_name}: lost {sorted(expected - after)}, gained {sorted(after - expected)} "
                               f"(before the rebuild: {len(before)} routes)")


def test_menu_is_grouped_into_the_approved_modules_in_order(db):
    groups = [g["label"] for g in _menu(db, _user_with(db, BEFORE_RESOURCES))]
    assert groups == ["Personal", "Recruitment", "Workforce", "Sales & Delivery", "Finance", "Leadership",
                      "AI Operations", "Admin & Settings"]


def test_renamed_labels(db):
    labels = {item["route"]: item["label"] for g in _menu(db, _user_with(db, BEFORE_RESOURCES)) for item in g["items"]}
    assert labels["/"] == "Home"
    assert labels["/offers-listing"] == "Offers"
    assert labels["/admin/users-access-control/users"] == "Users & Access"
    assert labels["/revenue"] == "Revenue Health"
    assert labels["/pnl"] == "P&L"
    assert labels["/forecast-vs-actual"] == "Forecast vs Actual"


def test_executive_duplicates_are_gone_from_the_catalogue():
    from app.seeds.init_resources import RESOURCE_ROUTES

    in_contract = {r for names in MODULES_AND_RESOURCES.values() for r in names}
    assert "Executive Dashboards" not in MODULES_AND_RESOURCES
    assert not {r for r in in_contract if r.endswith("-dashboard-view")}
    # still permission-only: authority.home_dashboard needs them to pick each person's Home
    assert {"ceo-dashboard", "cfo-dashboard", "bu-head-dashboard"} <= in_contract
    assert not {"ceo-dashboard", "cfo-dashboard", "bu-head-dashboard", "allocations", "ask-thunder"} & set(RESOURCE_ROUTES)


RETIRED_RESOURCES = {"onboarding", "budget", "schedule", "payroll", "reports", "invoice-management",
                     "executive-revenue-dashboard", "analytics", "ceo-dashboard-view", "cfo-dashboard-view",
                     "partner-dashboard-view", "bu-head-dashboard-view"}


def test_resources_that_gated_nothing_left_the_catalogue():
    """CEO decision 4: they gated no screen and no API. Existing grants on them are disabled by
    _initialize_contract_catalog_only, not deleted (test above)."""
    from app.core.db_contract import LEADERSHIP_ROLES

    in_contract = {r for names in MODULES_AND_RESOURCES.values() for r in names}
    assert not RETIRED_RESOURCES & in_contract
    for spec in LEADERSHIP_ROLES.values():  # a fresh database would refuse unknown names
        assert not RETIRED_RESOURCES & {r for names in spec["permissions"].values() for r in names}
    checked = set()
    for path in (ENDPOINTS.parent.parent.parent).rglob("*.py"):
        text = path.read_text()
        checked |= {r for r in RETIRED_RESOURCES if f'"{r}",' in text and "permission" in text and path.name != "db_contract.py"}
    assert not checked


def _position(db, name, code, rank):
    from app.models.org_structure import OrgPosition

    if db.query(OrgPosition).filter_by(name=name).first() is None:
        db.add(OrgPosition(name=name, rank=rank, rbac_role_name=code))
        db.flush()


def test_the_partner_dashboard_is_listed_once_for_a_partner_whose_home_it_is(db):
    _position(db, "Partner", "partner", 1)
    partner = _user_with(db, {"dashboard", "partner-dashboard"}, job_title="Partner")
    assert "/partner-dashboard" not in _routes(db, partner) and "/" in _routes(db, partner)
    # anyone else who may view it (e.g. leadership looking at a partner) keeps the menu item
    assert "/partner-dashboard" in _routes(db, _user_with(db, {"dashboard", "partner-dashboard"}))


def test_merged_screens_have_one_menu_item_each(db):
    from app.seeds.init_resources import NAV_LABELS, RESOURCE_ROUTES

    items = [item for g in _menu(db, _user_with(db, BEFORE_RESOURCES)) for item in g["items"]]
    routes = [item["route"] for item in items]
    assert len(routes) == len(set(routes))
    for old, new in ROUTE_MOVES.items():
        assert old not in routes and new in routes
        parts = {r for r, route in RESOURCE_ROUTES.items() if route == new}
        assert len({NAV_LABELS.get(r) for r in parts}) == 1, f"{new}: parts disagree on the menu label"
        # a role holding only one part still reaches the merged screen
        for part in parts:
            assert new in _routes(db, _user_with(db, {part}))


def test_linkedin_pipeline_follows_candidates(db):
    groups = _menu(db, _user_with(db, {"candidates"}))
    recruitment = [item["route"] for g in groups if g["label"] == "Recruitment" for item in g["items"]]
    assert recruitment.index("/linkedin-pipeline") == recruitment.index("/candidates") + 1
    assert not {"/candidates", "/linkedin-pipeline"} & _routes(db, _user_with(db, {"jobs"}))


# ---------------------------------------------------------------------------------------------
# Regrouping keeps grants; retired resources are disabled, never destroyed
# ---------------------------------------------------------------------------------------------

def test_a_resource_moved_to_another_module_keeps_its_row_and_grants(db, monkeypatch):
    import app.contracts.api_contract as contract
    from app.core.db_contract import _place_contract_resources

    _tenant(db)
    old = Module(tenant_id=1, name=f"Old-{_uid()}", display_name="Old", enabled=True)
    new = Module(tenant_id=1, name=f"New-{_uid()}", display_name="New", enabled=True)
    db.add_all([old, new])
    db.flush()
    name = f"moved-{_uid()}"
    resource = Resource(tenant_id=1, module_id=old.id, name=name, display_name=name, enabled=True)
    db.add(resource)
    db.flush()
    role = RoleTemplate(tenant_id=1, name=f"r-{_uid()}", display_name="R", enabled=True)
    db.add(role)
    db.flush()
    grant = RoleTemplatePermission(role_template_id=role.id, resource_id=resource.id, tenant_id=1,
                                   can_view=True, can_edit=True)
    db.add(grant)
    db.flush()

    monkeypatch.setattr(contract, "MODULES_AND_RESOURCES", {new.name: [name]})
    assert _place_contract_resources(db, {new.name: new}) == 1
    db.refresh(resource)
    assert resource.module_id == new.id and resource.enabled
    assert db.query(Resource).filter_by(name=name).count() == 1  # no grant-less twin
    kept = db.query(RoleTemplatePermission).filter_by(role_template_id=role.id, resource_id=resource.id).one()
    assert kept.can_view and kept.can_edit
    assert _place_contract_resources(db, {new.name: new}) == 0  # idempotent


def test_a_resource_dropped_from_the_contract_is_disabled_and_its_grants_kept(db):
    from app.core.db_contract import _initialize_contract_catalog_only

    _tenant(db)
    module = Module(tenant_id=1, name=f"Retired-{_uid()}", display_name="Retired", enabled=True)
    db.add(module)
    db.flush()
    resource = Resource(tenant_id=1, module_id=module.id, name=f"retired-{_uid()}", display_name="x", enabled=True)
    db.add(resource)
    db.flush()
    role = RoleTemplate(tenant_id=1, name=f"r-{_uid()}", display_name="R", enabled=True)
    db.add(role)
    db.flush()
    db.add(RoleTemplatePermission(role_template_id=role.id, resource_id=resource.id, tenant_id=1, can_view=True))
    db.flush()

    _initialize_contract_catalog_only(db)
    db.refresh(resource)
    db.refresh(module)
    assert not resource.enabled and not module.enabled
    assert db.query(RoleTemplatePermission).filter_by(role_template_id=role.id, resource_id=resource.id).count() == 1


# ---------------------------------------------------------------------------------------------
# Menu gate == API gate: each screen's own endpoints check the menu item's resource
# ---------------------------------------------------------------------------------------------

# (endpoint module, route path as declared, method) -> the resource the menu item uses
SCREEN_APIS = {
    ("risk_dashboard.py", "/dashboard", "get"): "risk-dashboard",
    ("risk_dashboard.py", "/dashboard/candidates/{candidate_id}/add-to-queue", "post"): "risk-dashboard",
    ("thunder_analytics.py", "/thunder", "get"): "thunder-analytics",
    ("interviews.py", "/rehire-reviews", "get"): "rehire-approval",
    ("interviews.py", "/rehire-reviews/{review_id}/decide", "post"): "rehire-approval",
    ("interviews.py", "/hm-review/my-candidates", "get"): "candidate-review",
    ("bulk_engagement.py", "/candidates/bulk-import", "post"): "bulk-launch",
    ("bulk_engagement.py", "/candidates/bulk-engage", "post"): "bulk-launch",
    ("bulk_engagement.py", "/candidates/bulk-import/list", "get"): "bulk-launch",
    ("checklist_templates.py", "/hr/templates", "post"): "checklists",
    ("checklist_templates.py", "/hr/templates/{template_id}", "put"): "checklists",
    ("checklist_templates.py", "/hr/templates/{template_id}/items", "post"): "checklists",
    ("hiring_pipeline.py", "", "get"): "convert-to-employee",
    ("hiring_pipeline.py", "/candidate/{candidate_id}/evaluate", "post"): "convert-to-employee",
    ("employees.py", "/utilization-summary", "get"): "utilization-dashboard",
    ("employees.py", "/bench-cost-summary", "get"): "utilization-dashboard",
    ("revenue.py", "/leakage", "get"): "sales-ops",
    ("revenue.py", "/leakage/scan", "post"): "sales-ops",
    ("revenue.py", "/reconciliation/alerts", "get"): "sales-ops",
    ("cost_rate.py", "/pnl/bu/{business_unit_id}", "get"): "finance-operations",
    ("cost_rate.py", "/intercompany-settlements", "get"): "finance-operations",
    ("agent_maturity.py", "/maturity", "get"): "admin-agent-state",
    ("agent_maturity.py", "/maturity/{agent_name}", "get"): "admin-agent-state",
    ("tenants.py", "/me/locale", "get"): "locale-currency",
    ("tenants.py", "/me/locale", "patch"): "locale-currency",
    ("certifications_admin.py", "/list", "get"): "certifications",
    ("certifications_admin.py", "/create", "post"): "certifications",
    ("system_health.py", "/health", "get"): "system-health",
    ("admin_weekly_recap.py", "/weekly-recap", "get"): "admin-weekly-recap",
}


def _declared_gates(filename):
    """{(path, method): resource} for every route decorator with a require_resource_permission dependency."""
    gates = {}
    for node in ast.walk(ast.parse((ENDPOINTS / filename).read_text())):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            if not (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute) and deco.args
                    and isinstance(deco.args[0], ast.Constant)):
                continue
            for call in ast.walk(deco):
                if (isinstance(call, ast.Call) and getattr(call.func, "id", None) == "require_resource_permission"
                        and isinstance(call.args[0], ast.Constant)):
                    gates[(deco.args[0].value, deco.func.attr)] = call.args[0].value
    return gates


@pytest.mark.parametrize("endpoint", sorted(SCREEN_APIS), ids=lambda e: f"{e[0]}:{e[2]} {e[1]}")
def test_screen_api_checks_the_menu_items_resource(endpoint):
    filename, path, method = endpoint
    assert _declared_gates(filename).get((path, method)) == SCREEN_APIS[endpoint]


def test_every_screen_api_resource_is_a_menu_resource():
    from app.seeds.init_resources import RESOURCE_ROUTES

    assert set(SCREEN_APIS.values()) <= set(RESOURCE_ROUTES)
