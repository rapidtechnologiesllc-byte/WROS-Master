# BlitzenX WROS Agent System — Registry, Architecture & Roadmap

**Last Updated:** 2026-08-09 (content), merged into one file 2026-08-11
**Source:** Merged from `AGENTS.md`, `AgentDevelopment.md`, `AGENT_COMMUNICATION_SYSTEM.md`, `AGENT_STATE_SYSTEM_COMPLETE.md`, and `AGENT_DEVELOPMENT_BACKLOG.md` — those four are now deleted, this file is the single source of truth going forward.

> **Known discrepancy, flagged rather than silently resolved** (per this project's own convention — see `CLAUDE.md`'s Core-Pull correction): the five source docs disagree on how many agents this system covers — **27** (this file's own registry, Section 3), **50+** (referenced throughout the architecture/state-dashboard docs), and **56** (the operating-model section count in the backlog doc, Section 7 — one agent can cover more than one section, so 56 sections ≠ 56 agents). Treat the 27-agent registry in Section 3 as the concrete, current count; the "50+" figures elsewhere are aspirational targets from the same planning pass, not a second real count.
>
> The two tier-naming schemes below (Section 2's Tier 1–6 vs Section 3's CORE/RESOURCE/FINANCE/HR/ENGAGEMENT/DECISION/MONITOR/SUPPORT) also don't map 1:1 — they were written in the same session but never reconciled. Section 3's names are what's actually referenced in code/status tracking; Section 2's numbered tiers are the strategic/authority framing.
>
> Per `CLAUDE.md`'s 2026-08-11 update, none of this blocks building — it's context, not a gate.

---

## 1. Executive Mandate

> **BlitzenX will reach $100M revenue and 2,000 employees by 2030. Every agent must contribute measurably to that goal, or it gets disabled.**

This is not a collection of AI assistants — it's an **Agentic Enterprise Operating System** where:
- 50+ specialized agents (target; 27 concretely defined today, see Section 3) work in a coordinated hierarchy
- Every agent has a contract (inputs, outputs, authority, success metrics, failure conditions — template in Section 6)
- Every agent has a strategic role tied to the $100M/2000 goal
- Every agent is accountable (fear score, kill switches, quarterly reviews — Section 5)
- No agent operates independently — structured event communication, not conversational memory (Section 4)

### The "300 Mindset"

Borrowed from Sparta: absolute commitment, no retreat, no excuses.

- Targets are operational requirements, not suggestions
- Success rate < 95% = intervention required
- Fear score > 60 = leadership escalation; > 80 = kill switch candidate
- Every decision must have: evidence, confidence, recommended action, owner, deadline (not "agent → conversational memory → human intuition")
- Hallucination rate, false positive/negative rate, and escalation frequency are tracked per agent; unauthorized actions trigger a kill switch

### Authority Levels

| Level | Name | Meaning |
|---|---|---|
| 0 | Observe | Cannot act on observations without approval |
| 1 | Recommend | Recommendation doesn't move until a human approves |
| 2 | Execute w/ Approval | Needs explicit authorization per action |
| 3 | Autonomous | Acts independently, within policy boundaries |
| 4 | Deterministic | Not a choice — enforced, AI cannot override |

---

## 2. Agent Hierarchy & Tiers (strategic framing)

```
                    WROS ORCHESTRATOR
                           │
          ┌────────────────┼────────────────┐
          │                │                │
     ENTERPRISE        COMMERCIAL       WORKFORCE
    (50+ Agents)      (14 Agents)      (18 Agents)
          │                │                │
     Finance        Accounts/Pipeline   Capacity
     Risk           Sales               Skills
     CEO Dependency Expansion           Deployment
     Governance     Relationships       Utilization
          │                │                │
          └────────────────┼────────────────┘
                           │
                       HUMAN OWNER
                           │
                      WROS STATE
                           │
                  Candidate Data, Employee Data,
                  Revenue, Utilization, Risk Events
```

**Rule:** agents don't arbitrarily invoke each other. The Orchestrator decides which agent acts, in what sequence, whether authority exists, whether human approval is required, and whether it changes enterprise state.

| Tier | Agents | Authority | Accountability | Target |
|---|---|---|---|---|
| 1 — Core Recruitment & Control | Thunder, Recruitment, Supervisor, CEO Dependency | 3–4 | Daily standups, success rate > 95% | 2,000 employees by 2030 |
| 2 — Resource Management | Resource Management, Core-Pull Conflict, Deployment | 2–3 | Weekly reviews, utilization > 75% | 80% avg utilization |
| 3 — Finance & Economics | CFO, Partner ROI, Revenue Recognition, Margin, EBITDA, Cash Flow | 1–2 | Daily revenue tracking, accuracy > 99% | $100M revenue by 2030 |
| 4 — HR & People | HR, Employee Mental Health, Onboarding, Buddy Program, Retention Risk | 1–3 | Weekly wellbeing checks, retention > 95% | 95% retention in first 90 days |
| 5 — KPI & Metrics | KPI Agent, Forecasting, Risk, CEO Dependency Reduction | 0–1 | Daily progress tracking, forecast accuracy > 90% | On-track toward $100M/2000 |
| 6 — Support | Engagement, Interview Reminder, Activity Feed, Executive Signal, Help Desk | 0–2 | Weekly, engagement metrics | < 24hr response time |

---

## 3. Agent Registry — Concrete Status (27 agents)

**Fully Operational:** 5 (Recruitment, Supervisor, Thunder, Flash, HTD Pipeline)
**Partially Implemented (code exists, gaps in logging/routes):** 19
**Not Yet Implemented:** 3 (KPI, HR, Employee Mental Health)

### CORE tier — recruiting pipeline (✅ Operational)

| Agent | Service File | API Routes | Logging | Notes |
|---|---|---|---|---|
| Recruitment Agent | `recruitment_job_creation_service.py` | `POST /jobs/generate-with-agent`, `POST /jobs/generate-complete` | ✅ (2026-08-08) | Tested with edge cases; LLM prompt validates job titles exclude location/seniority |
| Supervisor Agent | `supervisor_agent_service.py` | Embedded in orchestration | ✅ | Multi-agent coordinator for candidate lifecycle |
| Thunder (AI Recruiter) | `thunder_service.py` | Multiple config endpoints | ✅ | External-facing (WhatsApp/Email). Fixed 2026-08-07: was passing wrong `tenant_id` to auto-assignment; now correctly uses `user.tenant_id` throughout |
| Flash Orchestration Engine | `flash_orchestration_engine.py` | — | ✅ | Daily execution; analyzes HTD + opportunities + agent state; issues directives, escalates to CEO when critical |

### RESOURCE tier (⚠️ Partial)

| Agent | Service File | API Routes | Logging | Notes |
|---|---|---|---|---|
| Resource Management Agent | `resource_management_agent_service.py` | ✅ | ❌ TODO | Bench matching, allocation. Enforces no cross-BU borrowing |
| Core-Pull Conflict Agent | `core_pull_service.py` | ❌ TODO | ❌ TODO | CORE wins over SPECIALTY (R-04 enforcement) |
| HTD Pipeline Accountability Agent | `htd_pipeline_accountability_agent.py` | ✅ | ✅ | Tracks SPECIALTY→CORE conversion, partner CORE capacity forecast, bottleneck detection |

### FINANCE tier (⚠️ Partial)

| Agent | Service File | API Routes | Logging | Notes |
|---|---|---|---|---|
| CFO Agent | `cfo_agent_service.py` | ✅ | ❌ TODO | Revenue snapshot, EBITDA forecasting, cash flow, margin trends |
| CEO/FY Progress Agent | `ceo_fy_progress_service.py` | ✅ | ❌ TODO | Tracks quarterly progress toward 2030 goal; validates investment requests |
| Partner ROI Agent | `partner_roi_service.py` | ✅ | ❌ TODO | Partner revenue contribution, utilization, SPECIALTY economics (125% of BXIN cost) |
| Opportunity Tracker Agent | `opportunity_tracker_agent_service.py` | ✅ | ❌ TODO | Sales pipeline toward $100M; alerts on stalls, escalates at-risk deals to Flash |

### HR tier (❌ Mixed)

| Agent | Service File | API Routes | Logging | Notes |
|---|---|---|---|---|
| Onboarding Agent | `onboarding_agent_service.py` | ✅ | ❌ TODO | Document collection, joining prep, Candidate→Employee transition |
| Buddy Program Agent | `buddy_program_service.py` | ❌ TODO | ❌ TODO | 30-day buddy program tracking and graduation |
| Employee Milestone Agent | `employee_milestone_service.py` | ❌ TODO | ❌ TODO | Anniversaries, promotions, achievements |
| **KPI Agent** | `kpi_agent_service.py` (stub only) | ❌ | ❌ | **NOT IMPLEMENTED** — high priority, needed for dashboard |
| **HR Agent** | `hr_agent_service.py` (stub only) | ❌ | ❌ | **NOT IMPLEMENTED** — high priority, core to WROS |
| **Employee Mental Health Agent** | `employee_mental_health_agent_service.py` (stub only) | ❌ | ❌ | **NOT IMPLEMENTED** — medium priority |

### ENGAGEMENT tier (⚠️ Partial)

| Agent | Service File | API Routes | Logging |
|---|---|---|---|
| Outreach Agent | `outreach_agent_service.py` | ❌ TODO | ❌ TODO |
| Interview Reminder Agent | `interview_reminder_service.py` | ❌ TODO | ❌ TODO |
| Interview Confirmation Agent | `interview_confirmation_service.py` | ❌ TODO | ❌ TODO |

### DECISION tier — scoring agents (⚠️ Partial)

| Agent | Service File | API Routes | Logging |
|---|---|---|---|
| Abandonment Scoring Agent | `abandonment_scoring_service.py` | ❌ TODO | ❌ TODO |
| Compensation Scoring Agent | `compensation_scoring_service.py` | ❌ TODO | ❌ TODO |
| Desire Intelligence Agent | `desire_signal_service.py`, `desire_profile_service.py` | ❌ TODO | ❌ TODO |

### SUPPORT tier (⚠️ Partial)

| Agent | Service File | API Routes | Logging |
|---|---|---|---|
| Activity Feed Agent | `activity_feed_service.py` | ❌ TODO | ❌ TODO |
| Daily Digest Agent | `daily_digest_service.py` | ❌ TODO | ❌ TODO |
| Executive Signal Agent | N/A (in dashboard) | ✅ | ❌ TODO |
| Culture Agent | `culture_agent_service.py` | — | ❌ TODO |

**Go-live readiness at last count: 5/27 agents fully operational (18.5%).**

---

## 4. Inter-Agent Communication System

**Problem it solves:** agents were isolated — no way for Thunder to tell HR "I qualified a candidate."

**Solution:** `AgentEventService` (`app/services/agent_event_service.py`) — structured event-driven communication, not conversational memory.

```python
# Agent publishes structured event
AgentEventService.publish_event(
    db=db,
    event_type="candidate.qualified",
    source_agent="Thunder",
    entity_id=candidate_123,
    target_agents=["Interview Reminder", "KPI Agent"],
    payload={"candidate_name": "John Doe"},
    action_required="Schedule interview",
    owner="Interview Reminder Agent",
    deadline=datetime.utcnow() + timedelta(days=1)
)

# Other agents consume the event
pending_events = AgentEventService.get_pending_events(db, "Interview Reminder")

# Agent acts on event
AgentEventService.consume_event(
    db=db, event_id=evt_123,
    consumer_agent="Interview Reminder",
    action_taken="Scheduled interview for 2026-08-15"
)
```

If an agent gets stuck, it escalates instead: `escalate_event(event_id, reason, "CEO")` moves the event to `ESCALATED` and alerts the target.

### Event model

```python
class AgentEvent:
    event_id: str; event_type: str; source_agent: str; target_agents: str
    entity_id: str; entity_type: str
    current_state: str; new_state: str
    payload: JSON; confidence: int
    action_required: str; owner: str; deadline: DateTime
    status: str  # PENDING / PROCESSED / ESCALATED
    audit_trail: JSON
```

### Recruitment flow (example event chain)

```
Thunder → "candidate.qualified" → Interview Reminder → schedules interview
        → "candidate.interviewed" → HR Agent → sends offer
        → "candidate.offered" → Onboarding Agent → begins onboarding
        → "hire.completed" → Resource Management → assigns to project
        → consumed throughout by KPI Agent, which updates metrics at every step
```

Other mapped flows: Resource allocation (utilization → KPI), Finance (revenue recognition → margin calculation → KPI), HR (employee lifecycle → performance tracking → retention risk).

### Status

Built: event service, event model with audit trail, 20+ event types mapped, publish/consume/escalate all implemented, full workflow examples documented.
Ready but not yet run: seed script for 59 candidates / 50 employees / 10 jobs / 6 opportunities / sample events (`migrations/seed_real_business_data.py`).
Not yet done: wiring agents to actually consume events on a schedule (cron), event listener endpoints for real-time notification, hooking fear-score calculation to the event stream.

---

## 5. Agent State Dashboard & Fear Score System

**Coverage as designed:** all agents, with strategic targeting, fear scoring, and kill switches.

### What's built

| Piece | File |
|---|---|
| Agent Registry (agent metadata: id, domain, tier, owner, authority, strategic importance, FY/2030 targets, thresholds) | `app/services/agent_registry_service.py` |
| State models: `agent_state_targets`, `agent_actual_performance`, `agent_fear_scores`, `agent_issues`, `agent_improvements` | `app/models/agent_state_target.py` |
| Fear score calc, progress tracking, stress/threat classification, auto-generated improvement recs, kill-switch eligibility | `app/services/agent_state_service.py` |
| Kill switch evaluation + execution (disable/re-enable, audited) | `app/services/agent_kill_switch_service.py` |
| Role-based dashboard views | `app/services/role_based_dashboard_service.py` |

### Fear score (single canonical formula — was duplicated 3x across source docs)

```
Fear Score = 20 (baseline) + (gap_percent × 0.8)

Min: 20 (no gap, beating target)   Max: 100 (100% gap, zero progress)

Stress levels:      Threat levels:
  0–20  MOTIVATED      NONE (0–50)        no action needed
  20–40 NEUTRAL         WARNING (50–70)    investigate, plan improvements
  40–60 CONCERNED       CRITICAL (70–80)   escalate to leadership
  60–80 DESPERATE       EXISTENTIAL (80+)  evaluate kill switch
  80+   TERRIFIED
```

Auto-generated recommendation triggers:
```
fear_score > 60           → "URGENT: escalate to leadership immediately"
fy_progress < 50%         → "CRITICAL: increase execution velocity"
success_rate < 90%        → "Debug quality: investigate failures"
is_kill_switch_candidate  → "EVALUATE KILL SWITCH"
each blocking_issue       → "BLOCKING ISSUE: [description] — [impact]"
```

### Kill switch logic

- **Criteria (AND):** Fear > 85, Gap > 50%, min success rate 90%
- **Execution:** CEO/Admin only, reason logged to audit trail, agent → `DISABLED`, all further execution requests → 403, re-enable requires CEO approval

### Role-based dashboards

| Role | Dashboard | Featured Agents | Focus |
|---|---|---|---|
| CEO | Strategic | KPI, Risk, CFO, Forecast, Scrum | All agents, risks, $100M/2000 progress |
| Recruiter | Pipeline | Thunder, Recruitment, Interviews | Hiring funnel, time-to-fill |
| HR Manager | People | HR Agent, Mental Health, Onboarding, Buddy | Retention, wellbeing, culture |
| Finance | Revenue | CFO, Partner ROI, Opportunity, Margin | Pipeline, revenue, margins |
| Manager | Operations | Resource Mgmt, Deployment, Performance | Utilization, team KPIs |
| Employee | Personal | None | Timesheet, tasks, growth |

### API endpoints (as designed)

```
GET  /agent-state/all                              -- all agents with fear scores
GET  /agent-state/{agent_name}                      -- single agent detail
PUT  /agent-state/{agent_name}/kill-switch           -- execute kill switch

GET  /dashboard/my-dashboard                         -- personalized for current user
GET  /dashboard/ceo-strategic | recruiter-pipeline | hr-people | finance-revenue

GET  /agent-kill-switch/evaluate/{agent_name}
GET  /agent-kill-switch/evaluate-all
POST /agent-kill-switch/execute/{agent_name}
POST /agent-kill-switch/reenable/{agent_name}
```

### Status snapshot (2026-08-09)

Done: data models, services, API endpoints, migrations, 50+ agent registry, role-based dashboard logic, kill switch automation, test scenarios.
Not done: frontend dashboard, real-time updates via WebSocket, email alerts, audit trail viewer.

> **Caveat inherited from Section 1's discrepancy note:** "backend 100% complete" claims in the original source doc should be re-verified against actual code before being trusted — this project has a documented pattern (see `CLAUDE.md`) of docstrings/status docs asserting a component is real and wired when it wasn't (e.g. the `/admin/ai-config` endpoint referenced by three different files' docstrings that turned out not to exist). Don't take "✅ complete" in this file at face value for anything you're about to build on top of — check the actual code first.

---

## 6. Agent Contract Template

Every agent entering production must define all of this (JSON shown for illustration, not a literal schema):

```python
{
  "agent_name": "Thunder", "unique_agent_id": "agent_thunder_001",
  "domain": "recruitment", "tier": "tier_1_core", "owner": "CFO/Recruitment",

  "business_purpose": "AI recruiter: source → screen → interview → offer → hire",
  "contributes_to": ["revenue", "headcount"], "strategic_importance": "CRITICAL",

  "inputs": ["Job requirements", "Candidate pool", "Interview feedback", "Offer decisions"],
  "outputs": ["Candidate shortlist", "Interview schedule", "Offer package", "Recruitment metrics"],
  "tools": ["LinkedIn API", "Job board integrations", "Interview scheduler", "Offer letter generator", "Candidate DB"],
  "data_sources": ["candidate table (r/w)", "job_requirements (r)", "interview (r/w)", "offer_letter (r/w)"],

  "authority_level": 3,
  "can_modify_candidate": true, "can_schedule_interview": true,
  "can_create_offer": false,           # requires human approval
  "can_send_offer_to_candidate": false, # requires CEO sign-off

  "must_escalate_if": [
    "Candidate < 30% match to role requirements",
    "Role requires CORE certification (defer to HR)",
    "Compensation request > 20% above market rate",
    "Candidate has red flags"
  ],
  "policies": [
    "Never fabricate candidate qualifications", "Never promise start date without offer approval",
    "Never commit to compensation without CFO review", "All candidates must pass bias screening",
    "No discrimination on protected characteristics"
  ],
  "escalate_to": {
    "high_risk_candidate": "HR team", "salary_negotiation": "CFO",
    "offer_rejected_3x": "CEO", "zero_qualified_candidates": "Recruitment leadership"
  },
  "requires_approval": ["Interview scheduling", "Offer creation (legal review)", "Offer send > $200k/year (CEO)"],

  "audit_trail": true, "decision_log": "agent_execution_log table",

  "success_metrics": {
    "fy_target": {"value": 250, "unit": "employees_hired", "deadline": "2026-12-31"},
    "y2030_target": {"value": 2000, "unit": "employees", "deadline": "2030-12-31"},
    "time_to_hire": {"target": 30, "unit": "days", "min": 20, "max": 45},
    "offer_acceptance_rate": {"target": 80, "unit": "%", "min": 70},
    "candidate_quality": {"target": 4.0, "unit": "out_of_5", "min": 3.5},
    "success_rate": {"target": 95, "unit": "%", "min": 95}
  },
  "failure_conditions": [
    "Success rate < 90% for 2+ weeks", "Hiring targets < 50% for 2+ months",
    "Quality score < 3.0 for 4+ weeks", "Hallucinating qualifications > 10%",
    "Escalation frequency > 50% of decisions"
  ],
  "recovery_procedure": [
    "Day 1-3: debug mode (detailed logging)", "Day 4-7: reduced autonomy (approval required)",
    "Day 8-14: manual override (human takes over)", "Day 15+: kill switch, escalate to CEO"
  ],
  "downstream_consumers": ["Interview Agent", "HR Agent", "Offer Letter Agent", "KPI Agent"],
  "memory": {
    "transaction_memory": "Current job + candidate in focus",
    "entity_memory": "Candidate skills, experience, interview history",
    "historical_memory": "Past hiring outcomes",
    "policy_memory": "Approved job descriptions, compensation ranges",
    "institutional_memory": "Market data, competitor hiring, tech trends"
  },
  "confidence_thresholds": {"high": "> 85% match", "medium": "70-85% (escalate)", "low": "< 70% (flag risky)"},
  "version": "1.0", "version_date": "2026-08-09", "deployment_date": "2026-08-09"
}
```

### Daily observability every agent must expose

```
Uptime · Executions · Success rate · Failures (+ root cause) · Human overrides
Hallucinations · Escalations · Avg execution time · Cost per execution
Business value generated · False positive % · False negative %
Fear score · Progress to FY target · Progress to 2030 target
```
Lives in: `agent_execution_log` table. Surfaced via: Agent Standups Dashboard (8:00 AM EST), Agent State Dashboard (real-time).

### Pre-production test gate

Unit tests · Scenario tests (realistic conditions, edge cases) · Adversarial tests (can it be manipulated/tricked into policy violations?) · Regression tests · Boundary tests (limits) · Authority tests (can it exceed its own permissions?).

### The 16-item development gate

No agent enters production until it has: defined purpose, owner, inputs, outputs, authority, tools, policies, failure states, escalation rules, audit trail, KPIs, full test suite, rollback mechanism, documented downstream consumers, fear-score baseline, controlled memory access, and version control.

### Development discipline (the order to build in)

1. Start with the contract (inputs/outputs/authority/failure conditions)
2. Define success metrics (FY + 2030 target)
3. Write tests before the agent code
4. Implement conservatively — start at Authority Level 1, earn autonomy
5. Log everything to `agent_execution_log`
6. Monitor from day one (fear score, execution metrics, hallucination rate)
7. Escalate early, before the terror zone
8. Iterate based on real results

### What agents must never become

Independent islands (must use structured events) · Black boxes (every decision auditable) · Unaccountable decision-makers · Policy violators (Level 4 rules are enforced, not advisory) · Hallucination factories (disabled if hallucination rate > 10%) · Out-of-control systems (kill switches exist) · Executors without authority (escalation rules prevent overreach).

---

## 7. Operating Model → Agent Mapping (56 sections)

Maps each of the 56 sections of the BlitzenX operating model (`BLITZENX_OPERATING_MODEL.md`) to a required agent. **Note:** this is a section count, not an agent count — several sections map to the same agent (e.g. Core-Pull Conflict Agent covers sections 3, 4, and 24).

**Status legend:** ✅ Done · 🔄 In Progress · 📅 Pending

| # | Operating model section | Required agent | Status | Owner |
|---|---|---|---|---|
| 1 | CEO unavailable 30 days, business continues | CEO/Executive Signal Agent | 📅 | — |
| 2 | Two legal entities (BXUS + BXIN) | Tenant Isolation & Multi-Entity Agent | 📅 | — |
| 3 | Two independent BUs, one brand (AXION+PRISM) | Business Unit Scoping Agent | 🔄 | Resource Mgmt Agent |
| 4 | No cross-BU operational dependency | **Core-Pull Conflict Agent** | 🔄 | S-353 |
| 5 | Shared corporate functions | Corporate Functions Orchestrator | 📅 | — |
| 6 | BU accountability (AXION+PRISM) | BU Principal Accountability Monitor | 📅 | — |
| 7 | BU Principal accountability (7 categories) | BU Outcome Accountability Agent | 📅 | — |
| 8 | Client vs resource ownership | Client-Resource Relationship Agent | 📅 | — |
| 9 | Account ownership (4 roles) | Account Ownership & Relationship Manager | 📅 | — |
| 10 | Strategic account governance (Tier 1/2/3) | Strategic Account Classification Agent | 📅 | — |
| 11 | CORE business (direct client) | CORE Business Fulfillment Agent | 🔄 | Resource Mgmt + HTD Pipeline |
| 12 | SPECIALTY business (offshore staff aug) | SPECIALTY Capacity Monetization Agent | 📅 | — |
| 13 | SPECIALTY client strategy | SPECIALTY Client Utilization Optimizer | 📅 | — |
| 14 | SPECIALTY resource model | SPECIALTY Allocation Service | 📅 | — |
| 15 | SPECIALTY economics (125% of BXIN cost) | SPECIALTY Economics Tracker | 📅 | Partner ROI Agent |
| 16 | SPECIALTY capacity philosophy | SPECIALTY Capacity Planning Agent | 📅 | HTD Pipeline Agent |
| 17 | Why SPECIALTY exists | HTD Pipeline Accountability Agent | ✅ | S-066 |
| 18 | New-hire entry model | New Hire Entry & Development Gating Agent | 📅 | — |
| 19 | HTD — Hire, Train, Deploy | HTD Pipeline Agent | ✅ | S-066 |
| 20 | HTD timeline (~365 days) | CORE Certification & Readiness Gate Agent | 🔄 | HTD Pipeline Agent |
| 21 | Lateral talent model (90 days min) | Lateral Talent Qualification Agent | 📅 | — |
| 22 | CORE certification (evidence-based) | CORE Certification Evidence Tracker | 📅 | — |
| 23 | CORE deployment (WROS owns workflow) | CORE Deployment Orchestration Agent | 🔄 | Resource Mgmt Agent |
| 24 | No cross-BU resource borrowing | Cross-BU Borrowing Prevention Agent | 🔄 | Core-Pull Conflict Agent |
| 25 | Workforce forecasting (2-3mo horizon) | Workforce Forecasting Agent | 📅 | — |
| 26 | Agentic workforce mgmt (50+ agents) | Agent Orchestration & Coordination Hub | 🔄 | Flash + Supervisor |
| 27 | Leadership Intelligence Agent | Leadership Intelligence Agent | 📅 | — |
| 28 | Succession planning | Succession Planning & Risk Detection Agent | 📅 | Leadership Intelligence Agent |
| 29 | CEO role (strategy, not execution) | CEO Decision Authority Validator | 📅 | Executive Signal Agent |
| 30 | Creation of new BUs (CEO only) | BU Creation Gating Agent | 📅 | — |
| 31 | BU management P&L | BU P&L Tracking & Reporting Agent | 📅 | CFO Agent |
| 32 | SPECIALTY excluded from BU P&L | SPECIALTY Revenue Isolation Agent | 📅 | CFO Agent |
| 33 | Enterprise capital allocation | Capital Allocation Request Validator | 📅 | CFO + CEO Agent |
| 34 | Investment committee | Investment Committee Coordinator | 📅 | CFO Agent |
| 35 | Sales/workforce integration | Sales-to-Workforce Pipeline Agent | 📅 | Opportunity Tracker + Forecasting |
| 36 | Deal governance | Deal Risk Analysis & Approval Agent | 📅 | CFO + Opportunity Tracker |
| 37 | Quality governance | Quality Metrics & Escalation Tracking Agent | 📅 | — |
| 38 | Knowledge management | Institutional Knowledge Capture Agent | 📅 | — |
| 39 | IP creation | IP Creation & Acceleration Pipeline Agent | 📅 | — |
| 40 | Corporate services (SLA'd internal orgs) | Corporate Service Level Validator | 📅 | — |
| 41 | Governance cadence | Governance Cadence & Calendar Agent | 📅 | Executive Signal Agent |
| 42 | 2030 headcount objective (1,500 / 2×) | 2030 Target Tracking & Growth Engine Agent | 📅 | CEO/FY Progress Agent |
| 43 | 2× growth engine infrastructure | Growth Infrastructure Validator | 📅 | CEO/FY Progress Agent |
| 44 | The Enterprise Test (10 questions) | Enterprise Test Gating Agent | 📅 | Executive Signal Agent |
| 45 | The 30-Day CEO Test | 30-Day Resilience Validator | 📅 | Executive Signal Agent |
| 46 | The Leadership Contract | Leadership Behavior Validator | 📅 | Executive Signal Agent |
| 47 | New management philosophy (system-dependent) | Management Philosophy Enforcer | 🔄 | Flash Orchestration Engine |
| 48 | Troy / AXION Principal | AXION Principal Accountability Monitor | 📅 | BU Outcome Accountability Agent |
| 49 | Curtis / PRISM Principal | PRISM Principal Accountability Monitor | 📅 | BU Outcome Accountability Agent |
| 50 | Hemant / AXION Offshore Leader | AXION Offshore Execution Monitor | 📅 | — |
| 51 | Manian / PRISM Offshore Leader | PRISM Offshore Execution Monitor | 📅 | — |
| 52 | Workforce management (shared, BU-bounded) | Workforce Management Policy Enforcer | 🔄 | Resource Mgmt Agent |
| 53 | What this means for every employee | Employee Development & Clarity Agent | 📅 | HR Agent |
| 54 | The final architecture | Architecture Validator | 📅 | Executive Signal Agent |
| 55 | The end state (vision) | End State Validator | 📅 | Executive Signal Agent |
| 56 | Operating principles / BlitzenX standard | Operating Principle Enforcer | 🔄 | Flash + Executive Signal |

**Rollup:** ✅ 5 sections done (17, 19, 26 partial, 47 partial, 56 partial) · 🔄 6 in progress (3, 4, 11, 20, 23, 24) · 📅 45 pending.

### Blocking dependencies

- Phase 4 (HR) needs: CFO Agent stable (cost tracking) + Resource Management Agent stable (allocation decisions)
- Phase 5 (Risk & Quality) needs: Financial Controls complete + Resource Management complete
- Phase 6 (Strategy) needs: Phase 1-5 operational + 30-Day CEO test defined
- Phase 7 (Knowledge) needs: Phase 4 HR agents operational

---

## 8. Development Roadmap

### Phase 0: Foundation — ✅ Complete
Agent logging utility (`app/utils/agent_logger.py`), agent registry service, `agent_execution_log` model.

### Phase 1: Core Recruiting — ✅ Complete
Recruitment Agent (S-001), Supervisor Agent (S-066), Thunder (S-067), HTD Pipeline Agent (S-066), Flash Orchestration Engine (S-066).

### Phase 2: Financial Controls — 🔄 In Progress
- [x] CFO Agent (financial snapshot + metrics)
- [ ] CEO/FY Progress Agent, Partner ROI Agent, Opportunity Tracker Agent, Capital Allocation Validator, BU P&L Tracker

### Phase 3: Resource Management — 🔄 In Progress
- [x] Resource Management Agent, Core-Pull Conflict Agent
- [ ] Workforce Forecasting Agent, SPECIALTY Capacity Optimizer, CORE Deployment Orchestrator, CORE Certification Evidence Tracker

### Phase 4: HR & Talent — ❌ Not Started
HR Agent, Onboarding Agent, Buddy Program Agent, Employee Milestone Agent, KPI Agent, Employee Mental Health Agent, Leadership Intelligence Agent, Succession Planning Agent, New Hire Entry Gating Agent.

### Phase 5: Risk & Quality — ❌ Not Started
Quality Metrics Agent, Risk Detection & Escalation Agent, Deal Risk Analysis Agent, 30-Day Resilience Validator, Enterprise Test Gating Agent.

### Phase 6: Strategy & Governance — ❌ Not Started
CEO Decision Authority Validator, BU Principal Accountability Monitor (both BUs), Leadership Behavior Validator, Governance Cadence Agent, 2030 Target Tracking Agent, Growth Infrastructure Validator, Management Philosophy Enforcer.

### Phase 7: Knowledge & IP — ❌ Not Started
Institutional Knowledge Capture Agent, IP Creation Pipeline Agent, Corporate Service Level Validator.

### Phase 8: Engagement — ❌ Not Started (lower priority)
Outreach, Interview Reminder, Interview Confirmation, Abandonment Scoring, Compensation Scoring, Desire Intelligence.

### Phase 9: Support — ❌ Not Started (lower priority)
Activity Feed, Daily Digest, Executive Signal, Culture Agent.

### Phase 10: Boundary Enforcement — ❌ Not Started
Client-Resource Relationship Agent, Account Ownership Manager, Strategic Account Governance Agent, Tenant Isolation Agent, BU Scoping Agent, Cross-BU Borrowing Prevention Agent, Workforce Management Policy Enforcer.

### Phase 11: Alignment & Validation — ❌ Not Started
Architecture Validator, Operating Principle Enforcer, End State Validator.

### Near-term task list (from the original Phase 2/3 session plan)
1. Wire logging to all 20 agents still missing it (Resource, Finance, Engagement, Decision, Support tiers)
2. Implement the 3 missing agents in full: KPI, HR, Employee Mental Health
3. Create the API routes still missing (Core-Pull, Buddy, Milestone, Engagement tier, Decision tier)
4. Agent sub-task orchestration framework (Recruitment → Screening/Interview/Offer; Resource Mgmt → Skill Matching/Allocation/Deployment; Finance → Cost Tracking/Invoice/Payroll)
5. Weekly gift/recognition system backend
6. Error recovery & resilience layer

---

## 9. Operating Model Alignment — non-negotiables for every agent

1. **No cross-BU resource borrowing** — each BU owns its CORE resources
2. **SPECIALTY monetizes capacity** — BXIN corporate revenue (125% of org cost target)
3. **BU autonomy with enterprise governance** — Principals own outcomes
4. **Institutional over personal** — the system owns decisions, not individual CEOs
5. **Excellence-based motivation** — 99.9999% success target, recognition over fear (see also the "Agent State Dashboard" in Section 5, which was explicitly redesigned from a fear/threat framing to an excellence/recognition framing per Avinash's direction — the underlying fear-score *math* is unchanged, only its presentation and stated philosophy)

> **The final principle:** Employees create value. Systems preserve value. AI multiplies value. IP captures value. The goal is not to replace humans — it's an organization where specialized agents make the org smarter, faster, more predictable, and less dependent on any individual, including the CEO.
