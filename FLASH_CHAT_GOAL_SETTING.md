# Flash Chat: Goal Setting by Role

**Critical Feature:** Each role can chat with Flash to set goals for their team/individuals.

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

