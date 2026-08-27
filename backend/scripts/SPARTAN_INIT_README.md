# Spartan System Initialization

Complete guide to initializing the autonomous organism's decision-making infrastructure.

## Overview

The Spartan system requires three components to operate:

1. **Organization Hierarchy** - Who reports to whom, decision authority levels
2. **System Policies** - Guardrails that the system enforces (margin floor, utilization ceiling, etc.)
3. **Forecasting Engine** - Predicts resource/client/revenue needs and escalates

This guide covers initialization steps 1 and 2. Step 3 (Forecasting) is launched via API.

---

## Prerequisites

Before running initialization scripts, ensure:

- ✅ Backend database is created and migrated
- ✅ Users exist with roles assigned (CEO, CFO, CWP, Partners, BU Heads, etc.)
- ✅ BusinessUnits exist
- ✅ Multi-role support initialized (user_roles junction table populated)

Check:
```bash
psql -U postgres -d wros_dev -c "SELECT COUNT(*) FROM users;"
psql -U postgres -d wros_dev -c "SELECT COUNT(*) FROM business_units;"
psql -U postgres -d wros_dev -c "SELECT COUNT(*) FROM user_roles;"
```

---

## Quick Start (Recommended)

Run all initialization in one command:

```bash
cd backend
python scripts/init_spartan_system.py
```

This runs:
1. Organization hierarchy initialization
2. System policies initialization

**Expected output:**
```
✓ ALL INITIALIZATION STEPS COMPLETED SUCCESSFULLY

Spartan System is now ready to operate:
  • Organization hierarchy established
  • Decision policies enforced
  • Escalation chains active
  • Forecasting system enabled
```

---

## Individual Scripts

### 1. Organization Hierarchy Initialization

```bash
python scripts/init_org_hierarchy.py
```

**What it does:**
- Queries existing Users and their assigned roles
- Infers organizational hierarchy from role assignments
- Creates OrgNode records with proper reporting chains

**Hierarchy created:**
```
CEO (Level 0, authority: BOARD)
├─ Partner #1 (Level 1, authority: DIVISION)
│   ├─ VP Engineering (Level 2)
│   ├─ BU Head (Level 2)
│   │   ├─ Workforce Ops Manager (Level 3, dual: BU Head + CWP)
│   │   │   └─ Hiring Manager (Level 4)
│   │   ├─ Delivery Manager (Level 3)
│   │   └─ Finance Manager (Level 3)
│   └─ Account Managers (Level 3)
├─ Partner #2, #N (same structure)
├─ CFO (Level 1, org-wide policy enforcer)
└─ CWP (Level 1, org-wide policy enforcer)
```

**Escalation chains created:**
- **Delivery:** BU Head → Partner → CEO
- **Recruitment:** Hiring Manager → Workforce Ops Manager → CWP/Partner → CEO
- **Finance:** Finance Manager → Partner (or CFO for policies) → CEO
- **VP Engineering:** Engineering Lead → VP Eng → Partner → CEO

**Key features:**
- Auto-discovers roles from Users table
- Handles multi-role assignments
- Creates dual-reporting for Workforce Ops Manager (BU Head + CWP)
- Generates decision domains based on role hierarchy

### 2. System Policies Initialization

```bash
python scripts/init_policies.py
```

**What it does:**
- Seeds 13 core system policies
- Each policy has a rule type, value, and override authority
- Policies are enforced by AutonomousForecastingService and DoctorAgentDaemon

**Policies created:**

**Finance (3):**
- MARGIN_FLOOR: 30% minimum margin (override: CFO)
- STRATEGIC_CLIENT_MARGIN: 20% minimum for Fortune 500
- COST_PER_FTE: $250K/year maximum per employee

**Resources (2):**
- UTILIZATION_CEILING: 85% maximum utilization (override: Partner)
- DEMAND_FULFILLMENT: 90% minimum fulfillment rate

**Delivery (2):**
- MAX_DELIVERY_DELAY: 14-day maximum delay (override: Partner)
- SLA_BREACH_THRESHOLD: 5% maximum SLA breaches

**Recruitment (3):**
- HIRING_PACE: Must keep up with demand
- TIME_TO_HIRE: 45-day maximum from offer to start
- OFFER_ACCEPTANCE_RATE: 75% minimum acceptance

**Acquisition (3):**
- RUNWAY_MINIMUM: 6+ months cash required (cannot override - existential)
- QUARTERLY_REVENUE_TARGET: $4M/quarter minimum
- NEW_CLIENT_PACE: 1 client/2 weeks

**How policies work:**
```python
# When a human makes a decision, system validates:
decision = {"type": "APPROVE_PROPOSAL", "margin_percent": 25}
validation = validate_decision_against_policy(decision, user_id)

# If violates policy:
if validation.status == "POLICY_VIOLATION":
    # System returns:
    {
        "violations": [{"policy": "MARGIN_FLOOR", "required": "30%", "your_value": "25%"}],
        "allow_override": True,
        "requires_justification": True,
        "recommendation": "❌ DECISION REJECTED - Violates margin floor"
    }
    # Human can:
    # A) Adjust decision to comply
    # B) Override with justification (logged in DecisionLog for audit)
```

---

## Database Schema

### OrgNode Table

Stores organizational hierarchy:

```sql
CREATE TABLE org_nodes (
    id UUID PRIMARY KEY,
    name VARCHAR(255),
    node_type VARCHAR(50),        -- PERSON, ROLE, DEPARTMENT
    user_id UUID FK → Users.UserID,
    parent_node_id UUID FK → OrgNode.id,  -- Who this person reports to
    hierarchy_level INTEGER,       -- 0=CEO, 1=C-level, 2=VP, 3=BU Head, 4=Manager
    authority_level VARCHAR(50),   -- INDIVIDUAL, TEAM, DEPARTMENT, DIVISION, EXECUTIVE, BOARD
    decision_domains VARCHAR(500), -- CSV: HIRING, BUDGET, PRICING, TIMELINE, SCOPE, POLICY
    business_unit_id UUID FK,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### DecisionPolicy Table

Stores system policies:

```sql
CREATE TABLE decision_policies (
    id UUID PRIMARY KEY,
    policy_name VARCHAR(255),           -- MARGIN_FLOOR, UTILIZATION_CEILING, etc.
    policy_domain VARCHAR(50),          -- PRICING, UTILIZATION, HIRING, TIMELINE
    phalanx VARCHAR(50),                -- finance, resources, recruitment, delivery, acquisition
    rule_type VARCHAR(50),              -- FLOOR, CEILING, MANDATORY, FORBIDDEN
    rule_value VARCHAR(255),            -- "30%", "$250K", "85%", etc.
    condition VARCHAR(500),             -- Description of when rule applies
    can_override BOOLEAN,               -- Can humans override this policy?
    override_authority VARCHAR(50),     -- CFO, Partner, CEO, CWP, etc.
    override_justification_required BOOLEAN,
    is_active BOOLEAN,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### DecisionLog Table

Logs all autonomous and human decisions:

```sql
CREATE TABLE decision_logs (
    id UUID PRIMARY KEY,
    decision_type VARCHAR(50),          -- APPROVE_PROPOSAL, HIRE, TIMELINE, etc.
    decision_domain VARCHAR(50),        -- PRICING, HIRING, TIMELINE, BUDGET
    phalanx VARCHAR(50),
    decided_by UUID FK → OrgNode.id,
    decision_maker_type VARCHAR(20),    -- SYSTEM or HUMAN
    decision VARCHAR(255),              -- APPROVED, REJECTED, OVERRIDDEN
    parameters VARCHAR(1000),           -- JSON of decision params
    justification VARCHAR(2000),        -- Why the decision was made
    policy_violated BOOLEAN,            -- Did this decision violate a policy?
    violated_policy_id UUID FK,
    override_approved BOOLEAN,          -- Was violation approved?
    decided_at TIMESTAMP
);
```

---

## Integration Points

### 1. AutonomousForecastingService

When forecasting detects a gap:

```python
# Recruitment falls behind
forecast = forecast_recruitment_needs(db)
if forecast['gap_analysis']['status'] == 'CRITICAL':
    # Get manager to contact from OrgNode hierarchy
    vp_eng_node = get_org_node(hierarchy_level=2, authority_level='EXECUTIVE')
    # Send alert to VP Engineering
    alert = generate_autonomous_alert_to_human(
        alert_type="KPI_FALLEN",
        content=forecast,
        escalate_to_node_id=vp_eng_node.id
    )
```

### 2. DoctorAgentDaemon Escalation

When an agent fails:

```python
# Agent fails (strike 3)
# Query escalation path from OrgNode
agent_owner = get_org_node(user_id=agent.owner_user_id)
escalation_chain = get_escalation_chain(agent_owner)
# Follow chain: BU Head → Partner → CEO
escalate_to_next_level(escalation_chain)
```

### 3. StrategicConsul Decision Making

When executives resolve escalations:

```python
# Partner decides on delivery issue
# System logs decision in DecisionLog
log_decision(
    decision_type="TIMELINE_ADJUSTMENT",
    decided_by=partner_org_node.id,
    decision_maker_type="HUMAN",
    decision="APPROVED",
    policy_violated=False  # or True if they violated SLA policy
)
```

### 4. Forecasting Dashboard

Frontend displays org hierarchy in escalation chains:

```javascript
// Display who decision escalates to
const escalationChain = [
  { level: 4, name: "Hiring Manager" },
  { level: 3, name: "Workforce Ops Manager" },
  { level: 2, name: "BU Head" },
  { level: 1, name: "Partner" },
  { level: 0, name: "CEO" }
];

// Show in MessageQueueDashboard → Forecasting tab
// User sees: "Hiring gap escalates to: Workforce Ops Manager → Partner → CEO"
```

---

## Verification

After running initialization:

### Check Org Hierarchy

```bash
psql -U postgres -d wros_dev << EOF
SELECT 
  o.name, 
  o.hierarchy_level,
  o.authority_level,
  p.name as "reports_to"
FROM org_nodes o
LEFT JOIN org_nodes p ON o.parent_node_id = p.id
ORDER BY o.hierarchy_level, o.name;
EOF
```

Expected output:
```
      name      | hierarchy_level | authority_level |  reports_to
─────────────────────────────────────────────────────────────────
 CEO             |               0 | BOARD           |
 CFO             |               1 | EXECUTIVE       | CEO
 CWP             |               1 | EXECUTIVE       | CEO
 Partner A       |               1 | DIVISION        | CEO
 VP Engineering  |               2 | EXECUTIVE       | Partner A
 BU Head A       |               2 | DIVISION        | Partner A
 Workforce Ops   |               3 | TEAM            | BU Head A
```

### Check Policies

```bash
psql -U postgres -d wros_dev << EOF
SELECT policy_name, rule_type, rule_value, override_authority
FROM decision_policies
ORDER BY phalanx, policy_name;
EOF
```

Expected output:
```
       policy_name       | rule_type | rule_value | override_authority
──────────────────────────────────────────────────────────────────────
 COST_PER_FTE            | CEILING   | $250,000   | CFO
 MARGIN_FLOOR            | FLOOR     | 30%        | CFO
 STRATEGIC_CLIENT_MARGIN | FLOOR     | 20%        | CFO
 DEMAND_FULFILLMENT      | FLOOR     | 90%        | PARTNER
 UTILIZATION_CEILING     | CEILING   | 85%        | PARTNER
...
```

---

## Testing the System

### Test 1: Forecasting Escalation

```bash
curl -X POST http://localhost:8080/spartan/forecasting/recruitment/forecast

# Should return forecast with escalation_node = "VP_ENGINEERING"
# System knows to escalate to VP Eng based on org hierarchy
```

### Test 2: Policy Validation

```bash
curl -X POST http://localhost:8080/spartan/forecasting/decision/validate \
  -H "Content-Type: application/json" \
  -d '{
    "decision_type": "APPROVE_PROPOSAL",
    "parameters": {"margin_percent": 25},
    "decision_maker_id": "cfo-user-id"
  }'

# Should return POLICY_VIOLATION because 25% < 30% floor
# System blocks proposal, requires override with justification
```

### Test 3: Escalation Chain

```bash
# Query org hierarchy to verify reporting chain
SELECT * FROM org_nodes 
WHERE user_id = 'hiring-manager-user-id';

# Should show:
# - parent_node_id points to Workforce Ops Manager
# - Which points to BU Head
# - Which points to Partner
# - Which points to CEO
```

---

## Troubleshooting

### "No CEO found in system"

**Problem:** init_org_hierarchy.py failed because no CEO user exists

**Solution:**
```bash
# Create CEO user first
INSERT INTO users (UserID, UserEmail, UserName, permission_role, business_unit_id)
VALUES (
  gen_random_uuid(),
  'ceo@company.com',
  'CEO',
  'CEO',
  (SELECT id FROM business_units LIMIT 1)
);

# Then re-run init script
python scripts/init_org_hierarchy.py
```

### "No users found with this role"

**Problem:** Users exist but don't have roles assigned

**Solution:**
```bash
# Check UserRoles table
SELECT u.UserName, rt.role_name
FROM user_roles ur
JOIN users u ON ur.user_id = u.UserID
JOIN role_templates rt ON ur.role_id = rt.id;

# If empty, assign roles via user_roles junction table
INSERT INTO user_roles (user_id, role_id, business_unit_id)
VALUES (
  'user-uuid',
  (SELECT id FROM role_templates WHERE role_name = 'Partner'),
  'business-unit-uuid'
);
```

### "parent_node_id is NULL for Partner"

**Problem:** Partner's parent_node_id not set to CEO

**Solution:** This is correct - Partners report to CEO. If you need to change reporting, update manually:
```bash
UPDATE org_nodes
SET parent_node_id = (SELECT id FROM org_nodes WHERE name = 'CEO')
WHERE name = 'Partner A';
```

---

## Next Steps

After initialization:

1. **Verify in Dashboard:**
   - Start backend: `uvicorn app.main:app --reload --port 8080`
   - Open frontend dashboard
   - Navigate to: MessageQueueDashboard → Autonomous Forecasting tab
   - Should see forecasts with escalation nodes

2. **Test Escalations:**
   - Create a recruitment task
   - Lower KPI to trigger forecast
   - Verify escalation goes to VP Engineering (not hardcoded)

3. **Wire to Tasks:**
   - Update task escalation logic to query OrgNode
   - Replace hardcoded role checks with authority_level + decision_domains
   - Test end-to-end escalation chain

4. **Monitor Decisions:**
   - Watch DecisionLog for decision audit trail
   - Verify policy violations are tracked
   - Review overrides with justifications

---

## References

- [Spartan Architecture](../SPARTAN_AUTONOMOUS_FORECASTING_COMPLETE.md)
- [OrgNode Model](../app/models/org_hierarchy.py)
- [AutonomousForecastingService](../app/services/autonomous_forecasting_service.py)
- [Forecasting API](../app/api/v1/endpoints/spartan_forecasting.py)

