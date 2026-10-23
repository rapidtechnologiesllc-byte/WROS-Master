# Flash Chat: Goal Setting by Role

**Critical Feature:** Each role can chat with Flash to set goals for their team/individuals.

## 🔒 CONFIDENTIALITY REQUIREMENT (CRITICAL)

**Flash Chat is STRICTLY CONFIDENTIAL.** Never share one person's conversation with another.

### What's Private
- ✅ My chat with Flash (only I see it)
- ✅ My goals/targets (only I see them until cascaded)
- ✅ My progress/challenges (only I and my manager see)
- ✅ My conversations about blockers (never shared)

### What's NOT Private (Cascaded Upward Only)
- ✅ My cascaded goals (my manager sees when activated)
- ✅ My progress vs goal (my manager sees results)
- ✅ Aggregated team metrics (manager's manager sees consolidated)
- ✅ CEO sees only company-level metrics, not personal conversations

### Database Level Security
```sql
-- Chat messages are NEVER cross-visible
SELECT * FROM flash_chat_messages WHERE user_id = 'person-A'
-- Returns only person-A's messages, not person-B's, even if same manager

-- Permissions table enforces scope
chat_messages.user_id (who initiated chat)
chat_messages.visibility_scope (private, manager_only, team_only, company_only)
```

### API Security (HIERARCHICAL ACCESS ONLY)

```
GET /flash/chat/{chat_id}
  Requires: 
    - auth_user_id == chat.user_id (own chat), OR
    - auth_user_id is in chat.user's direct reporting chain
  Rejects: 
    - If you're not the person who started the chat AND
    - If you're not in their direct reporting chain (manager/director/etc.)
  
Example:
  Tech Lead A's chat: Only A can see it
  Manager A (A's manager): Cannot see A's personal chat
  Manager B (different team): Cannot see A's chat
  CEO A (if A reports up to CEO A): Cannot see A's personal chat
  
GET /flash/chat/history
  Returns: ONLY current user's chats
  Filters: Only chats from their direct team (if manager)
  Never: Sibling chains (Manager B cannot see Manager A's team chats)
  
GET /flash/dashboards/{user_id}
  Requires: 
    - auth_user_id == user_id (own dashboard), OR
    - user_id is in auth_user's reporting chain (your direct report)
  Rejects:
    - Manager A cannot see Manager B's dashboard (different branch)
    - CEO B cannot see CEO A's division
    - Sibling managers cannot see each other's teams

Database Enforcement:
  SELECT * FROM flash_reports WHERE visible_to_user_id = 'ceo_a'
    Returns: Only cascaded reports from CEO A's division
    Never: Reports from CEO B's division
    
  SELECT * FROM flash_chat WHERE visible_to_user_id = 'manager_a'
    Returns: ONLY Manager A's own chats
    Never: Manager B's chats (even if same CEO)
    Never: Tech Lead A's personal chats (only their goals)
```

### Chain of Command Verification
```python
def can_see_user_data(requesting_user_id, target_user_id):
    """Check if requesting_user can see target_user's data"""
    
    # Can always see your own
    if requesting_user_id == target_user_id:
        return True
    
    # Check if target_user is in requesting_user's reporting chain
    def is_in_chain(target, requester):
        current = target.manager_id
        while current:
            if current == requester:
                return True  # Found requester in chain
            current = db.get_user(current).manager_id
        return False
    
    if is_in_chain(target_user_id, requesting_user_id):
        return True  # Requester is in target's hierarchy
    
    return False  # Sibling, different division, no access
```

### Example: What Each Person Sees (HIERARCHICAL ONLY)

**Tech Lead A chats with Flash:**
```
A: "I'm struggling with performance. Need help hitting 500 commits."
Flash: "What's blocking you? Design review? Tech debt? Unclear priorities?"
A: "Waiting on design review. Also need better dev environment."
```
**ONLY A sees this conversation.**
- Manager A CANNOT see this chat (it's A's private conversation)
- Tech Lead B CANNOT see this chat (it's not their chain of command)
- CEO CANNOT see this chat (only cascaded results)

**Manager A (A's manager) chats with Flash:**
```
Manager A: "My team is at 87/150 consultants. What's the blocker?"
Flash: "Team members cite: Design review delays, unclear priorities, tech debt"
```
**Manager A sees this.** Their manager sees RESULT but not this chat.
- Manager B CANNOT see this (different chain of command)
- Tech Lead B CANNOT see this (not in reporting line)
- CEO only sees aggregated metrics from their direct reports

**Manager A's Manager (Director A - reporting to CEO A) chats with Flash:**
```
Director A: "How's my org tracking?"
Flash: "3 teams: Team-A on pace, Team-B slight lag, Team-C critical lag"
```
**Director A sees this. CEO A sees results only.**
- Director B (different division) CANNOT see this
- CEO B (different org) CANNOT see this

**CEO A (only sees their direct reports) chats with Flash:**
```
CEO A: "How's my division tracking?"
Flash: "Workforce: 87/150 (on pace). Sales: 2/5 logos (slight lag). Partners: consolidated views"
```
**CEO A sees ONLY their division's cascaded metrics.**
- CEO B (different company/division) sees NOTHING from CEO A's organization
- Manager A (direct report to CEO A) is visible to CEO A
- Manager B (reports to different CEO) is completely hidden from CEO A

### Access Control by Hierarchy

```
CEO A
├─ Sees: Their direct reports + cascaded data from direct reports only
├─ Cannot see: CEO B's organization, CEO B's division, CEO B's metrics
├─ Cannot see: Manager A's personal chat with Flash
└─ Can see: Aggregated results from Manager A's team

CEO B (Different Division)
├─ Sees: Their direct reports + cascaded data from their division only
├─ Cannot see: CEO A's organization, any of CEO A's data
├─ Completely siloed from CEO A

Manager A (Reports to CEO A)
├─ Sees: Their team members' cascaded goals + results
├─ Cannot see: Manager B's team (even if same CEO A)
├─ Cannot see: Their team members' personal chats with Flash
└─ Sees: Aggregated team-level metrics

Manager B (Reports to CEO A)
├─ Cannot see: Manager A's team or data
├─ Cannot see: CEO A's view or other managers' teams
├─ Sees: Only their own team
└─ Cannot see: Other managers' conversations

Tech Lead A (Reports to Manager A)
├─ Sees: Their own chat with Flash (private)
├─ Cannot see: Tech Lead B's chat (even if same manager/team)
├─ Cannot see: Manager A's chat or aggregated view
└─ Their manager sees: Cascaded goals only
```

### Implementation Rules

1. **Every chat message has a `visibility_scope`:**
   - `private`: Only the user who started the chat
   - `manager_only`: User + their direct manager
   - `team_only`: User + their team members
   - `company_only`: CEO + C-level (aggregated only)

2. **Flash never mentions names in responses to manager/director/CEO:**
   ```
   WRONG: "Tech Lead A is 50 commits behind..."
   RIGHT: "3 team members cite design review delays as primary blocker"
   ```

3. **Database rows include access control:**
   ```sql
   flash_chat_messages:
     - user_id (who initiated)
     - visibility_scope (private/manager_only/team_only/company_only)
     - can_view_user_ids (explicit access list)
   ```

4. **API enforces strict access:**
   ```python
   def get_chat_message(chat_id, requesting_user_id):
       msg = db.get(chat_id)
       if requesting_user_id == msg.user_id:
           return msg  # Own chat, full visibility
       elif requesting_user_id == msg.user.manager_id and msg.visibility_scope >= manager_only:
           return sanitized(msg)  # Manager sees aggregated, not personal details
       else:
           raise 403 Forbidden  # No access
   ```

5. **Audit log tracks all access:**
   ```sql
   chat_access_log:
     - chat_id
     - accessed_by_user_id
     - timestamp
     - reason (own_chat / manager_review / audit)
   ```

### What This Protects
- ✅ Tech Lead A's struggles are not visible to Tech Lead B
- ✅ Manager A's team challenges not visible to Manager B
- ✅ CEO can't see individual conversations, only aggregates
- ✅ Prevents competitive disclosure ("Manager B's team is struggling")
- ✅ Protects vulnerable sharing (health issues, struggles, risks)

### Violation Examples (All Prevented)

❌ Manager A sees Tech Lead B's chat: `403 Forbidden`
❌ Tech Lead A sees Tech Lead B's goals: `403 Forbidden`
❌ CEO sees Manager A's coaching from Flash: `403 Forbidden`
❌ Partner sees another Partner's chat: `403 Forbidden`

### Reporting Exception (Data Protection)
Only HR + CEO can access aggregated anonymized data for compliance:
```
"3 team members report design review as blocker"
NOT: "Tech Lead A, B, C report design review as blocker"
```

---

## User Flows by Role

### CEO Chats with Flash

```
CEO: "I want 150 consultants by EOY. Set that up."

Flash: "OK, setting 150-consultant annual goal.
Need to cascade to:
- Workforce Ops: 150 hires
- Partners: ~50 hires each (if 3 partners)
- BU Heads: ~16.67 each (if 9 BUs)

Should I proceed with equal division, or do you want custom splits?"

CEO: "Equal division is fine."

Flash: "Goal set. Cascading now. 
✓ Workforce Ops: 150/year (37.5/Q, 12.5/month)
✓ Partner A: 50/year (12.5/Q, 4.17/month)
✓ Partner B: 50/year
✓ Partner C: 50/year
✓ BU Heads 1-9: 16.67 each

All departments notified. Ready for first reports Friday."
```

### Partner Chats with Flash

```
Partner: "My 3 BUs need revenue targets. I have $5M annual goal."

Flash: "Got it. Your $5M → Split 3 ways = $1.67M per BU
- BU 1 (NYC): $1.67M/year (416K/month)
- BU 2 (London): $1.67M/year
- BU 3 (Singapore): $1.67M/year

Or should I weight by size? BU 1 is bigger than BUs 2&3."

Partner: "Weight it. NYC is 50%, others 25% each."

Flash: "Revised:
- BU 1 (NYC): $2.5M/year (50% of $5M)
- BU 2 (London): $1.25M/year (25% of $5M)
- BU 3 (Singapore): $1.25M/year (25% of $5M)

Setting targets now. All BU heads notified."
```

### BU Head Chats with Flash

```
BU Head: "Set utilization target for my team. What's realistic?"

Flash: "Industry benchmark for services: 70-80% billable utilization
Your team: 12 consultants
Current month: 65% utilization (8/12 billable)

Recommend 75% target (9 billable/month)?

Or set custom: ___% "

BU Head: "75% works. Set for full year."

Flash: "Setting 75% utilization target.
Annual: 75% (9 people billable)
Monthly: 75% (9 people)
Weekly: 75% (9 people)
Daily: 75% (9 people)

Team notified. Will track weekly."
```

### Manager Chats with Flash

```
Manager: "My 3 engineers need sprint velocity targets."

Flash: "Current sprint velocity: 45 points (last 4 weeks average)
Team size: 3 engineers

Recommend maintaining 45 points/sprint, or increase to 50?"

Manager: "Increase to 50 to push momentum."

Flash: "Setting 50 points/sprint target (annual equivalent: 2,600 points)
- Quarterly: 650 points
- Monthly: 217 points
- Weekly: 50 points (per sprint)
- Daily: 7 points

Engineers notified. Tracking starts next sprint."
```

### Tech Lead Chats with Flash

```
Tech Lead: "What's a good commit target for me annually?"

Flash: "Looking at your history:
- Last 52 weeks: 420 commits
- Average: 8/week

Recommend 450-500/year (aggressive growth)?
Or maintain ~420?"

Tech Lead: "Go for 500. Want to improve."

Flash: "Setting 500 commits/year target.
- Quarterly: 125 commits
- Monthly: 42 commits
- Weekly: 10 commits
- Daily: 1.4 commits

That's up from your current 8/week. Doable with focus.
Flash will alert me if I slip behind pace."
```

### Individual Contributor Chats with Flash

```
Recruiter: "How many hires should I aim for this year?"

Flash: "Team target: 150 hires/year
Your role: Recruiter (1 of 4 on team)
Fair split: ~37.5 hires/person

But your close rate is higher than team average (65% vs 55%).
Suggest: 40 hires? Accounts for your strength."

Recruiter: "40 hires. Let's do it."

Flash: "Your target: 40 hires/year
- Quarterly: 10 hires
- Monthly: 3.3 hires
- Weekly: 0.77 hires
- Daily: 0.11 hires (roughly 1 every 9 days)

You'll feed into team target (150 total). Progress tracked."
```

---

## Chat Interface Architecture

### Flash Chat Window (Sidebar)
```
┌─────────────────────────────┐
│ FLASH CHAT                  │
│ Goal Setting & Guidance     │
├─────────────────────────────┤
│                             │
│ Flash: "What can I help    │
│ you set up today?"          │
│                             │
│ You: [Type here...]         │
│                             │
│ [Submit Button]             │
│                             │
│ Recent Chats:               │
│ • Set 150-hire goal         │
│ • Review Q3 targets         │
│ • Get 2027 recommendation   │
│                             │
└─────────────────────────────┘
```

### Chat Messages

**Flash Proposes:**
```
"Your team is at 87/150 consultants (week 33).
Current pace: ~160 hires for year (12% short).
Recommend: Increase hiring to 2.8/week (from 2.4)?
Or keep at 2.4 and adjust target to 140?"
```

**User Responds:**
```
"Keep the 150 target. I'll increase hiring."
```

**Flash Confirms:**
```
"✓ Target: 150 hires/year (no change)
✓ Pace increased to 2.8/week (was 2.4)
✓ You need 32 more hires by EOY (66 in remaining 23 weeks)

This is achievable. Good call.
I'll track weekly and alert if pace drops below 2.5."
```

---

## API Endpoints for Flash Chat

### 1. Start Chat Session
```
POST /flash/chat/start
{
  "user_id": "CEO",
  "context": "goal_setting",
  "scope": "ceo_level"  // who are they setting goals for?
}
```

Response:
```json
{
  "chat_id": "chat-12345",
  "initial_message": "What can I help you set up today?",
  "suggested_actions": [
    "Set annual goal",
    "Review existing targets",
    "Get recommendations",
    "Cascade goals to team"
  ]
}
```

### 2. Send Message
```
POST /flash/chat/{chat_id}/message
{
  "message": "I want 150 consultants by EOY"
}
```

Response:
```json
{
  "response": "OK, setting 150-consultant annual goal. Need to cascade to: Workforce Ops: 150 hires, Partners: ~50 each, BU Heads: ~16.67 each. Should I proceed with equal division, or custom splits?",
  "options": [
    "Equal division",
    "Custom splits",
    "Let me think"
  ],
  "proposed_cascade": {
    "workforce_ops": 150,
    "partners": [50, 50, 50],
    "bu_heads": [16.67, 16.67, ...]
  }
}
```

### 3. Confirm Action
```
POST /flash/chat/{chat_id}/confirm
{
  "action": "cascade_goals",
  "details": {
    "goal": "150_consultants",
    "cascade_method": "equal_division",
    "activate": true
  }
}
```

Response:
```json
{
  "status": "success",
  "message": "Goals cascaded to all departments",
  "cascaded_to": {
    "workforce_ops": 150,
    "partners": 3,
    "bu_heads": 9
  },
  "notifications_sent": 12
}
```

---

## Chat Features

### Auto-Completion
- "Set 150 consultants" → Flash auto-calculates cascades
- "My team's velocity" → Flash looks up current metrics
- "Revenue targets" → Flash knows org revenue goal

### Recommendations
- "What's a good hire target?" → Flash analyzes capacity
- "Should I increase to 200?" → Flash checks feasibility
- "Is 75% utilization realistic?" → Flash benchmarks against industry

### Conflict Detection
- "Set my BU revenue to $2M" but CEO set Partner target at $5M for 3 BUs → Flash alerts: "That's higher than your fair share"
- "Hire 100 people" but company annual target is 150 → Flash: "That's 67% of team target. Feasible?"

### Real-Time Feedback
```
Manager: "50 points/sprint for my team"
Flash: "That's 2,600/year. 
Your team did 2,400 last year (45/sprint).
Growth: +8% 
Feasibility: HIGH"
```

---

## Conversation Flows by Persona

### CEO
**Goal:** Set strategic targets
**Flash Role:** Propose cascades, validate math, recommend targets

Conversation:
1. CEO states goal ("150 consultants")
2. Flash proposes cascade ("50 each partner", "16.67 each BU")
3. CEO adjusts if needed ("weight by size")
4. Flash recalculates
5. CEO confirms ("set it up")
6. Flash activates and notifies departments

### Partner
**Goal:** Set BU targets from their portion
**Flash Role:** Distribute partner goal to BUs, offer weighting

Conversation:
1. Partner states their allocation ("$5M for my 3 BUs")
2. Flash proposes equal split ("$1.67M each")
3. Partner adjusts ("weight by size")
4. Flash recalculates and asks for weights
5. Partner confirms weights ("50% / 25% / 25%")
6. Flash sets per-BU targets

### Manager
**Goal:** Set team velocity/hiring targets
**Flash Role:** Recommend based on history, track achievements

Conversation:
1. Manager asks ("what velocity target?")
2. Flash analyzes ("you did 45 last 4 weeks, industry is 50")
3. Manager chooses ("set to 50")
4. Flash calculates cascades ("50/sprint = 2,600/year")
5. Flash confirms ("team will be notified")

### Individual
**Goal:** Understand personal contribution to team goal
**Flash Role:** Calculate fair share, explain trajectory

Conversation:
1. Person asks ("how many hires should I do?")
2. Flash calculates ("150 team target / 4 recruiters = 37.5")
3. Flash adjusts for ability ("your rate is higher, so 40")
4. Person agrees
5. Flash tracks progress weekly

---

## Implementation Phases

### Phase 1 (NOW)
- [ ] Chat interface stub (empty chat window in sidebar)
- [ ] Flash responds with predefined messages
- [ ] CEO can trigger goal setting via chat

### Phase 2 (NEXT)
- [ ] Flash autonomously calculates cascades
- [ ] Partners, BU Heads can chat to set their targets
- [ ] Recommendations based on historical data

### Phase 3
- [ ] Team members (manager, individual) can set personal targets
- [ ] Conflict detection (goal exceeds parent's allocation)
- [ ] Real-time feasibility analysis

### Phase 4
- [ ] Full autonomy: Flash chats without confirmation needed
- [ ] Multi-turn conversations (Flash asks clarifying questions)
- [ ] Learning from past conversations

---

## Why This Matters

**Before:**
- CEO sets goal manually in form
- CEO navigates to separate "Goals" screen
- CEO fills out 4 separate goal fields
- CEO clicks "Save"
- 6 other people do same manually
= 30+ clicks, fragmented experience

**After:**
- CEO types: "I want 150 consultants"
- Flash: "Setting it up for the org"
- Flash cascades automatically
- Everyone notified, ready to go
= 1 message, unified experience

---

## Quick Start

Add Flash Chat to every screen:
1. Sidebar always shows Flash Chat
2. Pre-populate with user's role ("CEO", "Partner A", "Manager", etc.)
3. Suggest actions based on role ("Set goals", "Review progress", "Get help")
4. Submit message → Flash responds with options/confirmations

**Implementation time:** 2-3 hours (chat UI + Flash integration)

