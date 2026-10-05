# Session Handoff — 2026-10-05

Start a new Claude Code session on `main` and say: "Read HANDOFF.md and continue."
Work directly on `main` (no feature branches); push to `origin main` after checks.

## Production status (hrms.blitzenx.com) — UP since 2026-10-05 ~20:00 UTC

Verified: `https://hrms.blitzenx.com/api/health` → 200, login UI reaches the
backend (validate-email / login), queue worker running, a queued LinkedIn
`create_candidate` completed (`CAN-9dab3d60…`). Not verified: a real user
login (needs a real password; do it in the browser yourself).

### What was wrong and what was fixed (2026-10-05, second session)

| # | Problem | Fix |
|---|---|---|
| 1 | Server was still on `aaaae253`, which crashes on import (`IndentationError` in `secrets_manager.py`) → systemd restart loop → nginx 502 | Shipped `main` to the server as a git bundle over ssh (server has no GitHub credentials) |
| 2 | Startup then died: 25 model columns missing from the prod DB (`role_templates.hierarchy_level` first). `create_all()` never alters existing tables | `db_contract.py` Migration 5 adds them (`3ac04ba6`). Existing users get `password_reset_required=false` (no forced reset) |
| 3 | Every candidate creation failed: `tasks.candidate_id VARCHAR(36)` vs 40-char `CAN-<uuid>`. 676 varchar columns in prod were shorter than the models | Migration 7 `_widen_short_varchar_columns()` — generic, widen-only, idempotent (`71e1ef79`, `9849cd2f`). Model-vs-prod scan now clean except `api_keys_config.created_by/updated_by` (DB varchar on purpose, Migration 1) |
| 4 | Worker left failed messages in `PROCESSING` forever (marked FAILED on an already-broken session) | `db.rollback()` before marking FAILED (`9849cd2f`); the stuck message was re-queued and completed |
| 5 | Frontend live since 09-12 called `http://localhost:8080`; `.env.production` pointed at `api.blitzenx.com` (doesn't resolve publicly) | `REACT_APP_API_URL=https://hrms.blitzenx.com/api` (nginx strips `/api`, backend serves `/api/v1/...`), built and deployed (`1690d5cf`). Previous build kept at `frontend/build-prev-1791230584` |
| 6 | No `wros-queue-worker` unit exists on the server | Cron watchdog in `HRMS`'s crontab: `flock` single instance, restarts within 1 min, survives reboot. Log: `/home/HRMS/wros-queue-worker.log` |
| 7 | Startup printed `DATABASE_URL` with the password (journald) — and the same password is in git history | Logs now mask it (`***`). **DB password rotated** (40 random chars, generated on the server, only in `backend/.env` there). Old password rejected by Postgres |
| 9 | Clicking a LinkedIn task on My Tasks showed "No action configured"; LinkedIn steps never reached the candidate's history | Tasks with a candidate open `/candidates/:id` (notes, History, stage bar); LinkedIn tasks without one open `/linkedin-pipeline`. Each pipeline move/Import writes a History entry with the recruiter's notes; unified creation logs "Candidate Added" again (`f2818123`). Ankurjit Singh's history backfilled |
| 8 | CI `npm ci` failed: lock written by npm 11, runners use npm 10; Node 18 too old | Lock regenerated with npm 10.9 (`b132a4c5`); `test-and-deploy.yml` on Node 22 |

## Deploying

The `HRMS` user has **no usable sudo** (`sudo -l` lists NOPASSWD ALL, but every
`sudo -n` asks for a password) and the server **cannot `git fetch`**. So:

- **Backend:** `backend/scripts/deploy_backend.sh` runs on the server, piped over
  ssh. It fetches a git bundle, `pip install`s, refuses to restart if `import
  app.main` fails, restarts by killing the uvicorn process (unit has
  `Restart=always`), health-checks `/health` for 200, **rolls back** on failure,
  installs the worker cron and restarts the worker. `test-and-deploy.yml` calls
  it. Manual deploy from a dev machine (ssh key in `~/.ssh` works, port 22587):
  ```
  SHA=$(git rev-parse HEAD); SERVER_SHA=$(ssh -p 22587 HRMS@46.224.149.7 "git -C /home/HRMS/WROS-Master rev-parse HEAD")
  git bundle create /tmp/deploy.bundle "$SERVER_SHA..HEAD"
  scp -P 22587 /tmp/deploy.bundle HRMS@46.224.149.7:/tmp/wros-deploy.bundle
  ssh -p 22587 HRMS@46.224.149.7 "bash -s -- /tmp/wros-deploy.bundle $SHA" < backend/scripts/deploy_backend.sh
  ```
- **Frontend:** `deploy.yml` (build in CI, scp to `frontend/build-new`, swap). nginx
  root is `/home/HRMS/WROS-Master/frontend/build/build`. Manual: `npm run build`
  locally, upload to `frontend/build-new/build`, `mv build build-prev-<ts>; mv build-new build`.
- **GitHub Actions has not run a deploy yet:** today's jobs failed with "not
  acquired by Runner" (hosted-runner capacity / billing on the account). The new
  backend deploy path was exercised manually (3 deploys today), not from CI.

### Seen, not fixed

- `GET /documents/candidate/{id}` returns 403 for Admin (Documents tab on the profile).
- History tab's filter list has no "Candidate Added" option (entries still show under "All").

### Server loose ends (need sudo or a decision)

- A proper `wros-queue-worker` systemd unit would be better than cron (needs sudo).
- `wros-queue-worker.log` has no rotation (~1 line / 30 s).
- `frontend/build-old` is owned by another user and can't be removed without sudo;
  `build-prev-*` directories accumulate.
- The old DB password is still in git history, `CLAUDE.md` and several tracked
  `backend/*.py` scripts. It no longer opens prod; it's still the local-dev password.

## Done earlier today (all on main)

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
