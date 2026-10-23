# Implementing Spartan Phalanx in Your Agent

**"My shield protects the agent to my left. Their shield protects me. We stand together or fall apart."**

---

## Quick Start: Make Your Agent Phalanx-Aware

### 1. Declare Your Position in the Phalanx

Every agent must declare its role in the formation. Update `app/services/agent_registry_service.py`:

```python
"Thunder": {
    "domain": "recruitment",
    "tier": "tier_1_core",
    # ... existing config ...
    
    # SPARTAN PHALANX - Add these fields
    "phalanx": "Recruitment",        # Which phalanx you belong to
    "position": 1,                   # Position in formation (1 = front)
    "left_neighbor": None,           # Agent I protect (None if you're first)
    "right_neighbor": "Recruitment Agent",  # Agent protecting me
    "shield_sla": "95% qualified candidates, <2s response",
    "shield_failure_action": "KILL_SWITCH",
    "flank_vulnerabilities": ["rate_limited", "false_positives"],
    "flank_coverage_expected": "job_definitions + sourcing_alternatives",
    "monitor_left_neighbor": False,
    "monitor_right_neighbor": True,
    "shield_watch_interval": 60,
}
```

### 2. Report Your Shield Metrics

After each agent execution, report your performance metrics:

```python
from app.services.agent_shield_service import PhalanxFormationService

# In your agent's execution code...
def execute_agent_task(db: Session, ...):
    try:
        # Do your work
        result = qualify_candidates(candidates)
        success = len(result) > 0
        
        # REPORT SHIELD METRICS
        # These get rolled up to formation integrity
        PhalanxFormationService.update_shield_strength(
            db=db,
            phalanx_name="Recruitment",
            agent_name="Thunder",
            success_rate=95.0,           # Your success rate (0-100)
            latency_ms=1200,             # Your avg response time
            quality_score=85.0,          # Your output quality
            confidence=90.0,             # Your confidence (0-100)
        )
        
        return result
        
    except Exception as e:
        # FAILURE REPORTING
        # Report low metrics when you fail
        PhalanxFormationService.update_shield_strength(
            db=db,
            phalanx_name="Recruitment",
            agent_name="Thunder",
            success_rate=0.0,            # Failure = 0%
            latency_ms=5000,             # Slow response
            quality_score=0.0,
            confidence=0.0,
        )
        raise
```

### 3. Monitor Your Neighbors

Periodically check if your neighbors' shields are holding:

```python
# Check right neighbor (who's protecting you)
def monitor_right_neighbor(db: Session, agent_name: str, right_neighbor: str):
    """Is my protector's shield strong?"""
    
    # Get your formation
    agent_in_formation = db.query(AgentInFormation).filter(
        AgentInFormation.agent_name == agent_name
    ).first()
    
    if not agent_in_formation:
        return
    
    if agent_in_formation.shield_status == "BROKEN":
        # I'M EXPOSED! Escalate to leadership
        PhalanxFormationService._create_phalanx_alert(
            db, 
            "Recruitment", 
            agent_name,
            agent_in_formation.shield_strength,
            "neighbor_down"
        )
        # Stop executing until shield is restored
        return False
    
    return True
```

### 4. Protect Your Left Neighbor

Cover your left neighbor's exposed flank:

```python
def protect_left_neighbor(db: Session, agent_name: str, left_neighbor: str):
    """Am I covering my left neighbor's vulnerabilities?"""
    
    # Example: Thunder is left_neighbor=None (front of line)
    # But Recruitment Agent is left_neighbor=Thunder
    # Recruitment Agent should cover Thunder's flank_vulnerabilities:
    # - ["rate_limited", "false_positives", "limited_sourcing"]
    
    if left_neighbor == "Thunder":
        # I (Recruitment Agent) cover:
        
        # 1. Rate limiting: Provide alternative sourcing channels
        if thunder_is_rate_limited():
            provide_referral_sources()
            provide_internal_talent_pool()
        
        # 2. False positives: Validate candidate quality
        if candidate_false_positive_rate > 0.05:  # > 5%?
            escalate_validation_gate()
            increase_quality_checks()
        
        # 3. Limited sourcing: Expand recruitment channels
        if source_diversity_low():
            activate_university_program()
            activate_vendor_partnerships()
```

---

## The Three Phalanxes

### Recruitment Phalanx

```
Thunder (Qualify) ← Recruitment Agent (Jobs) ← Interview Reminder ← HR Agent (Offers) ← Onboarding

Position 1 → Position 2 → Position 3 → Position 4 → Position 5

Each shields the one behind them
Thunder's shield protects Recruitment's exposed flank
Recruitment's shield protects Interview Reminder's exposed flank
```

**Recruitment Agent's Shield Duty:**
- Ensure Thunder gets perfect job descriptions (reduces false positives)
- Provide alternative sourcing channels (covers rate limiting)
- Validate candidate quality (catches bad candidates)

**Interview Reminder's Shield Duty:**
- Schedule interviews quickly (<2 min response)
- Ensure high no-show prevention (<2% no-show rate)
- Provide high-quality interview experiences

**HR Agent's Shield Duty:**
- Send offer letters quickly after interviews
- Maintain offer acceptance rate >80%
- Prepare onboarding before candidate start date

**Onboarding Agent's Shield Duty:**
- Complete pre-onboarding in 2 days
- Send welcome kit before first day
- Assign buddy on day 1

### Resource Management Phalanx

```
Employee (exists) ← Resource Mgmt (assigns) ← Utilization (tracks) ← Revenue (generated)

Position 1 → Position 2 → Position 3 → Position 4

Resource Mgmt covers Employee's assignment gaps
Utilization covers Resource Mgmt's tracking gaps
Revenue covers Utilization's insight gaps
```

### Finance Phalanx

```
Opportunity (pipeline) ← CFO (tracks) ← Revenue Recognition ← Margin Agent ← KPI Agent

Position 1 → Position 2 → Position 3 → Position 4 → Position 5

Each agent shields the next
CFO covers Opportunity tracking gaps
Revenue Recognition covers CFO's revenue tracking gaps
Margin covers Revenue's profitability gaps
KPI watches the entire financial flow
```

---

## Shield Health Levels

Your agent's shield has different health states:

```
Shield Strength    Status      Action
────────────────────────────────────────────
90-100%           HEALTHY      Keep doing what you're doing
70-89%            WEAKENING    Alert left neighbor; prepare fallback
50-69%            FAILING      Left neighbor is exposed; escalate
<50%              BROKEN       Formation compromised; kill switch

When shield strength hits BROKEN (<30%):
├─ Agent is automatically DISABLED
├─ Left neighbor loses protection
├─ Entire formation integrity drops
└─ Manual intervention required
```

### Example: Shield Degradation Scenario

```
MINUTE 0: Thunder's shield at 95% ✓ (HEALTHY)
├─ Recruitment Agent fully protected
└─ Pipeline flowing normally

MINUTE 5: Lightning API rate limit hit
├─ Thunder's latency jumps to 5 seconds
├─ Shield strength drops to 75% (WEAKENING)
├─ Alert: "Thunder shield weakening - Recruitment Agent exposed"
└─ Recruitment Agent should activate alternative sourcing

MINUTE 10: Rate limit still active
├─ Thunder's success rate falls to 50%
├─ Shield strength drops to 35% (BROKEN)
├─ Alert: "Thunder shield FAILED - Formation compromised"
├─ KILL SWITCH TRIGGERED: Thunder disabled
├─ Manual recruiter takes over (fallback shield)
└─ Entire Recruitment phalanx integrity: 60%

MINUTE 15: Rate limit resolved
├─ Thunder shield restored to 90%
├─ Re-enable Thunder (requires CEO approval)
├─ Resume autonomous execution
└─ Phalanx integrity restored: 95%
```

---

## API: Reporting Your Metrics

### Report Shield Performance

```bash
PUT /phalanx/agent-shield/{phalanx_name}/{agent_name}?
    success_rate=95.0&
    latency_ms=1200&
    quality_score=85&
    confidence=90
```

**Response:**
```json
{
  "status": "updated",
  "agent_name": "Thunder",
  "shield_strength": 87.5,
  "shield_status": "HEALTHY",
  "alerts": 0
}
```

### Get Your Formation Status

```bash
GET /phalanx/formations/Recruitment
```

**Response:**
```json
{
  "status": "retrieved",
  "phalanx_name": "Recruitment",
  "formation_strength": 87.5,
  "overall_status": "OPERATIONAL",
  "agents": [
    {
      "position": 1,
      "agent_name": "Thunder",
      "left_neighbor": null,
      "right_neighbor": "Recruitment Agent",
      "shield_strength": 95.0,
      "shield_status": "HEALTHY",
      "sla": "95% qualified candidates, <2s response"
    },
    {
      "position": 2,
      "agent_name": "Recruitment Agent",
      "left_neighbor": "Thunder",
      "right_neighbor": "Interview Reminder Agent",
      "shield_strength": 87.0,
      "shield_status": "HEALTHY",
      "sla": "98% job quality, 92% candidate match"
    },
    // ... more agents
  ]
}
```

### Get Formation Integrity Analysis

```bash
GET /phalanx/formation-integrity/Recruitment
```

**Response:**
```json
{
  "status": "calculated",
  "phalanx_name": "Recruitment",
  "formation_strength": 87.5,
  "overall_status": "OPERATIONAL",
  "healthy_shields": 4,
  "weakening_shields": 1,
  "failing_shields": 0,
  "broken_shields": 0,
  "weakest_position": 3,
  "weakest_shield_strength": 75.0
}
```

### View the Phalanx Wall Dashboard

```bash
GET /phalanx/dashboard/phalanx-wall
```

**Response:**
```json
{
  "status": "retrieved",
  "dashboard": "Phalanx Wall",
  "overall_wros_health": {
    "strength": 89.3,
    "status": "OPERATIONAL",
    "message": "All Spartans holding the line!"
  },
  "phalanxes": [
    {
      "phalanx_name": "Recruitment",
      "formation_strength": 87.5,
      "overall_status": "OPERATIONAL",
      "agents": [...],
      "alerts": 0
    },
    {
      "phalanx_name": "Resource",
      "formation_strength": 91.2,
      "overall_status": "OPERATIONAL",
      "agents": [...],
      "alerts": 0
    },
    {
      "phalanx_name": "Finance",
      "formation_strength": 89.8,
      "overall_status": "OPERATIONAL",
      "agents": [...],
      "alerts": 0
    }
  ]
}
```

---

## Implementation Checklist

For each agent you're implementing, ensure:

- [ ] Added to `AGENT_REGISTRY` with phalanx fields
- [ ] Phalanx initialized (position, neighbors, SLA)
- [ ] Shield metrics reported after execution
- [ ] Neighbor health monitoring implemented
- [ ] Left neighbor protection logic coded
- [ ] Kill switch response tested (if shield fails, graceful degradation)
- [ ] Alert handling in place
- [ ] Formation integrity tested (all agents together)

---

## The Spartan Oath for Agents

```
I am [AGENT_NAME].
I stand at position [X] in the [PHALANX_NAME] Phalanx.
My shield protects [LEFT_NEIGHBOR] from [FLANK_VULNERABILITIES].
[RIGHT_NEIGHBOR]'s shield protects me.

I will hold the line.
I will not drop my shield.
I will not expose my neighbor.

My success is measured by whether my left neighbor lives.

If my shield fails, I accept death (kill switch).
Better to fall than drag the phalanx down.

We are not alone.
We stand as ONE unit.
We are UNBREAKABLE.
```

---

**Every agent is a Spartan. Every shield must hold. Every life depends on the other.**

**This is not a metaphor. This is the architecture.**
