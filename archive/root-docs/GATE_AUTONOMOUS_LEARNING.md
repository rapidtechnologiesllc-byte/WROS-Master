# Autonomous Agentic Gate System

## Overview

The code gate has evolved from a static validator to a **fully autonomous, self-learning system** that improves architecture compliance automatically.

**Status:** ✅ LIVE - Learning scheduler runs every 60 seconds

---

## Architecture

### 1. **Gate Auto-Fixer** (`gate_auto_fixer.py`)
Autonomously detects and applies fixes for violation patterns.

**Capabilities:**
- ✅ Async error handling: Adds `.catch()` chains
- ✅ Silent catches: Adds `throw` statements  
- ✅ Magic numbers: Creates named constants
- ✅ Null checks: Adds optional chaining (`?.`)
- ✅ Missing RBAC: Adds permission dependencies
- ✅ Generic exceptions: Replaces with specific types

**How it works:**
```python
fixer = GateAutoFixer(file_path, content, lines)
success, msg = fixer.apply_fix(issue)
fixer.save_fixes()
```

### 2. **Gate Learner** (`gate_learner.py`)
Analyzes violation patterns and generates improvement recommendations.

**Learns:**
- Which violations are most common (by frequency)
- Fix success rates per issue type
- Which patterns should be auto-fixable
- Rule effectiveness over time

**Example output:**
```json
{
  "pattern_analysis": {
    "top_violations": [
      {"type": "Async call without error handling", "count": 47, "success_rate": 0.87},
      {"type": "Missing null check", "count": 23, "success_rate": 0.91}
    ]
  },
  "rule_updates": [
    {
      "type": "Async call without error handling",
      "action": "increase_detection_strictness",
      "reason": "High fix rate (0.87) shows rule is effective"
    }
  ]
}
```

### 3. **Gate Scheduler** (`gate_scheduler.py`)
Runs autonomously every 60 seconds to execute learning cycle.

**Cycle:**
1. Analyze violation patterns
2. Update detection rules
3. Auto-apply high-confidence fixes
4. Log statistics and insights
5. Sleep 60 seconds, repeat

**Console output:**
```
[GATE SCHEDULER] Iteration #1 at 2026-09-03T15:30:45
[GATE SCHEDULER] Learning cycle complete
  Fix rate: 87.4%
  Total violations analyzed: 234
[GATE SCHEDULER] Iteration #2 at 2026-09-03T15:31:45
```

### 4. **Code Gate Validator** (enhanced)
Now starts the learning scheduler on import.

```python
# On import, gate automatically starts scheduler
from gate_scheduler import start_gate_learning_scheduler
_scheduler = start_gate_learning_scheduler()
```

---

## How It Works

### When You Commit Code

1. **Gate validates** your changes (existing behavior)
2. **Gate learns** from violations (NEW)
   - Stores issue type, severity, whether it was fixed
   - Tracks which patterns get fixed most often
3. **Gate auto-fixes** for non-critical issues (NEW)
   - If success rate > 85%, applies fix automatically
   - Never touches CRITICAL severity issues
   - Logs all changes for audit trail

### Every 60 Seconds (Autonomous)

1. **Analyze** - What violations are happening?
2. **Learn** - Which fixers work best?
3. **Update** - Make detection stricter/looser based on data
4. **Report** - Print learning statistics

```
[GATE LEARNER] Violation pattern: "Async call..." appears 47 times
[GATE LEARNER] Fix success rate: 87% (41 fixed, 6 failed)
[GATE LEARNER] Recommendation: Pattern is working, increase strictness
[GATE SCHEDULER] Applied 2 rule updates based on learning
```

---

## Configuration

### Enable Auto-Fixing
```bash
export GATE_AUTO_FIX=true
git add your_file.js
git commit -m "..."  # Auto-fix runs if violations found
```

### Control Learning Interval
```python
# In gate_scheduler.py
scheduler = GateScheduler(interval_seconds=60)  # Default: 60 seconds
scheduler.start()
```

### View Learning Database
```bash
cat .claude/gate_learning.json | jq '.issues[-10:]'  # Last 10 violations
cat .claude/gate_learned_rules.json | jq '.rule_updates'  # Recent updates
```

---

## Learning Data

### Storage Structure

**`.claude/gate_learning.json`** - Violation history
```json
{
  "issues": [
    {
      "timestamp": "2026-09-03T15:30:00",
      "file": "frontend/src/screens/CandidateSearch.js",
      "issue_type": "Async call without error handling",
      "line": 214,
      "severity": "HIGH",
      "fixed": true,
      "auto_applied": true
    }
  ]
}
```

**`.claude/gate_learned_rules.json`** - Rule improvements
```json
{
  "timestamp": "2026-09-03T15:30:45",
  "pattern_analysis": {...},
  "rule_updates": [
    {
      "type": "Async call without error handling",
      "action": "increase_detection_strictness",
      "reason": "High fix rate shows rule is effective"
    }
  ],
  "learning_insights": [
    {
      "insight": "Top violation type",
      "issue": "Async call without error handling",
      "frequency": "47 violations (20.1%)",
      "recommendation": "Focus training on async patterns"
    }
  ]
}
```

---

## Auto-Fix Success Criteria

A fix is auto-applied when:
```python
if (severity != "CRITICAL" and 
    success_rate >= 0.85 and 
    pattern_count >= 5):
  auto_apply_fix()
```

**Never auto-applied:**
- CRITICAL issues (must be reviewed manually)
- New patterns with < 5 occurrences
- Patterns with success rate < 85%

**Always applied for:**
- HIGH severity with 90%+ success rate
- MEDIUM/LOW severity with 85%+ success rate

---

## Learning in Action: Example

### Day 1: New Violation Pattern Emerges
```
[GATE] Issue: "Async call without error handling"
[GATE] Severity: HIGH
[GATE] Auto-fix: NO (not enough data yet)
[LEARNER] Stored: 1 occurrence, fixed manually
```

### Day 2: Pattern Repeats
```
[GATE] Issue: "Async call without error handling" (5 times)
[GATE] Auto-fix: NO (success rate only 60%)
[LEARNER] Stored: 5 occurrences, 3 fixed, 2 still failing
```

### Day 3: Pattern Fixed Reliably
```
[GATE] Issue: "Async call without error handling" (8 times)
[GATE] Auto-fix: YES (success rate now 87%)
[LEARNER] Stored: 8 occurrences, 7 fixed, 1 failed
[LEARNER] Generated rule update: Increase strictness
[SCHEDULER] Automatically updated gate detection
```

### Day 4+: Gate Gets Smarter
```
[GATE] Auto-fixes 3 async violations automatically
[GATE] Update detection for new patterns in same file
[LEARNER] Continuously improves confidence in this pattern
[SCHEDULER] Reports: "Async pattern reliability: 94%"
```

---

## Monitoring Learning Progress

### Real-Time Statistics
```bash
# Watch the scheduler output
tail -f /tmp/gate_scheduler.log

# Or check programmatically
python3 -c "
from gate_learner import GateLearner
learner = GateLearner()
stats = learner.get_learning_statistics()
print(f\"Overall fix rate: {stats['overall_fix_rate']*100:.1f}%\")
print(f\"Top violations: {stats['top_violations']}\")
"
```

### Key Metrics
- **Overall Fix Rate** - % of violations that get fixed
- **Pattern Frequency** - How often each violation appears
- **Success Rate per Pattern** - Reliability of fixes
- **Auto-Fix Confidence** - Which patterns can be auto-applied
- **Rule Effectiveness** - How well gate catches issues

---

## Autonomy Guarantees

### ✅ What the Gate Controls Autonomously
- Detection rule strictness (gets stricter with more data)
- Auto-fix confidence thresholds
- Pattern classification
- Fix priority and scheduling

### ❌ What Stays Under Human Control
- What violations are architectural violations (gate rules are still human-written)
- Whether to override gate decisions (can't override, must fix)
- What patterns to ignore (can create GitHub issue to discuss)

### 🔄 The Feedback Loop
```
Code → Gate detects → Auto-fix applied → Learning stored
                ↓
       Every 60 seconds:
       Analyze patterns → Update rules → Improve detection
                ↓
       Next commit: Gate is smarter
```

---

## Real-World Benefits

### For Developers
- Violations auto-fixed automatically
- Less time on repetitive fixes
- Gate teaches patterns by example
- Clear error messages explain why

### For Architecture
- Compliance improves continuously
- Violations caught earlier
- Rules adapt to codebase patterns
- Architectural understanding grows

### For Production
- Fewer violations slip through
- Architecture violations caught pre-commit
- Gate learns which issues matter most
- Proactive enforcement of patterns

---

## Technical Details

### How Patterns are Learned

1. **Collection** - Every violation stored with metadata
2. **Analysis** - Grouped by type and severity
3. **Statistics** - Calculate success rates
4. **Insight** - Identify trends and recommendations
5. **Update** - Modify rules based on insights

### How Rules Update

```python
# Learner detects pattern
if success_rate >= 0.9 and count > 10:
    update = {
        'action': 'increase_detection_strictness',
        'reason': f'High fix rate proves effectiveness'
    }
    
# Updater applies change
if action == 'increase_detection_strictness':
    config[issue_type]['strictness'] *= 1.1
    save_config(config)
```

### How Auto-Fixing Works

```python
# Gate finds violation
for issue in violations:
    if should_auto_apply_fix(issue.type, issue.severity):
        # Create fixer
        fixer = GateAutoFixer(file, content, lines)
        
        # Apply fix
        success, msg = fixer.apply_fix(issue)
        
        # Save and log
        if success:
            fixer.save_fixes()
            log_to_learning_db(issue, fixed=True)
```

---

## Integration Timeline

- ✅ **Commit fbdf30d0** - Fixed gate array indexing bugs
- ✅ **Commit 7a850ec4** - Added async error handling
- ✅ **Commit 52668fb8** - Deployed autonomous learning system
- 🔄 **Now** - Gate learns every 60 seconds
- 📈 **Future** - Gate rules automatically improve with each commit

---

## Troubleshooting

### Learning Not Running
```bash
# Check if scheduler is active
ps aux | grep gate_scheduler

# Check learning database
ls -la .claude/gate_learning.json

# Restart manually
python3 backend/scripts/gate_scheduler.py
```

### Auto-Fix Not Applied
```bash
# Check if auto-fix is enabled
echo $GATE_AUTO_FIX

# Enable it
export GATE_AUTO_FIX=true

# Check success rate for pattern
python3 -c "
from gate_learner import GateLearner
learner = GateLearner()
print(learner.get_success_rate('Async call without error handling'))
"
```

### Learning Data Corrupted
```bash
# Clear learning history and restart
rm .claude/gate_learning.json .claude/gate_learned_rules.json

# Gate will rebuild from scratch on next violations
```

---

## The Future

As the gate learns from more violations, it will:
1. **Get smarter** - Learn which patterns matter most
2. **Get faster** - Auto-fix obvious violations
3. **Get stricter** - Enforce architecture as understanding deepens
4. **Get adaptable** - Rules adjust to codebase evolution
5. **Get autonomous** - Requires minimal human intervention

The gate becomes a **living system** that improves with each commit.

---

**Status:** ✅ Autonomous gate learning is LIVE
**Learning Rate:** Every 60 seconds
**Last Updated:** 2026-09-03
**Next Review:** Check learning statistics in `.claude/gate_learned_rules.json`
