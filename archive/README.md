# Archive (2026-10-13)

Everything here was moved out of the working tree because it is **historical**. That covers session summaries, "COMPLETE / PRODUCTION READY" reports, iteration certifications, plans that were already executed, one-off fixer/seed scripts, and test-result dumps. Nothing here is imported by the app, CI, the git hooks or the deploy scripts; that was checked before moving.

Many of these documents contradict each other and the current code. Do **not** treat anything here as current status. Current state lives in:

- `../OPEN_ITEMS.md`: verified open defects, decisions and GitHub-issue triage
- `../docs/OPEN_REQUIREMENTS_BACKLOG.md`: open backlog stories (S-001..S-401)
- `../HANDOFF.md`: production and deploy procedure
- `../CLAUDE.md`: working rules

| Folder | Contents |
|---|---|
| `root-docs/` | ~320 markdown/text status docs from the repo root |
| `root-scripts/` | one-off Python/PowerShell/SQL scripts, JSON test dumps, dashboards and the duplicate offer-letter template from the repo root (the app loads `backend/templates/`) |
| `backend-docs/` | ~160 docs from `backend/`, many duplicating root docs |
| `backend-scripts/` | one-off DB check/drop/verify scripts and SQL dumps from `backend/` |
| `backend-docs-duplicates/` | byte-identical copies of `docs/` that lived in `backend/docs/` |
| `frontend-docs/` | TODO/status docs from `frontend/` |
| `post-go-live-fixes/` | 2026-09-17 hardcoding audit; still-true findings are in `OPEN_ITEMS.md` (P1-5) |
| `scratchpad-reports/` | old audit reports |

Restore any file with `git mv archive/<folder>/<file> <original path>`. History is preserved because the files were moved with `git mv`.

Not archived but **untracked** (still on disk, now gitignored): `local_dev.sqlite3*`, `dump.rdb`, `deploy.bundle`, `*.pid`, `backend/nohup.out`.
