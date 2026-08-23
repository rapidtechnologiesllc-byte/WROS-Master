# Goal Cascading Specification

**Overview:** CEO sets strategic goals. System automatically cascades to all departments. 10X efficiency improvement over manual goal-setting per department.

---

## Design Principle

**Before:** 
- CEO sets goals
- Workforce Ops manually sets "150 hires"
- Sales manually sets "$15M revenue"
- Partners manually set "$5M each"
- BU Heads manually set their revenue
- Disconnect between CEO strategy and operational targets

**After:**
- CEO sets: "150 consultants, $15M revenue, 5 logos"
- System auto-cascades to Workforce Ops, Sales, Partners, BU Heads
- Everyone sees their piece of the CEO's constraint
- Perfect alignment from CEO → CFO → Directors → Individual Contributors

---

## Database Schema

### Table: `strategic_goals` (CEO Level)

```sql
CREATE TABLE strategic_goals (
    id UUID PRIMARY KEY,
    tenant_id INT NOT NULL,
    goal_name VARCHAR(100),  -- e.g., "Total Consultants", "Annual Revenue"
    goal_type VARCHAR(50),   -- "headcount" | "revenue" | "logos" | "partnership"
    current_value DECIMAL(18,2),
    target_value DECIMAL(18,2),
    unit VARCHAR(20),        -- "people", "$", "logos", "partnership"
    year INT,                -- 2026, 2027, etc.
    set_by_user_id VARCHAR(36),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);
```

### Table: `cascaded_goals` (Department Level - Auto-Generated)

```sql
CREATE TABLE cascaded_goals (
    id UUID PRIMARY KEY,
    strategic_goal_id UUID NOT NULL,  -- Parent CEO goal
    department VARCHAR(50),            -- "workforce_ops", "sales", "partner", "bu_head"
    annual_target DECIMAL(18,2),
    quarterly_target DECIMAL(18,2),
    monthly_target DECIMAL(18,2),
    weekly_target DECIMAL(18,2),
    daily_target DECIMAL(18,2),
    current_progress DECIMAL(18,2),
    scope_id VARCHAR(36),  -- Partner ID if partner-level, BU ID if BU-level
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    auto_generated BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (strategic_goal_id) REFERENCES strategic_goals(id)
);
```

---

## API Endpoints

### 1. Create/Update CEO Strategic Goal (Auto-Cascades)

```http
POST /goals/strategic
Content-Type: application/json

{
  "goal_name": "Total Consultants",
  "goal_type": "headcount",
  "target_value": 150,
  "unit": "people",
  "year": 2026,
  "cascade_rules": {
    "workforce_ops": {
      "formula": "direct_assignment",  
      "target": 150
    },
    "partner": {
      "formula": "divide_equal",
      "count": 3,
      "target_per": 50
    },
    "bu_head": {
      "formula": "divide_equal", 
      "count": 9,
      "target_per": 16.67
    }
  }
}
```

**Response:**
```json
{
  "strategic_goal_id": "goal-123",
  "goal_name": "Total Consultants",
  "target": 150,
  "cascaded_to": {
    "workforce_ops": [
      {
        "cascaded_goal_id": "dept-goal-001",
        "department": "workforce_ops",
        "annual_target": 150,
        "quarterly_target": 37.5,
        "monthly_target": 12.5,
        "weekly_target": 2.4,
        "daily_target": 0.34
      }
    ],
    "partner": [
      {
        "cascaded_goal_id": "partner-goal-001",
        "partner_id": "partner-A",
        "annual_target": 50,
        "quarterly_target": 12.5,
        "monthly_target": 4.17,
        "weekly_target": 0.96,
        "daily_target": 0.137
      },
      ...  // 3 partners total
    ]
  }
}
```

---

### 2. Get All CEO Strategic Goals

```http
GET /goals/strategic?year=2026
```

**Response:**
```json
{
  "goals": [
    {
      "id": "goal-consultants",
      "name": "Total Consultants",
      "type": "headcount",
      "current": 87,
      "target": 150,
      "unit": "people",
      "progress_pct": 58
    },
    {
      "id": "goal-revenue",
      "name": "Annual Revenue",
      "type": "revenue",
      "current": 3200000,
      "target": 15000000,
      "unit": "$",
      "progress_pct": 21
    },
    {
      "id": "goal-logos",
      "name": "Managed Services Logos",
      "type": "logos",
      "current": 2,
      "target": 5,
      "unit": "logos",
      "progress_pct": 40
    }
  ]
}
```

---

### 3. Get Cascaded Goals for a Department

```http
GET /goals/cascaded?department=workforce_ops&year=2026
```

**Response:**
```json
{
  "department": "workforce_ops",
  "cascaded_goals": [
    {
      "cascaded_goal_id": "cascade-001",
      "strategic_goal_name": "Total Consultants",
      "annual_target": 150,
      "quarterly_target": 37.5,
      "monthly_target": 12.5,
      "weekly_target": 2.4,
      "daily_target": 0.34,
      "current_progress": 87,
      "status": "ON_TRACK"
    }
  ]
}
```

---

### 4. Get Cascaded Goal for Specific Partner/BU

```http
GET /goals/cascaded/partner/partner-A?year=2026
```

**Response:**
```json
{
  "scope": "partner",
  "scope_id": "partner-A",
  "cascaded_goals": [
    {
      "cascaded_goal_id": "cascade-partner-001",
      "strategic_goal_name": "Annual Revenue",
      "annual_target": 5000000,
      "quarterly_target": 1250000,
      "monthly_target": 416667,
      "weekly_target": 96154,
      "daily_target": 13699,
      "current_progress": 3200000,
      "status": "SLIGHT_LAG"
    }
  ]
}
```

---

### 5. Update CEO Goal (Re-Cascades Automatically)

```http
PUT /goals/strategic/goal-consultants
Content-Type: application/json

{
  "target_value": 175,  // Changed from 150
  "cascade_rules": {
    "workforce_ops": {
      "formula": "direct_assignment",
      "target": 175
    },
    ...
  }
}
```

**Effect:**
- Updates strategic_goals table
- Recalculates all cascaded_goals automatically
- All department dashboards update in real-time
- Flash validation uses NEW targets for progress checks

---

### 6. Flash Validation Uses Cascaded Goals

When Flash validates a tech lead's report:

```python
# Flash gets the cascaded goal for Workforce Ops
goal = get_cascaded_goal("workforce_ops", year=2026)

# Example response from above:
# annual_target: 150
# weekly_target: 2.4
# current_progress: 87

# Tech Lead reports: 3 hires this week
current_progress_with_this_week = 87 + 3  # = 90

# Flash validation
variance = 90 - expected_by_this_week  # Compare to lifecycle pace
```

---

## Cascade Rules / Formulas

### Formula 1: Direct Assignment (1:1)
Used when one department owns the entire goal.

```
Formula: direct_assignment
Target Department: Workforce Ops
CEO Goal: 150 consultants
Result: Workforce Ops gets 150 hires target
```

### Formula 2: Equal Division
Used when goal is divided equally among N entities (e.g., 3 Partners, 9 BUs).

```
Formula: divide_equal
Count: 3 (three partners)
CEO Goal: $15M annual revenue
Result: Each Partner gets $5M ($15M / 3)

Breakdown: $1.25M/quarter, $416K/month, $96K/week, $13.7K/day
```

### Formula 3: Weighted Division (Future)
Used when divisions have different sizes/capacity.

```
Formula: divide_weighted
Weights: {
  "partner-A": 0.5,  // 50% of goal
  "partner-B": 0.3,  // 30% of goal
  "partner-C": 0.2   // 20% of goal
}
CEO Goal: $15M
Result: 
  Partner A: $7.5M
  Partner B: $4.5M
  Partner C: $3M
```

---

## Workflow Example: CEO Updates Goal

### Step 1: CEO Sets New Target
```
CEO Dashboard → Strategic Goals
Current: 150 consultants
Updated to: 175 consultants
Click: Save & Cascade
```

### Step 2: System Cascades

**Workforce Ops Auto-Updates:**
- Annual: 175 hires (was 150)
- Quarterly: 43.75 hires (was 37.5)
- Monthly: 14.58 hires (was 12.5)
- Weekly: 3.37 hires (was 2.4)
- Daily: 0.48 hires (was 0.34)

**All Workforce Ops reports now validate against NEW target (175, not 150)**

### Step 3: Flash Adjusts Coaching

**Tech Lead was at 87 hires (week 33):**

**Before (150 goal):**
- Expected week 33: ~42 hires
- Status: ON_TRACK (87 vs ~42)

**After (175 goal):**
- Expected week 33: ~49 hires  
- Status: SLIGHT_LAG (87 vs ~49)
- Flash updates: "You're still on pace for 160 hires, not 175. Need to accelerate to hit new target."

---

## Implementation Priority

### Phase 1 (MVP): Single-Level Cascade
- CEO sets goal
- System cascades to ONE department (Workforce Ops)
- Other departments get placeholders

### Phase 2: Multi-Department Cascade
- CEO goal cascades to Workforce, Sales, Partners, BU Heads
- Equal division formulas working
- Flash validation uses cascaded goals

### Phase 3: Weighted Division
- Custom allocation rules per department
- Different targets based on capacity
- Advanced admin UI for cascade rules

---

## Key Benefits

✅ **10X Efficiency**
- 1 CEO goal setting instead of 6 independent settings
- Auto-calculation of quarterly, monthly, weekly, daily

✅ **Perfect Alignment**
- Everyone sees their piece of CEO's vision
- No disconnect between strategy and operations

✅ **Dynamic Updates**
- CEO changes target from 150 → 175
- Cascaded goals update in real-time
- Flash validation immediately uses new targets

✅ **Flash Validation Accuracy**
- Flash compares against CEO-driven constraints
- Not arbitrary department targets
- Reflects actual organizational priorities

---

## Testing Scenarios

### Scenario 1: Initial Cascade
```
CEO sets: 150 consultants
Expected: Workforce Ops gets 150, Quarterly 37.5, Monthly 12.5, etc.
Verify: All cascaded goals calculated correctly
```

### Scenario 2: Update & Re-Cascade
```
CEO updates: 150 → 175 consultants
Expected: All cascaded goals recalculate (43.75/Q, 14.58/month, etc.)
Verify: Old reports still reference old targets, new reports use new targets
```

### Scenario 3: Flash Uses Cascaded Goal
```
Workforce Ops sees cascaded goal (150 hires)
Tech Lead reports: 3 hires
Flash compares: 87 + 3 = 90 actual vs expected weekly pace
Verify: Flash feedback references cascaded goal (150, not some other number)
```

---

## Notes

- **Backward Compat:** Old manually-set goals still work, but cascade goals take precedence
- **Audit Trail:** cascaded_goals tracks cascade_source, so you can see "generated from CEO goal X"
- **Real-time:** Updates cascade instantly; no delayed processing
- **Permissions:** Only CEO can set strategic goals; department heads can see cascaded targets but not edit them

