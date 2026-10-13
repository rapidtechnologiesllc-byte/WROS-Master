# Correction: Business-Hours-Aware Notification Delivery

**Applies to:** HRMS-0113 (Notification Engine Base, S-211 — already built in Core Platform) and S-387 (Timesheet Submission Nag Agent). This is a platform-wide fix, not a single-story patch, because the whole point of HRMS-0113 existing is that every other agent inherits its behavior instead of reimplementing send logic — so the fix belongs there, once, not scattered across every story that sends a notification.

---

## The gap

S-387's cascade only made Step 3 explicitly timezone-aware (the "Monday + 4 hours in the employee's local timezone" step). Steps 1, 2, 4, 5, 6, and 7 are date-triggered ("Friday," "Monday," "Tuesday"...) with no business-hours constraint on *when within that day* the send actually fires. If the underlying scheduled job runs at one fixed UTC time, an employee on the US West Coast could receive a WhatsApp escalation at 4am their time while it's a perfectly reasonable business hour for someone in India or on the East Coast. Same exposure applies to any other agent sending a notification — the AR Follow-Up Agent (S-390) reminding a client at an unreasonable hour, or any future agent built on this platform.

## The fix — amend HRMS-0113, not each individual agent

**New rule for HRMS-0113 (add to its existing Business Rules):**

> **BR-0113-03 — Non-P0 notifications respect the recipient's local business hours, per HRMS-0121's timezone configuration.**
> A P1 or P2 priority notification scheduled to fire on a given calendar day does not send at the literal moment the trigger condition is met — it queues and releases at the next point the recipient's local time falls within a configured business-hours window (default 08:00–20:00, matching the window already established in HRMS-1104's Outreach Agent for candidate messaging). P0 (immediate/emergency) notifications are the sole exception and continue to fire immediately regardless of local time, since a P0 by definition represents something urgent enough that the delay itself would be the bigger problem.

This means every story that already calls `sendNotification()` — which is every notification-sending story in this backlog — inherits correct business-hours behavior automatically, without needing an individual retrofit. That's the whole reason HRMS-0113 was built as one shared dispatch point instead of letting each agent implement its own send logic.

**Data model addition (Phase 2, Domain 1):**
```
notifications.scheduled_release_at  — nullable timestamp; if set, the notification is queued and
                                       held until this time (computed as the next business-hours
                                       window in the recipient's timezone) rather than sent immediately
```

## The fix — amend S-387 specifically

With HRMS-0113 fixed, S-387's own change is small: **every step in the cascade (not just Step 3) is now correctly business-hours-gated automatically**, because every step already sends through HRMS-0113 rather than a direct channel call. The one thing worth being explicit about in S-387 itself:

**Amend BR-1601-02** (previously scoped only to Step 3) to read:

> **BR-1601-02 — Every step in the cascade respects the recipient's local business hours, not just Step 3.**
> Steps 1, 2, 4 (employee-facing) and Steps 5, 6, 7 (manager-chain-facing) all inherit HRMS-0113's business-hours gating (BR-0113-03) rather than firing at the literal moment their day-based trigger condition is met. A recipient in a different timezone than whoever the cascade's reference day was computed against will still see each step land at a reasonable local hour, not a raw UTC-triggered one.
> **One nuance worth calling out:** the cascade's own day-to-day progression (Friday → Monday → Tuesday → Wednesday → Thursday) is still measured in the *employee's* timezone throughout, including for Steps 5-7 even though those notify someone else (the manager, the manager's manager, the BU Head) — the cascade doesn't reset or re-time itself to the manager's timezone at Step 5, it simply continues on the same clock, with each individual notification's *delivery hour* (not which day it falls on) respecting whichever recipient is actually receiving that specific step.

## Why this is the better fix than patching every story individually

If this fix lived only in S-387, the next agent built after it — the AR Follow-Up Agent, the Auto-Scheduler, anything Claude Code builds later that needs to notify someone — would need the same fix rediscovered and reapplied by hand. Putting it in HRMS-0113 means it's structurally impossible to forget, the same reasoning already used throughout this backlog for why `sendThunderMessage()` is the only send path for candidate messages and `createCandidateSafe()` is the only creation path for candidates. One shared correct implementation beats N individually-remembered ones.

## Action needed on already-generated documents

`S-211_HRMS-0113.docx` (already generated, Batch 1) and `S-387_HRMS-1601.docx` (just generated, this session) both need their Business Rules sections amended per this addendum before Claude Code builds against them. I can regenerate both documents now with this correction folded in — let me know and I'll do that immediately rather than leaving this as a separate addendum someone has to remember to cross-reference.
