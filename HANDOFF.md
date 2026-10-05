# Session Handoff — 2026-10-05

Start a new Claude Code session on `main` and say: "Read HANDOFF.md and continue."
Work directly on `main` (no feature branches); push to `origin main` after checks.

## Production status (hrms.blitzenx.com)

- **Backend is DOWN.** Every `/api/*` request returns `502 Bad Gateway` from nginx.
  The frontend loads, but nginx can't reach the backend process. Cause not visible
  from outside. On the server:
  ```
  sudo systemctl status wros-backend
  sudo journalctl -u wros-backend -n 200 --no-pager
  sudo systemctl status wros-queue-worker
  ```
  If it fails at startup, the log will name it. The LinkedIn startup backfill
  can no longer block startup (fixed in 5f3067ed).

## CI/CD — deploy to prod (fixed in this session, verify first run)

The deploy pipeline never actually deployed (at least since 2026-09-23):

| Workflow | Problem | Fix |
|---|---|---|
| `test-and-deploy.yml` (the real SSH deploy) | Change detection diffed `origin/main...HEAD`, always empty on a push to main, so it skipped every deploy and reported success | Diff `github.event.before..HEAD`; deploy unless a test job failed (skipped test jobs no longer block) |
| `test-and-deploy.yml` backend step | Ran `alembic upgrade head` (Alembic isn't used; schema is created by `db_contract.initialize_database()` at startup), so the step failed before the restart | Install into `/home/HRMS/WROS-Master/venv`, `systemctl restart wros-backend` and `wros-queue-worker`; health check prints `journalctl` on failure |
| `test-and-deploy.yml` frontend step | Rebuilt on the server against `http://46.224.149.7:8080` (plain-http IP, so the browser blocks it on https) and overwrote the CI build | Removed; the frontend is deployed only by `deploy.yml` |
| `deploy.yml` (frontend) | `npm ci` failed: `package-lock.json` had typescript 7.0.2, `package.json` wants 4.9.5 | Lock regenerated (`npm install --package-lock-only`); `npm ci --dry-run` passes |
| `deploy-backend.yml` | Invalid file (top-level `outputs:`), plus Celery steps (no Celery in repo) | Fixed; it validates/simulates only — it does **not** deploy |

**Next:** watch the Actions run for this push. Required secrets: `PROD_SSH_KEY`,
`PROD_SERVER_HOST`, `PROD_USER`. The SSH user needs passwordless `sudo systemctl
restart wros-backend wros-queue-worker` and `journalctl`. If the SSH deploy fails,
the log shows which step.

## Done today (all on main)

- Client/BU fields use real dropdowns; Account Manager comes from users (`clients.account_manager_user_id`); Client Owner removed.
- Job approval flow commented out: every new job is `active` (create_job, Flash chat, queue handler). Status can't be edited directly.
- Job Details section save fixed; job update/approve/delete queue-id collisions fixed.
- LinkedIn pipeline: uuid→varchar columns; JSON status updates, forward-only (Pending → Connected → Phone Collected → Import); per-stage follow-up tasks on My Tasks; candidate created at queue time (Thunder OFF until Import, placeholder email `@linkedin-pending.blitzenx.com`); dedup by profile slug + existing candidates; dashboard per user; permissions + ownership checks.
- Thunder activity feed: tenant scoping fixed, `ConversationEvent.tenant_id` inherited from its conversation, read state per user, Thunder loop respects `thunder_enabled`.

## Open decisions / next work

1. **Thunder engagement is not running and the current loop must not be turned on.**
   `run_thunder_autonomous_cycle` sends nothing, rolls back every cycle, and its
   "Phase 3B" would auto-create interviews/offers/employees. Do **not** call
   `start_scheduler()` (≈45 jobs; in development it auto-commits to git every
   90s). Recommended: a new `run_first_engagement_sweep` in `start_worker.py`
   behind `THUNDER_ENGAGEMENT_ENABLED` (default false) with a real kill switch,
   a created-after cutoff, and `send_thunder_message` (WhatsApp → email
   fallback). Delete Phase 3B. Needs the user's decision on the cutoff.
2. **Email:** `backend/.env` `AZURE_TENANT_ID/CLIENT_ID/CLIENT_SECRET` are
   placeholders, so nothing has ever been sent. Needs an Entra app with
   application `Mail.Send` (admin consent) and a real `helpdesk_hrms@blitzenx.com`
   mailbox (sender is hardcoded in `email_service.py`). The user sets these;
   locally use a stub/allowlist so real candidates aren't emailed.
3. **Review findings still open (MEDIUM):** Import can overwrite a pre-existing
   candidate's phone and turn Thunder back on; placeholder-email collisions
   between similar slugs; activity-feed unread count loads all events;
   `task_service.create_task` commits internally.
4. 4 jobs are stuck in `pending_approval` (created before approval was disabled);
   the user hasn't decided whether to activate them.

## Local dev notes

- Backend: `cd backend && python -m uvicorn app.main:app --reload --port 8080`;
  queue worker: `cd backend && python start_worker.py` (needed for candidate creation).
- Run git from the repo root (`backend/` contains a stale nested `.git`).
- Regression baseline: `13 failed, 25 passed, 1 xfailed, 2 errors` (pre-existing);
  many unit tests error on a SQLite fixture (`unknown database app_schema`).
