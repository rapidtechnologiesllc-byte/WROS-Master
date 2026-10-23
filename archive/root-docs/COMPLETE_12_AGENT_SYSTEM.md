# Complete 12-Agent System: From LinkedIn to Deployed

## The Full Hiring Lifecycle

```
TIER 1: SOURCING (Passive Candidates from LinkedIn)
  LinkedIn Profile Scanner → LinkedIn Extractor → Profile-to-Contact Converter
  
         ↓ (Engagement reached)
         
TIER 2: ENGAGEMENT (Active Pipeline - Ready Now)
  Thunder (Contact) → Recruiter Screener → Interview Scheduler
  → Panel → Offer Generator → Thunder (Negotiate) → HR → Onboarding → Resource Manager
  
         ↓ (Deployed)
         ✓ ON PROJECT - Revenue Generating
         
ALTERNATIVE PATH: NOTICE PERIOD
  Offer Accepted (with 90-day notice) → Notice Period Manager 
  → Onboarding Prep (starts day 80) → Start Date Scheduler → Deployment Ready
  → Resource Manager → On Project
```

---

## The 12 Agents (Complete System)

### SOURCING TIER (3 agents)

#### 1. LinkedIn Profile Scanner
**Purpose:** Find passive candidates
**Input:** Job title, skills, location (e.g., "Python engineer in San Francisco")
**Process:** 
- Query LinkedIn API for profiles
- Filter by seniority, skills, location
- Identify high-match passive candidates
**Output:** LinkedIn profile URLs (500+ per batch)
**Queue:** Scanner_Input
**Conversion Target:** 500 profiles/day → LinkedIn extraction

#### 2. LinkedIn Profile Extractor
**Purpose:** Extract data from LinkedIn profiles
**Input:** LinkedIn profile URLs
**Process:**
- Scrape: name, email, phone (if available), current company, role, skills, location
- Extract personal intelligence data (hobbies, interests, travel)
- Calculate match score (0-1) to open job
**Output:** Candidate profile data (name, email, skills, match score)
**Queue:** Extractor_Input, Extractor_Output
**Conversion Target:** 80% profiles successfully extracted

#### 3. Profile-to-Contact Converter
**Purpose:** Convert LinkedIn profiles into actionable contacts
**Input:** Extracted profile data
**Process:**
- Verify email address (real + active)
- Check if person already in candidate DB
- Create contact record (if new)
- Score engagement likelihood (passive candidate warmth)
**Output:** Contact ready for outreach
**Queue:** Converter_Input, Converter_Output
**Conversion Target:** 60% profiles become active contacts → Thunder input queue

### ACTIVE PIPELINE TIER (8 agents - Already Built)

#### 4-11. Thunder, Screener, Scheduler, Panel, Offer Gen, Negotiation, HR, Onboarding, Resource Manager
(Exactly as before - for candidates ready to join immediately)

### NOTICE PERIOD TIER (1 agent)

#### 12. Notice Period Manager
**Purpose:** Handle candidates with offer but long notice (30/60/90 days)
**Input:** Offer accepted but with future start date
**Process:**
- Calculate start date: offer_date + notice_period
- Schedule onboarding prep (starts 80% through notice period)
- Auto-trigger onboarding workflow at day 80
- Coordinate with manager for team assignment
- Track candidate engagement during notice period
**Output:** Scheduled start date, prep tasks assigned
**Queue:** NoticeManager_Input
**Conversion Target:** 100% (all accepted offers with notices)
**Special Cases:**
- 30-day notice: Onboarding prep starts day 24
- 60-day notice: Onboarding prep starts day 48  
- 90-day notice: Onboarding prep starts day 72

---

## Complete Message Queue Architecture

```
SOURCING PIPELINE:
LinkedIn_Scanner_Input (50 job titles)
    ↓
LinkedIn_Extractor_Input (500 profiles)
    ↓
Profile_Converter_Input (400 extracted profiles)
    ↓
Active_Engagement_Input ← converts to Thunder's input queue (if verified)
    ↓
Profile_Warm_List ← or add to nurture list (if no email/passive)

ACTIVE PIPELINE (8 agents):
Thunder_Input → Recruitment_Input → InterviewScheduler_Input → 
HiringPanel_Input → OfferGenerator_Input → ThunderNegotiation_Input →
HR_Input → Onboarding_Input → ResourceMgmt_Input

NOTICE PERIOD PIPELINE:
NoticeManager_Input (offers with start dates >today)
    ↓
OnboardingPrep_Input (day 80 of notice period) ← triggers auto-transition
    ↓
Onboarding_Input ← joins main onboarding pipeline
    ↓
ResourceMgmt_Input
    ↓
Deployed
```

---

## Daily Execution (Full 12-Agent System)

```
CYCLE: SOURCING (4 hours)
  Scanner: Scan LinkedIn for 50 job titles → 500 profiles discovered
  Extractor: Extract 500 profiles → 400 extracted successfully (80%)
  Converter: Convert 400 extracted → 240 verified emails (60%)
  
  Result: 240 new passive candidates identified, added to nurture list
  
CYCLE: ACTIVE PIPELINE (8 hours)
  Thunder: Process 240 new profiles + 10 existing warm leads = 250 contacts
    → 190 engaged (76%)
  Screener: Screen 190 engaged → 76 qualified (40%)
  Scheduler: Schedule 76 qualified → 46 interviews (60%)
  Panel: Interview 46 → 46 scores (100%)
  Offer Gen: Create 23 offers (50%)
  Negotiation: 23 offers → 18 accepted (78%)
  HR: 18 accepted → 18 employee accounts
  Onboarding: 18 onboarded → 17 complete (95%)
  Resource: 17 deployed (100%)
  
  Result: 17 new hires deployed today
  
CYCLE: NOTICE PERIOD MANAGEMENT (1 hour)
  NoticeManager: Check all pending offers with notice periods
    - 5 candidates at day 75 (5 days to onboarding prep) → flag upcoming
    - 3 candidates at day 80 (onboarding prep starts today) → trigger prep
    - 2 candidates at day 89 (1 day to start date) → confirm everything ready
  
  Result: 3 candidates enter onboarding prep, 2 ready for tomorrow's start
  
DAILY OUTCOME:
- 17 new deployments (active pipeline)
- 3 entering onboarding (from notice period)
- 240 passive leads identified (sourcing)
- 23 offers in negotiation
- 46 interviews scheduled

Monthly (22 work days):
- 374 new hires (17 × 22)
- Plus notice period people joining 30-90 days after offer
- Passive lead pipeline: 5,280 new profiles/month

Annual (250 work days):
- 4,250 hires from active pipeline
- Plus notice-period joiners throughout year
- 132,000 passive profiles identified/evaluated
- Expected hires: 4,250+ (MASSIVELY exceeds 2,000 by 2030 target)
```

---

## Key Integration Points

### Sourcing → Active Pipeline
**When:** Profile converted + email verified + engagement score calculated
**Action:** Put on Thunder_Input queue
**Key:** Only add to active queue if warm (engagement score >0.5)
**Cold profiles:** Go to nurture list (reach out later when warmed up)

### Active Pipeline → Notice Period Handler
**When:** Offer accepted AND start_date > today
**Action:** Put on NoticeManager_Input queue
**Key:** Don't put on HR_Input yet - let Notice Manager handle timing
**Trigger:** On day 80 of notice period, auto-move to Onboarding_Input

### Notice Period → Onboarding
**When:** 90-day notice nearing completion (day 85)
**Action:** Trigger onboarding workflow
**Key:** Onboarding starts before they quit current job (preparation)
**Result:** On start date, they're already set up and ready

---

## The Magic Numbers

### Sourcing Funnel Conversion
```
500 LinkedIn profiles identified
  ↓ 80% extraction success
400 profiles extracted
  ↓ 60% email verified
240 passive candidates created
  ↓ 76% engagement rate (Thunder outreach)
190 engaged candidates
  ↓ 40% qualification rate
76 qualified candidates
  ↓ 50% interview → offer conversion
38 offers to passive candidates
  ↓ 78% offer acceptance
30 passive candidates accept offers with notice
  ↓ + their notice periods (30-90 days)
Staggered joining over next 90 days
```

### Compare: Active vs Passive Funnels

| Metric | Active Candidates | Passive Candidates |
|--------|------------------|-------------------|
| Source | Job board, referrals | LinkedIn scan |
| Engagement rate | 76% | 55% (harder to reach) |
| Qualified rate | 40% | 35% |
| Interview rate | 60% | 50% |
| Offer acceptance | 80% | 78% |
| Notice period | 0-14 days | 30-90 days |
| Final hire rate | 10% of contacts | 3-4% of contacts |

**But:** Passive candidates are higher quality (employed, specialized skills)

---

## Queue Monitoring (12-Agent System)

### Daily Status Check

```
GET /pipeline/status (Extended)

Queue Depths:
  SOURCING:
  - LinkedIn_Scanner_Input: 50 (job titles to scan)
  - LinkedIn_Extractor_Input: 500 (profiles to extract)
  - Profile_Converter_Input: 400 (extracted to verify)
  - Active_Engagement_Input: 240 (ready for Thunder)
  
  ACTIVE PIPELINE:
  - Thunder_Input: 250 (candidates to contact)
  - Recruitment_Input: 190 (engaged to screen)
  - InterviewScheduler_Input: 76 (qualified to schedule)
  - HiringPanel_Input: 46 (interviews to conduct)
  - OfferGenerator_Input: 23 (interview scores to offer)
  - ThunderNegotiation_Input: 23 (offers to negotiate)
  - HR_Input: 18 (accepted to create employee account)
  - Onboarding_Input: 17 (new employees to onboard)
  - ResourceMgmt_Input: 0 (all deployed)
  
  NOTICE PERIOD:
  - NoticeManager_Input: 12 (offers with notice periods)
  
Bottlenecks:
  - None today ✓

Recommendations:
  - Increase LinkedIn scanning (demand > supply)
  - All other queues flowing well
```

---

## Implementation Roadmap

### Phase 1 (Week 1): Deploy Active Pipeline ✓ DONE
- 8-agent system (Thunder → Deployed)
- Message queue monitoring
- Orchestration working

### Phase 2 (Week 2): Add Sourcing
- LinkedIn Scanner Agent
- LinkedIn Extractor Agent  
- Profile-to-Contact Converter Agent
- Wire to active pipeline

### Phase 3 (Week 3): Add Notice Period Handler
- Notice Period Manager Agent
- Schedule onboarding prep (day 80)
- Auto-trigger to main onboarding

### Phase 4 (Week 4): Optimize & Monitor
- Tune sourcing volume
- Monitor notice-period flow
- Scale all queues

---

## The Scale Path to 2,000

**Month 1-2 (Ramp up sourcing):**
- Active pipeline: 17/day × 44 days = 748 hires
- Notice period joiners: ~50 (from early offers)
- Total: 800 employees

**Month 3-6:**
- Active pipeline: 20/day × 88 days = 1,760 hires (scaling)
- Notice period joiners: ~200
- Total: 2,760 employees

**Month 7-12:**
- Normalize at 20/day
- Total new hires: ~2,000

**Result: Hit 2,000 by end of 2026 (4.5 months)**

---

## What This Requires

### Sourcing Agents (3)
- LinkedIn Profile Scanner
- LinkedIn Extractor  
- Profile-to-Contact Converter

### Active Pipeline Agents (8)
- ✓ Already built

### Notice Period Agent (1)
- Notice Period Manager

### Infrastructure
- ✓ Message queue system (exists)
- ✓ Orchestrator (Flash - built)
- ✓ Dashboard (monitoring - built)

---

## The Bottom Line

**8 agents = active hiring (people ready to join now)**
**+3 agents = passive sourcing (LinkedIn candidates)**  
**+1 agent = notice period management (future starts)**

**= 12 agents handling complete hiring lifecycle**

With this system:
- Passive candidates: 240/day discovered
- Active pipeline: 250/day processed  
- Notice period: 12-20/day managed
- **Daily deployment: 17-20 people**
- **Monthly deployment: 374-440 people**
- **Annual deployment: 4,500+ people**
- **Path to 2,000: 5 months** (not 4 years)

You don't need 75 agents.
You need 12 agents + message queues + monitoring.
This gets you 2,000 by 2030 by **month 5**.
