# Unfinished workstreams (handoff 2026-10-23)

Uncommitted, UNTESTED work saved when the cloud session closed. None of it is in production.
Each patch applies to the commit named below (the commit it was written against), not to main.

| Patch | Base commit | What it is | State |
|---|---|---|---|
| `ws-a-certifications-intercompany.patch` | `05d2b69d` | Certification records with expiry (create/edit/delete + UI); intercompany entries linked to the company record (FK + backfill); remove the dead `ResourceDemand` table | Written, not run through the gate |
| `ws-b-renewals-margin-floor.patch` | `7e2922ca` | Allocation extend/edit with history; renewal owner/status + 60/30/15-day alert job; Renewals tab; margin policy (rate card) + margin check at placement with BU Head / Partner approval below the floor | Mid-build (Employees screen not finished) |
| `ws-c-client-approval-po-invoices.patch` | `d47be39b` (before #413) | Per-client client timesheet approval (signed email link or uploaded VMS evidence); work orders + PO on invoices; sequential invoice numbers per issuing company; AR by payment terms + aging tab | Mid-build; needs main merged in (timesheet_approval_service changed in #413) |

Apply one:

    git checkout -b feat/ws-b <base-commit>
    git apply --index wip/ws-b-renewals-margin-floor.patch
    git merge origin/main        # resolve conflicts
    # finish, test, commit through the gate (never --no-verify)

Spec for all three: `wip/SPEC.md`.
