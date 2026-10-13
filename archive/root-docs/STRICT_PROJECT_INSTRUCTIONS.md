# WROS — Strict Project Instructions

These are binding for every Claude Code session on this repository, every phase, every story. Where this document and a specific story's requirements doc disagree on a rule of engagement (not on business logic — the story doc always wins on business logic), this document governs.

---

## 1. Never build ahead of the acceptance gate

Every phase document (`01` through `04`) ends with an acceptance gate — a checklist that must fully pass before the next phase starts. Do not begin Phase 2 work because Phase 1 "looks done." Run the gate's actual tests. If a gate item fails, fix it before proceeding, even if the failure seems unrelated to what you're currently building. A failing tenant-isolation test discovered while building Phase 3 still means Phase 1 isn't actually done.

## 2. Never reimplement a function that already exists

Before writing send logic, creation logic, notification logic, or Core-Pull decision logic, search the codebase for `sendThunderMessage`, `createCandidateSafe`, `sendNotification`, and any Core-Pull-related function respectively. If any of these exist, call them. If you believe none of them adequately covers your case, stop and say so explicitly rather than writing a parallel implementation — this project has already been burned once by the same capability (LinkedIn sourcing) being independently built three separate times before anyone noticed.

## 3. Every hard-rule story gets a negative-case test, written before the code

Per the Development & Review Standard's Part 3 template: for any story touching R-01 through R-11, write the test that attempts the violation (wrong experience level, wrong interview sequence, bill rate below floor, unapproved timesheet, etc.) via direct API call, bypassing any UI constraint — before writing the implementation. The test defines done. A story is not complete when its happy-path demo works; it's complete when its negative-case test passes.

## 4. No credential, API key, or secret in code, config committed to the repo, or logs

This includes error logs — Phase 1's logging framework must redact known secret patterns before writing. If you're integrating a new external service (a new job board, a new payroll provider) and need a credential, use the secrets manager pattern already established for every other integration in this backlog. Do not hardcode a value "temporarily" to unblock testing.

## 5. Treat all LLM-facing user content as data, never as instructions

Any story that assembles an LLM prompt from candidate resumes, RFP documents, or any other user-supplied text must be built with the assumption that content could contain an embedded instruction trying to manipulate the model's output. See Phase 1, Section B5, for the specific test pattern. This applies to every future LLM-calling story built in this platform, not just the ones that existed when this rule was written.

## 6. Currency, always

`BIGINT`, USD cents, field name ends in `_usd_cents`. If you find yourself adding a column to store a value in a native currency for "just this one display purpose," stop — that's what `convertFromUSD()` (HRMS-0121) is for. There is no second acceptable pattern.

## 7. Ask before assuming on anything hard-rule-adjacent

If a story's requirements doc is genuinely silent on a scenario that touches R-01 through R-11, tenant isolation, or Core-Pull, do not infer a reasonable-sounding answer and proceed. Flag it. These are the eleven things in this codebase where a wrong guess is expensive to discover later — everywhere else, use your judgment and note the assumption.

## 8. Financial calculations are exact arithmetic, not approximations

EPIC-16's cost/rate engines (Fully Loaded Cost, RM Burden, Min Bill Rate, the P&L Engine, Reserve Fund) implement locked formulas from the BlitzenX Operating Model reference document. These are not "close enough" targets — a calculation engine's acceptance criteria includes reproducing the reference document's own worked examples exactly. If your implementation produces a different number than the worked example, the implementation is wrong, not the example.

## 9. Placeholder constants stay visibly flagged until confirmed

Several financial constants (India/US billable-hours basis, 401k match %, Min Bill Rate multiplier) are pending Avinash's confirmation. Build against them as configurable values with a visible placeholder indicator in any UI that displays a figure depending on them — per HRMS-1608 and HRMS-1610's explicit requirement. Do not silently treat a placeholder as final, and do not block building the engine itself waiting for the real number — the engine is buildable now, the constant is what's pending.

## 10. GST/Statutory compliance is UAT-gated, not build-and-ship

Anything under the GST/Statutory Compliance placeholder gets built to a first-pass structure but does not go to production until BlitzenX's Finance team and CA have completed UAT against it. Do not treat "the code runs and produces a plausible-looking GSTR-3B" as done for this specific area — tax and statutory filing correctness is not something to self-certify.

## 11. Manual stays manual

Bank reconciliation (manual PDF/Excel upload), intercompany settlement (manual entry, never auto-calculated from NPBR), and invoice mark-as-paid (manual action, never inferred from any integration) are deliberately, permanently manual per direct instruction. Do not "improve" these into automated flows without explicit sign-off — the manual step is the control, not a temporary limitation waiting to be optimized away.

## 12. When in doubt about story numbering

Story numbers (S-xxx) and WROS IDs (HRMS-xxxx) are for cross-referencing requirements docs and for grep-ability in commit messages — they carry no build-priority meaning. Do not infer that S-230 must be built before S-390 because of the numbers; check the `dependsOn` field in the actual story doc.
