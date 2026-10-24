"""Project work without a client job, end to end (CEO 2026-10-24): allocation -> timesheet ->
invoice -> revenue chain, the same as a Staff Aug placement on a job."""
from datetime import date

from app.models.project import Project
from app.services import invoice_service, timesheet_service
from app.services.employee_allocation_service import allocate_employee_to_project
from app.services.revenue_chain_service import chain_lines
from tests.test_billable import _person
from tests.test_core_certification import _uid, db  # noqa: F401 -- fixtures
from tests.test_employee_import import mail, world  # noqa: F401 -- fixtures


def test_project_work_runs_through_timesheet_invoice_and_revenue(db, world):
    project = Project(tenant_id=1, client_id=world.client.id, name=f"Claims rollout {_uid()}",
                      delivery_engine="SPECIALITY", is_billable=True)
    db.add(project)
    worker = _person(db, world)
    db.flush()
    allocation = allocate_employee_to_project(db, tenant_id=1, employee=worker, demand=None, project=project,
                                              role="Policy Developer", billing_rate_usd_cents=10000,
                                              start_date=date(2026, 9, 1))
    assert allocation.demand_id is None and allocation.status == "ACTIVE"
    assert allocation.client_id == world.client.id and worker.status == "ALLOCATED"
    sheet = timesheet_service.create_weekly_draft(db, allocation, date(2026, 9, 7), tenant_id=1)
    db.flush()
    timesheet_service.upsert_entries(db, sheet, [{"entry_date": date(2026, 9, 7), "hours": 8, "entry_type": "BILLABLE"}])
    sheet.status = "APPROVED"
    db.commit()
    lines = [line for line in chain_lines(db, start=date(2026, 9, 1), end=date(2026, 9, 30), tenant_id=1)
             if line["timesheet_id"] == sheet.id]
    assert len(lines) == 1
    assert (lines[0]["job_id"], lines[0]["job_title"], lines[0]["project_id"]) == (None, "Policy Developer", project.id)
    invoice = invoice_service.generate_invoice(db, project, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30))
    assert invoice.total_usd_cents == 8 * 10000
