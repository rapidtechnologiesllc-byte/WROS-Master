# Client contact confidentiality

**Status:** DESIGN for Ruthless Architect review, then CEO answers to Q1-Q3. No code until approved.
**Date:** 2026-11-27 · Requested with the approval of `RECRUITMENT_VS_WORKFORCE_DESIGN.md`.

## 1. The rule (CEO 2026-11-27)

> "Client POC details should only be visible to partner and above and the assigned account manager for that
> account. All other communication via HRMS to the client POC should be filtered and require either partner or
> account manager approval."

Two parts:
1. **See:** a client contact's email, phone and LinkedIn are visible only to (a) Partner level and above
   (`authority.is_partner`, role template level, never a role name) and (b) that client's account manager
   (`clients.account_manager_user_id`). Everyone else sees the name, title and role type, with the address masked
   (`j***@acme.com`, phone hidden).
2. **Reach:** any HRMS message (email, WhatsApp, SMS) to a client contact that is not sent by a Partner+ or that
   client's account manager is **held** until a Partner+ or the account manager approves it.

## 2. Where contacts are today
| Path | What it does | Evidence |
|---|---|---|
| Client screen | lists contacts with email and phone | `clients.py:300-330`, `client_service` |
| Invoices | emailed to the client's ACCOUNTS contact | `invoice_service.py:365-368` |
| Client timesheet approval | emailed to TIMESHEET_APPROVER contacts | `client_timesheet_approval_service.py:127-129` |
| Inbound mail | matches senders to contacts, logs client emails | `client_email_log_service.py:51` |
| Allocation | stores the client reporting manager contact | `employee_allocation.py:89` |
| Free-form sends | any address typed by a user | `email.py:113`, `msgraph.py:276`, newsletter, Thunder, staff mail |

About seven outbound paths, with no single chokepoint (`EmailService.send_email`, `GraphMailbox.create_draft`,
`mail_sender`, `msgraph /me/sendMail`, newsletter `/me/sendMail`, `email_delivery` / Twilio / stub providers,
`channel_processors`).

## 3. Design

### 3.1 One visibility rule, applied in every response
- `client_contact_access.can_see(db, user, client) -> bool`: `authority.is_partner(db, user)` or
  `client.account_manager_user_id == user.UserID`.
- `client_contact_access.present(db, user, contact) -> dict`: full details when `can_see`, else name, title and
  role type, the email masked, and no phone or LinkedIn.
- Every response that carries contact details goes through `present`: client detail and contact list
  (`clients.py`), allocation detail (client reporting manager), invoice preview (to-address), the timesheet
  approval screen (approver addresses), and the client email log (sender addresses).
- Adding or editing a contact stays with whoever may edit the client. After saving, the editor sees what
  `present` allows.
- A guard test fails when a schema exposes `ClientContact.email/phone/linkedin_url` other than through `present`.

### 3.2 One outbound guard, called by every send path
- `client_contact_guard.check(db, sender, recipients, channel, purpose) -> Decision`:
  - no recipient is an active client contact of the sender's tenant → `SEND`
  - the sender is Partner+, or the account manager of **every** contacted client → `SEND`
  - a **standing approval** covers (contact, purpose) → `SEND` (Q1)
  - otherwise → `HOLD`
- **Held messages** go to a new table, `client_contact_approvals`: `tenant_id`, `client_id`, `contact_id`,
  `channel`, `purpose`, `requested_by`, the rendered `payload` (subject, body, attachments ref), `status`
  (PENDING/APPROVED/REJECTED/EXPIRED), `decided_by`, `decided_at`, `reason`. The send path returns "held for
  approval" instead of sending. The approver gets one task: the account manager, else the BU's partner, else the
  CEO. That task is a real decision. Approve sends the stored message unchanged; reject tells the requester why.
- **Standing approvals:** a new table, `client_contact_standing_approvals`: (`contact_id`, `purpose`,
  `approved_by`, `approved_at`, `revoked_at`). It covers system messages such as invoices and timesheet approval
  links, so they don't stop for a decision every week (Q1).
- **Every send path calls the guard**: `EmailService.send_email`, `GraphMailbox.create_draft`, `mail_sender`,
  `msgraph.send_mail`, newsletter, `email_delivery` and providers, WhatsApp/SMS senders. A guard test lists every
  Graph `sendMail` / `createDraft` / provider send in `app/` and fails when one is not routed through the guard.
- Matching is by normalized address (lower-case, trimmed) and normalized phone (E.164), against active contacts
  in the sender's tenant. CC and BCC count too.

### 3.3 Thunder and Flash
Agents never write to client contacts on their own. Their messages to a contact always `HOLD` unless a standing
approval covers the purpose. That holds the Phalanx rule: Flash escalates a held message older than the SLA to
the account manager, then the Partner.

## 4. Questions for the CEO (recommended answer first)
- **Q1. System messages (invoices to the client's Accounts contact, timesheet approval links):** need a standing
  approval per contact and purpose, given once by the account manager or a Partner? Recommended: yes. The
  alternative is approval of every single invoice email, which stalls billing.
- **Q2. The client owner (who sells to the client, `client_owner_user_id`):** same visibility and send rights as
  the account manager? Recommended: yes, they work the same contacts.
- **Q3. Finance (AR follow-ups):** sees the Accounts contact's address in full, or masked? Recommended: masked;
  Finance sends through the system with the standing approval, and the account manager sees replies.

## 5. Delivery
One PR: `client_contact_access` + `present` in every response, the guard in every send path, the two tables, the
approval task and screen, the guard tests, and a parity check that every send path still sends for a Partner and
an account manager. It is not stacked on the requisition PRs; it can ship first.
