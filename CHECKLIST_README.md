# Onboarding Checklist — Usage Guide

A flexible onboarding task system where **Hiring Managers** build reusable checklist templates and assign them to candidates. Two task types, **To-Do** and **Queue**, power different workflow patterns.

---

## Table of Contents

1. [Concepts](#1-concepts)
2. [Item Types Explained](#2-item-types-explained)
3. [Workflow Overview](#3-workflow-overview)
4. [HR Guide — Templates](#4-hr-guide--templates)
5. [HR Guide — Assigning to a Candidate](#5-hr-guide--assigning-to-a-candidate)
6. [HR Guide — Monitoring & Manual Completion](#6-hr-guide--monitoring--manual-completion)
7. [Candidate Guide](#7-candidate-guide)
8. [Queue Auto-Activation Logic](#8-queue-auto-activation-logic)
9. [API Reference](#9-api-reference)
10. [Example End-to-End Flow](#10-example-end-to-end-flow)
11. [Status Lifecycle Charts](#11-status-lifecycle-charts)

---

## 1. Concepts

| Term | Description |
|---|---|
| **Checklist Template** | A reusable blueprint created by HR. Contains a list of task definitions. |
| **Template Item** | A single task definition inside a template (type, title, due-day offset). |
| **Candidate Checklist** | A live copy of a template assigned to one specific candidate. |
| **Candidate Checklist Item** | The runtime copy of a template item — tracks `status`, `due_date`, etc. |

> **Templates are never modified once assigned.** Changing a template later does _not_ affect already-assigned checklists. Each assignment takes a snapshot.

---

## 2. Item Types Explained

### `todo` — Standard Task

- The candidate can complete it **at any time** — there is no ordering dependency.
- Starts in `pending` status.
- Can have an optional due date (computed automatically from `due_days_offset`).

**Use for:** Uploading a document, signing a form, completing a training module independently.

---

### `queue` — Ordered / Sequential Task

- Items are worked through **one at a time**, in ascending `order_index` order.
- Only the current active queue item is unlocked. All others remain `pending`.
- When an active item is marked complete → the **next** queue item automatically becomes `active`.
- A candidate **cannot** skip ahead or complete a queue item out of order.

**Use for:** Step-by-step onboarding flows — e.g. IT setup must be done before badge issuance, badge before building access.

> ⚠️ **Mixed checklists**: A template can contain both `todo` and `queue` items. Todo items are always accessible. Only queue items enforce ordering among themselves.

---

## 3. Workflow Overview

```
HR creates Template → Adds Items (todo/queue) → Assigns Template to Candidate
                                                         ↓
                                         [System copies all items]
                                         [First queue item → "active"]
                                         [All todo items → "pending" (open)]
                                                         ↓
                              Candidate completes todo items (any time)
                              Candidate completes active queue item
                                         ↓
                              System auto-activates next queue item
                                         ↓
                              All items done → Checklist "completed"
```

---

## 4. HR Guide — Templates

### Create a Template (with items inline)

```http
POST /checklist/hr/templates
Authorization: Bearer <hr_token>
Content-Type: application/json

{
  "name": "Standard Software Engineer Onboarding",
  "description": "Template for all new SWE hires",
  "items": [
    {
      "title": "Sign Offer Letter",
      "item_type": "todo",
      "order_index": 0,
      "due_days_offset": 1
    },
    {
      "title": "Submit PAN & Aadhar Documents",
      "item_type": "todo",
      "order_index": 1,
      "due_days_offset": 3
    },
    {
      "title": "IT Setup — Laptop & Accounts",
      "description": "Coordinate with IT to set up your laptop, email, and access credentials.",
      "item_type": "queue",
      "order_index": 0
    },
    {
      "title": "Security Badge Issuance",
      "description": "Visit HR desk with a photo ID to collect your badge.",
      "item_type": "queue",
      "order_index": 1
    },
    {
      "title": "Building Access Activation",
      "description": "After receiving badge, IT will activate floor access within 24 hours.",
      "item_type": "queue",
      "order_index": 2
    }
  ]
}
```

> **`due_days_offset`**: Number of days from the checklist **assignment date** when this item is due. Leave `null` for no due date.

---

### Add an Item to an Existing Template

```http
POST /checklist/hr/templates/{template_id}/items
Authorization: Bearer <hr_token>
Content-Type: application/json

{
  "title": "Complete HR Orientation",
  "item_type": "todo",
  "order_index": 2,
  "due_days_offset": 7
}
```

---

### Update a Template Item

```http
PUT /checklist/hr/templates/{template_id}/items/{item_id}
Authorization: Bearer <hr_token>
Content-Type: application/json

{
  "title": "Complete HR & Ethics Orientation",
  "due_days_offset": 5
}
```

> Only the fields you include will be updated (partial update).

---

### Delete a Template Item

```http
DELETE /checklist/hr/templates/{template_id}/items/{item_id}
Authorization: Bearer <hr_token>
```

---

### Delete a Template

```http
DELETE /checklist/hr/templates/{template_id}
Authorization: Bearer <hr_token>
```

> ⚠️ Deleting a template does **not** affect already-assigned candidate checklists. The candidate's snapshot remains intact.

---

## 5. HR Guide — Assigning to a Candidate

```http
POST /checklist/hr/assign
Authorization: Bearer <hr_token>
Content-Type: application/json

{
  "candidate_id": "CAND-20240401-001",
  "template_id": 3
}
```

**What happens automatically on assignment:**
1. All template items are **copied** into a new `CandidateChecklist`.
2. Due dates are computed: `assigned_at + due_days_offset`.
3. The **first queue item** (lowest `order_index`) is set to `active`.
4. All other queue items remain `pending`.
5. All `todo` items are set to `pending` (immediately actionable by candidate).

**Response** includes the full checklist with each item's status:

```json
{
  "id": 12,
  "candidate_id": "CAND-20240401-001",
  "template_name": "Standard Software Engineer Onboarding",
  "status": "active",
  "total_items": 5,
  "completed_items": 0,
  "todo_items": 2,
  "queue_items": 3,
  "active_queue_item": {
    "id": 31,
    "title": "IT Setup — Laptop & Accounts",
    "item_type": "queue",
    "status": "active",
    "order_index": 0
  },
  "items": [ ... ]
}
```

> A candidate can have **multiple checklists** assigned at the same time (e.g. one general + one role-specific).

---

## 6. HR Guide — Monitoring & Manual Completion

### View All Checklists for a Candidate

```http
GET /checklist/hr/candidate/{candidate_id}
Authorization: Bearer <hr_token>
```

Returns all checklists (active and completed) with per-item statuses and progress summary.

---

### Manually Mark an Item Complete (HR)

HR can mark any item complete on behalf of a candidate — useful when a task is verified offline.

```http
PUT /checklist/hr/candidate-item/{item_id}/complete
Authorization: Bearer <hr_token>
```

Response shows the completed item and the next auto-activated queue item (if any):

```json
{
  "status": "success",
  "message": "Item 'IT Setup — Laptop & Accounts' marked complete. Next queue item 'Security Badge Issuance' is now active.",
  "completed_item": { ... },
  "next_active_item": {
    "title": "Security Badge Issuance",
    "status": "active"
  },
  "checklist_completed": false
}
```

---

## 7. Candidate Guide

### View My Checklists

```http
GET /checklist/candidate/my-checklists
Authorization: Bearer <candidate_token>
```

Returns all assigned checklists. The `active_queue_item` field tells the candidate exactly which queue task they need to do now.

---

### Complete a Task

```http
PUT /checklist/candidate/item/{item_id}/complete
Authorization: Bearer <candidate_token>
```

**Rules:**
- ✅ Any `todo` item in `pending` status can be completed at any time.
- ✅ A `queue` item can only be completed when its `status` is `"active"`.
- ❌ A `queue` item with `status = "pending"` will return a `400` error — the candidate must complete prior queue items first.
- ❌ An already `completed` item returns `400`.

**Success Response:**

```json
{
  "status": "success",
  "message": "Item 'IT Setup — Laptop & Accounts' marked complete. Next queue item 'Security Badge Issuance' is now active.",
  "completed_item": {
    "id": 31,
    "title": "IT Setup — Laptop & Accounts",
    "item_type": "queue",
    "status": "completed",
    "completed_at": "2024-04-01T10:30:00"
  },
  "next_active_item": {
    "id": 32,
    "title": "Security Badge Issuance",
    "item_type": "queue",
    "status": "active",
    "activated_at": "2024-04-01T10:30:00"
  },
  "checklist_completed": false
}
```

When every item on the checklist is done, `checklist_completed` becomes `true` and the checklist `status` changes to `"completed"`.

---

## 8. Queue Auto-Activation Logic

```
Template has queue items with order_index: 0, 1, 2

On assignment:
  item[order_index=0].status = "active"    ← unlocked
  item[order_index=1].status = "pending"   ← locked
  item[order_index=2].status = "pending"   ← locked

Candidate completes item[order_index=0]:
  item[order_index=0].status = "completed"
  item[order_index=1].status = "active"    ← auto-unlocked ✓

Candidate completes item[order_index=1]:
  item[order_index=1].status = "completed"
  item[order_index=2].status = "active"    ← auto-unlocked ✓

Candidate completes item[order_index=2]:
  item[order_index=2].status = "completed"
  → No more queue items pending
  → All items done? → CandidateChecklist.status = "completed"
```

---

## 9. API Reference

### HR Routes

| Method | Path | Permission | Description |
|---|---|---|---|
| `POST` | `/checklist/hr/templates` | `candidate.edit` | Create template |
| `GET` | `/checklist/hr/templates` | `candidate.view` | List all templates |
| `GET` | `/checklist/hr/templates/{id}` | `candidate.view` | Get template + items |
| `PUT` | `/checklist/hr/templates/{id}` | `candidate.edit` | Update template |
| `DELETE` | `/checklist/hr/templates/{id}` | `candidate.edit` | Delete template |
| `POST` | `/checklist/hr/templates/{id}/items` | `candidate.edit` | Add item to template |
| `PUT` | `/checklist/hr/templates/{id}/items/{item_id}` | `candidate.edit` | Update template item |
| `DELETE` | `/checklist/hr/templates/{id}/items/{item_id}` | `candidate.edit` | Delete template item |
| `POST` | `/checklist/hr/assign` | `candidate.edit` | Assign template to candidate |
| `GET` | `/checklist/hr/candidate/{candidate_id}` | `candidate.view` | View candidate checklists |
| `PUT` | `/checklist/hr/candidate-item/{item_id}/complete` | `candidate.edit` | HR manually completes item |

### Candidate Routes

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/checklist/candidate/my-checklists` | Candidate JWT | View own checklists |
| `PUT` | `/checklist/candidate/item/{item_id}/complete` | Candidate JWT | Mark item as done |

---

## 10. Example End-to-End Flow

### Step 1 — HR Creates a Template

```http
POST /checklist/hr/templates
{
  "name": "New Hire — Week 1",
  "items": [
    { "title": "Sign NDA",           "item_type": "todo",  "order_index": 0, "due_days_offset": 1 },
    { "title": "Upload ID Proof",    "item_type": "todo",  "order_index": 1, "due_days_offset": 2 },
    { "title": "IT Account Setup",   "item_type": "queue", "order_index": 0 },
    { "title": "Workstation Ready",  "item_type": "queue", "order_index": 1 },
    { "title": "System Access Test", "item_type": "queue", "order_index": 2 }
  ]
}
→ Response: { "id": 5, "name": "New Hire — Week 1", ... }
```

### Step 2 — HR Assigns to Candidate

```http
POST /checklist/hr/assign
{ "candidate_id": "CAND-001", "template_id": 5 }

→ Queue item "IT Account Setup" is now ACTIVE
→ All todo items are PENDING (open)
```

### Step 3 — Candidate Signs NDA (todo, any time)

```http
PUT /checklist/candidate/item/41/complete
→ "Sign NDA" → completed ✓
```

### Step 4 — Candidate Completes Queue Step 1

```http
PUT /checklist/candidate/item/43/complete    ← "IT Account Setup" (active)
→ completed ✓
→ "Workstation Ready" automatically becomes ACTIVE
```

### Step 5 — Candidate tries to skip queue (blocked)

```http
PUT /checklist/candidate/item/45/complete    ← "System Access Test" (still pending)
→ 400 Bad Request: "Queue item cannot be completed yet — it is not the current active queue item."
```

### Step 6 — After all queue items done

```http
PUT /checklist/candidate/item/44/complete    ← "Workstation Ready"
PUT /checklist/candidate/item/45/complete    ← "System Access Test" (now active)
PUT /checklist/candidate/item/42/complete    ← "Upload ID Proof" (todo, any time)

→ checklist_completed: true
→ CandidateChecklist.status = "completed"
```

---

## 11. Status Lifecycle Charts

### `todo` Item

```
[pending] ──(complete)──▶ [completed]
```

### `queue` Item

```
[pending] ──(previous item completes)──▶ [active] ──(complete)──▶ [completed]
```

### Checklist

```
[active] ──(all items completed)──▶ [completed]
```

---

## Common Errors

| HTTP Code | Message | Cause |
|---|---|---|
| `400` | Item is already completed | Trying to complete an already-done item |
| `400` | Queue item cannot be completed yet | Trying to complete a queue item that is still `pending` |
| `404` | Candidate not found | Invalid `candidate_id` in assign request |
| `404` | Template not found | Invalid `template_id` |
| `403` | Permission denied | User role lacks `candidate.edit` or `candidate.view` |

---

*Last updated: April 2026 | Onboarding Module Backend*
