"""Read-only production status, piped over SSH by .github/workflows/prod-status.yml:

    venv/bin/python - < backend/scripts/prod_status.py      (cwd: backend/)

Reports whether the things that make the system autonomous actually work on the
server: Graph mailbox permissions, enrichment sources, background jobs, the
queue (sent vs held "not sent" and why), Thunder cadence, invoices and revenue.
Prints counts and reasons only; email addresses and phone numbers are masked.

SEND_TEST=1 also sends one email from each mailbox to itself to prove
Mail.Send. Nothing else is written, apart from a draft that is deleted at once.
"""
import os
import re
import subprocess
import sys
import traceback

sys.path.insert(0, os.getcwd())

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
SECRETISH = re.compile(r"(secret|password|passwd|token|api[_-]?key|database_url)", re.IGNORECASE)
PHONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")


def mask(text, limit: int = 300) -> str:
    text = str(text)
    if SECRETISH.search(text):  # never echo a line that mentions a credential, even a fragment of one
        return "<line mentioning a credential: redacted>"
    return PHONE.sub("<phone>", EMAIL.sub("<email>", text))[:limit]


def section(title: str):
    print(f"\n=== {title} ===")


def check(label: str, fn):
    try:
        print(f"[OK]   {label}: {fn()}")
        return True
    except Exception as exc:
        print(f"[FAIL] {label}: {mask(type(exc).__name__ + ': ' + str(exc))}")
        return False


def main() -> int:
    from app.core.config import settings  # also loads backend/.env

    section("Code")
    print("commit:", subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip())

    section("Configuration (set / not set)")
    from app.core.graph_auth import GraphServiceAuth
    print("graph app credentials:", "set" if GraphServiceAuth.is_configured() else "NOT SET")
    print("THUNDER_MAILBOX:", settings.THUNDER_MAILBOX)
    print("FINANCE_MAILBOX:", settings.FINANCE_MAILBOX)
    print("SCHEDULED_JOBS_ENABLED:", settings.SCHEDULED_JOBS_ENABLED or "(empty: no jobs run)")
    print("enrichment: ENRICHMENT_ENABLED", settings.ENRICHMENT_ENABLED,
          "| SEARXNG_URL", "set" if settings.SEARXNG_URL else "not set",
          "| GOOGLE_CSE", "set" if settings.GOOGLE_CSE_API_KEY and settings.GOOGLE_CSE_ID else "not set",
          "| GITHUB_TOKEN", "set" if settings.GITHUB_TOKEN else "not set")
    print("LLM: GEMINI_API_KEY", "set" if os.getenv("GEMINI_API_KEY") else "not set")

    section("Microsoft Graph mailbox permissions")
    from app.services.thunder_mail.graph_mailbox import GraphMailbox
    check("app token", lambda: "acquired" if GraphServiceAuth.get_access_token() else "empty")
    for mailbox in sorted({settings.THUNDER_MAILBOX, settings.FINANCE_MAILBOX}):
        box = GraphMailbox(mailbox)
        check(f"{mailbox} Mail.Read (inbox)", lambda b=box: "{} messages".format(
            b._call("GET", "/mailFolders/inbox", params={"$select": "totalItemCount"}).get("totalItemCount")))

        def readwrite(b=box, m=mailbox):
            draft_id, _, _ = b.create_draft(m, "WROS permission check (auto-deleted)", "<p>check</p>", "status-check")
            b._call("DELETE", f"/messages/{draft_id}")
            return "draft created and deleted"
        check(f"{mailbox} Mail.ReadWrite (draft)", readwrite)

        if os.getenv("SEND_TEST") == "1":
            def send(b=box, m=mailbox):
                draft_id, _, _ = b.create_draft(m, "WROS Mail.Send check", "<p>Production send check. Safe to delete.</p>",
                                                "status-check")
                b.send(draft_id)
                return "sent a test email to itself"
            check(f"{mailbox} Mail.Send", send)
        else:
            print(f"[SKIP] {mailbox} Mail.Send (run with send_test=true to prove it)")

    from sqlalchemy import text
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        def rows(sql, **params):
            db.execute(text("SET search_path TO app_schema, public"))  # a rollback undoes the engine's SET
            return db.execute(text(sql), params).fetchall()

        section("Background jobs (scheduled_job_runs)")
        try:
            jobs = rows("SELECT name, last_status, last_started_at, run_count, consecutive_failures, last_error "
                        "FROM scheduled_job_runs ORDER BY name")
            for r in jobs:
                print(f"{r[0]}: {r[1]} at {r[2]} runs={r[3]} consecutive_failures={r[4]}"
                      + (f" error={mask(r[5])}" if r[5] else ""))
            if not jobs:
                print("no job has run yet")
        except Exception as exc:
            db.rollback()
            print("[FAIL]", mask(exc))

        def table(title, sql, fmt):
            section(title)
            try:
                for r in rows(sql):
                    print(fmt(r))
            except Exception as exc:
                db.rollback()
                print("[FAIL]", mask(exc))

        table("Queue, last 14 days (type / status / count)",
              "SELECT type, status, count(*) FROM channel_queue_item WHERE created_at > now() - interval '14 days' "
              "GROUP BY type, status ORDER BY type, status", lambda r: f"{r[0]:45} {r[1]:12} {r[2]}")
        table("Held as NOT SENT (count / reason)",
              "SELECT left(error, 160), count(*) FROM channel_queue_item WHERE status = 'PENDING' "
              "AND error LIKE 'NOT_SENT:%' GROUP BY 1 ORDER BY 2 DESC LIMIT 10", lambda r: f"{r[1]} {mask(r[0])}")
        table("Recent failures (count / type / error)",
              "SELECT type, left(error, 160), count(*), max(created_at) FROM channel_queue_item WHERE status = 'FAILED' "
              "AND created_at > now() - interval '3 days' GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 12",
              lambda r: f"{r[2]} {r[0]} (last {r[3]:%Y-%m-%d %H:%M}) {mask(r[1])}")

        section("Thunder email")
        for label, sql in (
            ("cadence by stage", "SELECT stage, count(*) FROM thunder_cadence_state GROUP BY 1"),
            ("messages by direction/status", "SELECT direction || ' ' || status, count(*) FROM thunder_email_messages GROUP BY 1"),
            ("variants active", "SELECT 'active', count(*) FROM thunder_outreach_variants WHERE active"),
            ("mailbox poll", "SELECT mailbox, last_run_at::text || ' error=' || coalesce(left(last_error, 120), '-') "
                             "FROM thunder_mailbox_cursor"),
        ):
            try:
                print(label + ":", ", ".join(f"{mask(a)}={b}" for a, b in rows(sql)) or "none")
            except Exception as exc:
                db.rollback()
                print(label + ": [FAIL]", mask(exc))

        section("Enrichment")
        for label, sql in (
            ("profiles by status", "SELECT status, count(*) FROM candidate_intelligence_profiles GROUP BY 1"),
            ("source usage today", "SELECT source, sum(count) FROM enrichment_source_usage WHERE usage_date = current_date GROUP BY 1"),
        ):
            try:
                print(label + ":", ", ".join(f"{a}={b}" for a, b in rows(sql)) or "none")
            except Exception as exc:
                db.rollback()
                print(label + ": [FAIL]", mask(exc))

        section("Revenue chain")
        for label, sql in (
            ("invoices by status", "SELECT status, count(*) FROM invoices GROUP BY 1"),
            ("invoice deliveries", "SELECT channel || ' ' || status, count(*) FROM invoice_deliveries GROUP BY 1"),
            ("revenue rows", "SELECT source, count(*) FROM revenues GROUP BY 1"),
            ("clients with an ACCOUNTS contact", "SELECT 'clients', count(DISTINCT client_id) FROM client_contacts "
                                                 "WHERE role_type = 'ACCOUNTS' AND is_active"),
            ("employees without salary", "SELECT status, count(*) FROM employees WHERE base_salary_usd_cents IS NULL "
                                         "AND status <> 'EXITED' GROUP BY 1"),
            ("cost-rate configs", "SELECT coalesce(business_unit_id::text, 'org default'), count(*) FROM cost_rate_configs GROUP BY 1"),
        ):
            try:
                print(label + ":", ", ".join(f"{a}={b}" for a, b in rows(sql)) or "none")
            except Exception as exc:
                db.rollback()
                print(label + ": [FAIL]", mask(exc))

        section("Roles and authority (role templates; no personal data)")
        try:
            resources = rows("SELECT count(*) FROM resources")[0][0]
            print(f"resources seeded: {resources}")
            for name, display, level, spec, org, enabled, users, granted in rows(
                    "SELECT rt.name, rt.display_name, rt.hierarchy_level, rt.specialization, rt.org_level_access, "
                    "rt.enabled, (SELECT count(*) FROM users u WHERE u.role_template_id = rt.id), "
                    "(SELECT count(*) FROM role_template_permissions p WHERE p.role_template_id = rt.id AND p.can_view) "
                    "FROM role_templates rt ORDER BY rt.hierarchy_level DESC, rt.name"):
                print(f"{name!r} ({display}): level={level} spec={spec} org_level={org} enabled={enabled} "
                      f"users={users} resources_viewable={granted}/{resources}")
            print("users by legacy UserRole:", ", ".join(f"{a}={b}" for a, b in rows(
                'SELECT coalesce("UserRole", \'(none)\'), count(*) FROM users GROUP BY 1 ORDER BY 2 DESC')))
            print("users without a role template:", rows('SELECT count(*) FROM users WHERE role_template_id IS NULL')[0][0])
        except Exception as exc:
            db.rollback()
            print("roles: [FAIL]", mask(exc))

        section("Billing chain links")
        for label, sql in (
            ("active allocations without a project", "SELECT status, count(*) FROM employee_allocations "
                                                     "WHERE project_id IS NULL GROUP BY 1"),
            ("projects", "SELECT status, count(*) FROM projects GROUP BY 1"),
            ("timesheets by status", "SELECT status, count(*) FROM timesheets GROUP BY 1"),
            ("allocation/project client mismatches", "SELECT 'mismatch', count(*) FROM employee_allocations a JOIN projects p "
                                                     "ON p.id = a.project_id WHERE a.client_id <> p.client_id"),
        ):
            try:
                print(label + ":", ", ".join(f"{a}={b}" for a, b in rows(sql)) or "none")
            except Exception as exc:
                db.rollback()
                print(label + ": [FAIL]", mask(exc))
    finally:
        db.close()

    section("Cron")
    try:
        cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        cron = ""
    for name in ("wros-queue-worker", "wros-mail-sync", "wros-scheduled-jobs"):
        print(name, "installed" if name in cron else "MISSING")

    section("Log tails (masked)")
    for log in ("wros-queue-worker.log", "wros-mail-sync.log", "wros-scheduled-jobs.log"):
        path = os.path.join("/home/HRMS", log)
        print(f"--- {log}")
        if os.path.exists(path):
            out = subprocess.run(["tail", "-n", "15", path], capture_output=True, text=True).stdout
            for line in out.splitlines():
                print(mask(line))
        else:
            print("(no log yet)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print(mask(traceback.format_exc(), limit=4000))
        sys.exit(1)
