# EPIC-16: Finance & Accounting Operations

**Builds in parallel with Phase 3/4 once Phase 1 (Security) and Phase 2 (Data Model) both pass.** Depends on Payroll Sync (Integration Hub) and the Notification Engine (Phase 1) — does not depend on Thunder or Resource Management, so there's no reason to wait for either.

Source of truth for every formula in this epic: BlitzenX's Operating Model reference document (locked, v1.0). Where any other document in this project states a financial formula differently, this epic's story docs are authoritative — they were built directly from that reference and cross-checked against its worked examples.

---

## Build order within this epic

```
S-393 (HRMS-1608) Fully Loaded Cost Engine
S-394 (HRMS-1609) RM Burden Allocation Engine        } build in this order —
S-395 (HRMS-1610) Minimum Bill Rate Engine           } each depends on the last
              ↓
S-396 (HRMS-1607) BXIN/BXUS Separate P&L Engine
              ↓
S-397 (HRMS-1612) Reserve Fund Engine
S-398 (HRMS-1613) Hiring Affordability Gate Engine   } both read the P&L Engine's output
              ↓
S-387 (HRMS-1601) Timesheet Nag Agent
S-388 (HRMS-1602) Monthly Invoice Generation Cycle
S-389 (HRMS-1603) Manual Invoice Mark-as-Paid         } the operational chain,
S-390 (HRMS-1604) AR Follow-Up Agent                  } can build alongside the
S-391 (HRMS-1605) Bank Reconciliation                 } cost/P&L engines above
S-392 (HRMS-1606) Intercompany Settlement Ledger
              ↓
S-399 (HRMS-1611) Partner Incentive Calculator   (depends on S-389 + S-396)
              ↓
S-400 (HRMS-1614) Executive Finance Dashboard    (depends on everything above — build last)

S-401 (HRMS-1615) GST & Statutory Compliance     (BLOCKED — separate track, do not start
                                                   without Finance/CA requirements sign-off)
```

---

## The one thing to get right before writing any code in this epic

**Four numeric constants are placeholders, not final values**, per the reference document's own open-questions section: India billable-hours basis (1,920 vs. 1,680), US billable-hours basis (1,760 vs. 1,848), US 401k match %, and the Min Bill Rate multiplier (1.25 vs. 1.19). Build every engine that uses these as configurable values read from `system_config`, with a visible placeholder indicator in any UI that displays a dependent figure — per S-393 and S-395's explicit requirement. Do not hardcode a guess. Do not block building the engines waiting for the real numbers — the calculation logic is fully specified and buildable now, only the constants are pending.

## The second thing to get right

**"Paid" means manually marked paid (S-389), never inferred.** This governs S-399's entire incentive-calculation trigger and is a deliberate simplification matching how BlitzenX's Tally-based process works today — do not build any automatic payment-detection logic anywhere in this epic, including in S-391's bank reconciliation (which matches transactions for human confirmation, but never auto-marks an invoice paid based on a bank match).

## S-401 is not like the other 14 stories in this epic

Every other story here is buildable end-to-end from its requirements doc. S-401 (GST/Statutory Compliance) is explicitly a structural placeholder — its status is `BLOCKED` in the canonical backlog for a reason. Do not treat a working demo of S-401 as equivalent to a working demo of any other story in this epic; it requires a sign-off step (Finance + CA review) that no other story in this backlog requires, because it's the one place in this entire project where correctness isn't something Claude Code or Claude generally can self-certify.

## Correction already applied, relevant to this epic

HRMS-0113 (Notification Engine, Phase 1) was amended with BR-0113-03 — non-emergency notifications now respect the recipient's local business hours automatically. This directly affects S-387 (Timesheet Nag Agent) and S-390 (AR Follow-Up Agent), both of which send notifications across a workforce spanning multiple timezones. Neither story needed its own timezone logic added — both inherit the fix from HRMS-0113 by virtue of calling `sendNotification()` rather than implementing a direct channel send. See `06-CORRECTION-TIMEZONE-BUSINESS-HOURS.md` for the full detail.
