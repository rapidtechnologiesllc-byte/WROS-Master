# Holding company and companies across the whole system: design for approval

**Date:** 2026-10-14 · **Status:** design only. Part 1 is already live; Part 2 waits for your approval.

## The model (as you described it)

- **BlitzenX is the holding company, and it is the tenant (ID `1`).** It owns the consolidated, org-wide view: P&L, revenue, headcount, recruitment.
- **BX-US (`1-1`), BX-IN (`1-2`), BX-Canada (`1-3`) are separate registered companies.** Each has its own books and reports to BlitzenX.
- **Business units** (AXION, PRISM …) cut across companies. A BU can run in more than one company.
- **Functions** (Recruitment, HR, Finance …) are what people belong to and what work routes to.

## Part 1: live now (430b672a)

| Item | Status |
|---|---|
| Company IDs `<tenant>-<n>`, assigned once and never reused; BlitzenX = `1` | Live: BX-US `1-1`, BX-IN `1-2` |
| Every company reports to the holding company; a parent company is optional | Live |
| Company P&L under the org P&L (P&L screen → "By company") | Live; uses the data that already exists (below) |
| Tenant never assumed or hard-coded; sub-companies take the tenant of their holding company | Live |

How company P&L is attributed today:
- **Revenue:** earned on the clients the company contracts (`Client.contracting_company_id`).
- **Cost:** the people it employs (`Employee.company_id`): their delivery hours plus bench time, wherever they work.
- **Intercompany:** entries in the intercompany ledger count as revenue for the receiving company and cost for the paying one. At BlitzenX level they cancel out, so consolidated = sum of companies − intercompany.
- **Anything not attributed:** stays at holding level, shown as "Group".

## Part 2: the company across every module (proposal)

**Principle: derive the company, never re-key it.** Each record gets its company from what it already references, so nobody picks a company twice and nothing can disagree.

| Module | Record | Company comes from | Today | Change |
|---|---|---|---|---|
| Workforce | Employee | employer (set at hire/conversion) | ✅ `Employee.company_id` | Make it required at conversion. Headcount by company. |
| Workforce | Org seat | the employee's company | ✅ `OrgNode.company_id` | None |
| Sales | Client | contracting company (who signs and bills) | ✅ `contracting_company_id` | Required on new clients |
| Sales | Opportunity | client's contracting company | ❌ | Derived; pipeline by company |
| Recruitment | Job / requisition | hiring company: the client's contracting company, else the BU's company in the job's location | ❌ | Add `hiring_company_id` (derived, overridable). Recruitment dashboards by company. |
| Recruitment | Offer letter | the job's hiring company (legal employer on the offer) | ❌ | Derived; offer template per company (letterhead, entity name, currency) |
| Recruitment | Candidate | none until hired (the hire sets `Employee.company_id` from the offer) | n/a | None |
| Timesheets | Timesheet entry | the employee's company (cost side) and the client's contracting company (revenue side) | derived | None in data; timesheet reports by company |
| Finance | Invoice | the client's contracting company (the issuing entity) | ❌ | Add `issuing_company_id`; invoice number series and letterhead per company |
| Finance | Expense | the logger's employer; a client expense also carries the client's company | partly | Derived |
| Finance | **Intercompany charge** | automatic: when an employee of company A works for a client of company B, A charges B monthly at cost plus a markup | manual ledger only | **New monthly job** writes ledger entries, so company P&Ls are complete without manual entry |
| Executive | Dashboards | every KPI shows BlitzenX (consolidated) with a by-company breakdown | BU/partner only | Add a company filter |
| Access | Scope | unchanged: people see their business units across companies; holding-level roles see everything | ✅ | None |

## Impact and risk

- **Schema:** additive only: `jobs.hiring_company_id`, `offer_letters.issuing_company_id`, `invoices.issuing_company_id`, `opportunities.company_id`. All nullable and backfilled from the derivation rules; nothing removed.
- **Writers to change:** job create/edit, offer generation, invoice generation (auto-invoicing job included), conversion, client create. Each gets one call to a shared resolver, `company_for(record)`, rather than its own logic.
- **Readers to change:** P&L (already done), revenue and forecasting, recruitment dashboards, headcount, executive dashboards.
- **Highest-risk change:** the invoice issuing company and its number series, because it is outward-facing to clients. Gate it behind a parity check: existing invoices keep their numbers, and only new invoices use the per-company series.
- **Tests:** an end-to-end chain test for each company covering candidate → offer (BX-IN) → employee → allocation on a BX-US client → timesheet → invoice issued by BX-US → intercompany charge BX-IN → BX-US → both company P&Ls plus the BlitzenX consolidation, where intercompany nets to zero.

## Decisions needed from you

1. **Intercompany pricing:** cost plus what markup? Typical cost-plus is 8–15%; I'd propose a per-company-pair setting, starting at 10%.
2. **Who issues invoices to a US client served by Indian staff?** I recommend BX-US (the contracting company), with BX-IN charging BX-US intercompany.
3. **BX-Canada:** create it now as `1-3`? Its currency: today every amount is USD. Canada (CAD) and India (INR) books would need multi-currency, which would be a separate phase.
4. **Offer letters and invoices per company:** each company gets its own letterhead, legal name and number series? I recommend yes.

Once you answer these, Part 2 can be built in the order listed above, with the end-to-end chain test as the gate.
