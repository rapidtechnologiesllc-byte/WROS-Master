"""Every background job production may run, run by app.workers.scheduled_jobs_worker
(cron every 5 min). Nothing runs unless named in SCHEDULED_JOBS_ENABLED.

A job that contacts people outside the company (sends_external=True) must
declare a backlog_guard: a function that expires stale work before the first
run, so enabling it can never act on a months-old backlog. Jobs superseded by
the Thunder email cadence (follow-ups, campaigns, reactivation, ghosting,
keep-warm) are deliberately absent.
"""
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, Optional


@dataclass(frozen=True)
class ScheduledJob:
    name: str
    target: str  # "package.module:function", called as fn(db)
    interval: timedelta
    timeout_s: int
    sends_external: bool = False
    daily_after_utc: Optional[str] = None  # "HH:MM": at most once per UTC day, after this time
    backlog_guard: Optional[str] = None  # "package.module:function", called as fn(db, now)


_JOBS = (
    ScheduledJob("timesheet_draft_creation", "app.services.timesheet_service:create_weekly_draft_batch",
                 timedelta(hours=6), timeout_s=300),
    # internal staff only (employee, then reporting manager); last completed week only
    ScheduledJob("timesheet_reminders", "app.services.timesheet_nag_service:run_timesheet_nag_job",
                 timedelta(days=1), timeout_s=300, daily_after_utc="13:00"),
    ScheduledJob("ar_follow_up", "app.services.ar_followup_service:run_ar_follow_up_job",
                 timedelta(days=1), timeout_s=300, daily_after_utc="09:30"),
    ScheduledJob("expire_bu_ownerships", "app.services.candidate_pool_service:expire_bu_ownerships",
                 timedelta(days=1), timeout_s=120, daily_after_utc="00:00"),
    ScheduledJob("daily_revenue_scan", "app.services.revenue_scanning_service:run_daily_revenue_scan_job",
                 timedelta(days=1), timeout_s=300, daily_after_utc="02:00"),
    ScheduledJob("engagement_metrics", "app.services.engagement_metrics_service:run_engagement_metrics_job",
                 timedelta(hours=4), timeout_s=300),
    # internal only: re-derives hiring stages from facts and backfills pipelines
    ScheduledJob("hiring_pipeline_sweep", "app.services.hiring_pipeline_service:run_pipeline_sweep",
                 timedelta(hours=1), timeout_s=300),
    # internal only: confirmed client start dates become placements + allocations
    ScheduledJob("client_start_date", "app.services.client_onboarding_service:run_start_date_job",
                 timedelta(days=1), timeout_s=300, daily_after_utc="01:00"),
    # internal only: last month's fully approved timesheets -> DRAFT invoice + review task for Finance
    # (Senior Manager+); the client is emailed only after Finance approves (invoice_automation_service)
    ScheduledJob("auto_invoicing", "app.services.invoice_automation_service:run_auto_invoicing",
                 timedelta(days=1), timeout_s=600, daily_after_utc="04:00",
                 backlog_guard="app.services.invoice_automation_service:backlog_guard"),
    # candidate-facing: queues first engagement (email cadence) for contactable candidates not yet
    # engaged; the cadence itself enforces send caps, window, gap and consent
    ScheduledJob("thunder_engagement_sweep", "app.services.thunder_engagement_sweep:run_sweep",
                 timedelta(minutes=10), timeout_s=120, sends_external=True,
                 backlog_guard="app.services.thunder_engagement_sweep:backlog_guard"),
    # internal only: employees who meet the Core certification rules get one approval task for
    # their BU Head; pending requests follow the current head (core_certification_service)
    ScheduledJob("core_certification_sweep", "app.services.core_certification_service:run_daily_sweep",
                 timedelta(days=1), timeout_s=300, daily_after_utc="05:00"),
    # candidate- and interviewer-facing: interview reminders (before the start) and feedback
    # nudges (after the end), each sent once and only near its due time
    ScheduledJob("interview_reminders", "app.services.interview_reminder_job:run",
                 timedelta(minutes=5), timeout_s=120, sends_external=True,
                 backlog_guard="app.services.interview_reminder_job:backlog_guard"),
    # candidate- and interviewer-facing: Flash missions (jobs created in the Flash chat) -- bench
    # first, sourcing, interview scheduling as the requester, feedback chasing, until positions are
    # filled by candidates who joined (flash_mission_service); off unless FLASH_MISSIONS_ENABLED
    ScheduledJob("flash_mission_sweep", "app.services.flash_mission_service:run_sweep",
                 timedelta(minutes=5), timeout_s=240, sends_external=True,
                 backlog_guard="app.services.flash_mission_service:backlog_guard"),
    # internal only: every billable working employee's weekly utilization for the last completed
    # weeks (resource_management_service.run_utilization_snapshot); writes metrics, tells nobody
    ScheduledJob("utilization_snapshot", "app.services.resource_management_service:run_utilization_snapshot",
                 timedelta(days=7), timeout_s=600, daily_after_utc="06:00"),
    # internal only: one task for the renewal owner when an ACTIVE allocation ends in
    # RENEWAL_ALERT_DAYS (60/30/15) days; never twice for the same allocation, term and threshold
    ScheduledJob("renewal_alerts", "app.services.allocation_renewal_service:run_renewal_alerts",
                 timedelta(days=1), timeout_s=300, daily_after_utc="06:00"),
    # internal only: Finance gets one task per client PO (work order) ending within
    # PO_EXPIRY_ALERT_DAYS, so it is renewed before hours stop being invoiceable
    ScheduledJob("po_expiry_alerts", "app.services.work_order_service:run_po_expiry_alerts",
                 timedelta(days=1), timeout_s=120, daily_after_utc="06:00"),
    ScheduledJob("birthday_drafts", "app.services.culture_agent_service:generate_birthday_drafts",
                 timedelta(days=1), timeout_s=120, daily_after_utc="03:00"),
)

JOBS: Dict[str, ScheduledJob] = {job.name: job for job in _JOBS}
