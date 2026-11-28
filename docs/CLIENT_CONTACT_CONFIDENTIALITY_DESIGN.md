# Client contact confidentiality

**Status:** DESIGN v3, ready to build. Ruthless Architect: review #1 BLOCK, review #2 APPROVE WITH CHANGES (2026-11-28),
all applied (section 7). CEO answered Q1-Q4 on 2026-11-28 (section 4).

## 1. The rule (CEO 2026-11-27, 2026-11-28)
> "Client POC details should only be visible to partner and above and the assigned account manager for that account.
> All other communication via HRMS to the client POC should be filtered and require either partner or account manager
> approval."

- **Who sees a client's contacts and may write to them freely (privileged for that client):** the client's account
  manager, its client owner (CEO Q2), a Partner for clients in business units they partner (CEO Q3), and the CEO for
  every client. Partner = `authority.is_partner` AND the client's BU is in `bu_leadership.partnered_business_units`
  (`business_units.partner_user_id`), never `led_business_units` (that includes BU heads). CEO = `authority.is_ceo`
  (level 17). Org-wide visibility (`is_org_level`) does **not** grant it: that flag is for candidate scoping and some
  non-Partner roles carry it. A client with no business unit: account manager, client owner and CEO only.
- **Everyone else** sees a contact's name, title and role type; the email is masked (`j***@acme.com`), and phone and
  LinkedIn are hidden.
- **Reaching a client contact** by email, calendar invite or Teams meeting, WhatsApp or SMS, sent by someone not
  privileged for that client, is **held** until a privileged person approves it.
- **Financial messages** (invoices, payment reminders, statements) need an approval for **every message**, from anyone
  but a privileged sender. Other system messages (timesheet approval links, interview invites to client interviewers)
  need a **one-time standing approval per contact and purpose** (CEO Q1).
- **Any address at a client's domain counts as a client contact,** saved or not (CEO Q4). A client's domains come only from
  `Client.website` and a new `client_domains` table (added by the account manager), **never** from contact addresses.
  Generic mail domains (gmail, outlook, yahoo, ...: the `GENERIC_DOMAINS` list moved from `vendor_invoice_intake.py:39`
  to core and shared) are never client domains. Our own domains (`tenant_mail_domains` table, seeded from the domains
  of the tenant's users and its HRMS mailbox) never count either.

## 2. Leak surfaces (architect C1, C4)
Each one goes through `present()` (3.1). The sentinel test (5) proves it.

| Surface | Today | Change |
|---|---|---|
| Client contacts list / detail | `clients.py:300-330` | `present` |
| Client email log (from, to, cc, 2000-char snippet) | `clients.py:456-511` | mask from/to/cc, drop the snippet unless privileged |
| `client_email_log_service.match_clients` | no tenant filter, matches the website domain | filter by the mailbox's tenant (the poll has no caller); unknown tenant -> every tenant |
| Allocation `timesheet_approver_email` | `allocations.py:201` | `present` |
| Timesheet `client_approver_email` | timesheet.py:80 | `present` |
| Work order `invoicing_contact_email` (free text) | `work_orders.py:73` | `present` (treated as a contact address) |
| Invoice delivery `to_address` | `invoices.py:101` | `present` |
| Queue payloads, message deliveries | `message_queue.py:83` (not tenant-scoped) | mask recipients in responses; tenant filter |
| Calendar reads (attendees of any user's calendar) | `msgraph.py:393-399, 504-510` | mask attendee addresses |
| Flash / Thunder LLM context builders | none read contacts today | any that does goes through `present` |
| Held-message and queue screens | show recipients | `present` output only |
| Errors that echo addresses | `client_timesheet_approval_service.py:127-133`, `client_service.py:181` (reveals that an address is a contact) | no addresses in error text |
| Logs | `email.py:122` logs the recipient | recipient masked in logs |

**Pickers choose by `contact_id`** (architect C5): `AllocationForm.js:273` and `AllocationEditModal.js:256` send the
contact's id, and the server resolves the address. A non-privileged person can pick a contact without ever seeing its
address.

## 3. Design

### 3.1 Visibility
`client_contact_access`:
- `privileged(db, user, client) -> bool`
  - `client.account_manager_user_id == user`
  - or `client.client_owner_user_id == user`
  - or the account manager resolved through `account_manager_employee_id -> employees.wros_user_id` (legacy, H1)
  - or `is_org_level(user)`
  - or `is_partner(user)` and the client's BU is one the user partners
- `present(db, user, contact or address, client) -> dict`: the full value when privileged, otherwise masked.

### 3.2 Outbound: two chokepoints (architect C3)
**(a) Request time.** Where the person acting is known (an endpoint, an action, a Flash or Thunder step):
- `guard.decide(db, actor, recipients, channel, purpose, entity)` resolves every recipient: to, cc, bcc, calendar
  attendees, and phone numbers normalized to E.164 at match time, defaulting the country from `Client.country` through
  the existing country-name mapping (`employment_type_policy.country_code`); a number that can't be parsed is treated
  as a client contact (M1).
- A recipient is a **client contact** when it is a saved contact's address or phone, **or** its domain is a client's
  domain. Clients and contacts are matched through `clients.tenant_id`. When the tenant is unknown, every tenant is
  matched, failing closed (H2).
- Outcome:
  - **SEND** when there's no client recipient, or the actor is privileged for every contacted client, or (for a
    non-financial purpose) a standing approval covers every contact and the purpose.
  - Otherwise **HOLD**.
- The decision id travels with the queued work (queue payload `client_contact_decision_id`).

**(b) Egress.** One module, `outbound_transport`, is the only code allowed to call:
- Graph `sendMail`, `/messages/{id}/send`, `createReply`, `/forward`, and `/events` create, update (PATCH that adds
  attendees) and **DELETE/cancel** (Exchange emails a cancellation to every attendee: `cancel_interview_event`,
  `email_service.py:680-693`)
- newsletter `/me/sendMail`, `email_delivery` and the Twilio/SendGrid/stub providers, WhatsApp

Before sending, it resolves the **final** recipients (for a draft, by reading the draft back) and matches them again.
It refuses unless a SEND or APPROVED decision id is attached that covers exactly those recipients. A queue retry or a
re-run handler carries the same decision id, so nothing is sent around it.

**Proof that nothing bypasses it:**
- **Static test:** fails if any string literal or f-string outside `outbound_transport` contains `sendMail`, `/send`,
  `createReply`, `/forward` or `/events` (relative paths too, e.g. `_make_graph_request("POST", "/me/sendMail")`,
  `msgraph.py:297`), or calls a provider client.
- **Runtime sentinel test:** seeds a contact with a sentinel address and phone, patches `requests`, `httpx`, Twilio
  and Graph, and drives every send flow as a non-privileged user. It fails if the sentinel leaves without a decision
  id.

### 3.3 Holding and approving (architect H3-H6)
| Table | Purpose |
|---|---|
| `client_contact_held_messages` | `tenant_id`, `requested_by`, `channel`, `purpose`, `entity_type` / `entity_id`, recipients, attachment references, `status` (PENDING / RELEASED / REJECTED / EXPIRED), `expires_at`. It stores the **intent** (purpose, entity, recipients), never a rendered message holding a live credential such as a timesheet approval link. |
| `client_contact_decisions` | One row per (held message, client): `client_id`, approver, decision, reason, `decided_at`. The message is released only when every client involved is approved: all or nothing (H4). |
| `client_contact_standing_approvals` | `tenant_id`, `client_id`, `contact_id`, `purpose`, approved_by/at, `revoked_at`. Revoked automatically when the contact's email or phone changes. It survives an account-manager change; the new account manager can revoke it (H5). |

- **Approver:** the account manager, else the client owner, else the BU's partner (`business_units.partner_user_id` of
  the client's BU), else the CEO; a client with no BU goes from the client owner straight to the CEO. One task, a real
  decision. Escalation to the next in the chain is by the SLA only (HRMS has no on-leave data).
- **On release:** the message is **re-rendered**, and the business preconditions are checked again. An invoice must
  still be approved and not voided; a timesheet link is issued fresh at release. It is then sent through
  `outbound_transport`. Every decision is written to `ClientHistory`.
- **SLA:** 1 business day, then escalate to the next approver. After 5 days the message is EXPIRED and the requester
  is told. A scheduled job, `client_contact_hold_sweep`, runs every 30 minutes and is added to production's job list.
- **Flash and Thunder** never write to a client contact on their own. Their messages always HOLD unless a standing
  approval covers the purpose; financial purposes never have standing approvals. In the Phalanx, Flash escalates a
  held message past its SLA.

### 3.4 Decisions taken by default (architect's "missed" list; the CEO can change any)
1. **Partner scope:** own business units' clients (CEO Q3, answered).
2. **Unsaved addresses at a client domain:** count (CEO Q4, answered).
3. **Client interviewers on interview invites:** purpose `INTERVIEW`, one standing approval per contact.
4. **Newsletter subscribers who are also client contacts:** excluded from newsletters unless a standing approval for
   purpose `NEWSLETTER` exists.
5. **Backup approver:** the chain in 3.3, by SLA.
6. **An address that is both a candidate and a client contact:** treated as a client contact (stricter wins).
7. **Mail staff send from their own Outlook,** outside HRMS: HRMS can't hold it. When it appears in the client email
   log it is shown masked to non-privileged users.

## 4. Questions answered (CEO 2026-11-28)
- **Q1:** hybrid. **Financial** messages (invoice, pending payment) need approval for every message; others need one
  standing approval per contact and purpose.
- **Q2:** account manager **and** client owner are privileged.
- **Q3:** Partners see their own BUs' clients.
- **Q4:** any address at a client's domain counts.

## 5. Tests
- **Static egress scan:** no send call outside `outbound_transport`.
- **Runtime sentinel, sending:** the sentinel never leaves without a decision.
- **Runtime sentinel, reading:** every GET route, called as a non-privileged user, never returns the sentinel. This
  replaces the schema-field test, which can't see the copies in section 2 (M3).
- **Parity:** every send flow still sends for an account manager, a client owner, a Partner of the BU, and the CEO.
- **Approval flow:**
  - financial messages need every approval, and standing approvals don't apply to them
  - release re-renders and re-checks the preconditions
  - all-or-nothing across clients; expiry; escalation

## 6. Delivery
1. `client_contact_access` + `present` on every surface in section 2 + pickers by `contact_id` + error and log
   scrubbing + the reading sentinel test. **Visibility ships first.**
2. `outbound_transport` (every send moved into it) + `guard.decide` + held messages, decisions, standing approvals,
   the approval task and screen, the hold sweep job + static and sending sentinel tests.

Each step: architect review, full suite in the gate, browser check, release `master` -> `main`.

## 7. Review #2 changes applied
| Finding | Where |
|---|---|
| 1 privilege: CEO (`is_ceo`), not org-level roles | 1, 3.1 |
| 2 client domains only from website + `client_domains`; generic and own domains excluded | 1 |
| 3 event DELETE / PATCH guarded; static scan catches relative paths and f-strings | 3.2(b) |
| 4 escalation by SLA only | 3.3 |
| 5 Partner = `partnered_business_units`; no-BU clients to the CEO | 1, 3.3 |
| 6 mailbox tenant, held-screen masking, country mapping, LLM context | 2, 3.2 |
