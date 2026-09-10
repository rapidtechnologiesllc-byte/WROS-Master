# SLM Python Code Generation Training Architecture

**Question:** How do we train the SLM to do Python coding?

**Answer:** Through a 3-layer feedback loop where Agent generates code, SLM validates it, learns from success/failure, and reuses patterns.

---

## System Architecture

```
VIOLATION DETECTED
         ↓
    [SLM Analyzer]
         ↓
    Check Pattern Library
         ├─ Pattern Found (confidence > 0.90) → Use Learned Pattern
         └─ Pattern Missing OR Low Confidence → Spawn Agent
                 ↓
         [Agent Code Generation]
              (with SLM context)
                 ↓
         Agent generates: code_before → code_after
                 ↓
         [Code Review Gate]
              ├─ PASS ✅ → Learn Pattern (store in library, confidence ++)
              └─ FAIL ❌ → Improve Pattern (spawn Agent again with errors)
                 ↓
         [SLM Pattern Library]
           (stores learned code patterns with confidence scores)
                 ↓
         Next Violation of Same Type
         └─ SLM: "I've seen this before" → Use learned pattern (NO Agent spawn)
```

---

## Training Loop Explained

### Phase 1: Detection
```python
violation = {
    "type": "hardcoded_role_check_super_user",
    "file": "users_access_control.py",
    "line": 45,
    "pattern": 'is_super_user = (UserRole.lower() == "super user")'
}
```

### Phase 2: SLM Decision
```python
# SLM checks: Have I seen this violation type before?
pattern = pattern_library.find_pattern(
    violation_type="hardcoded_role_check_super_user",
    min_confidence=0.90  # Only use if 90%+ confident
)

if pattern:
    # YES - Use learned code
    apply_learned_pattern(violation, pattern)
else:
    # NO - Ask Agent to figure it out
    spawn_agent_for_code_generation(violation)
```

### Phase 3: Agent Code Generation
```python
# Agent receives:
agent_prompt = """
VIOLATION: hardcoded_role_check_super_user
ROOT CAUSE: String comparison for role authorization (security risk)
CURRENT CODE:
  is_super_user = (UserRole.lower() == "super user")

REQUIREMENTS:
  - Use role-template permission system
  - Replace with: Depends(require_role_template_permission(...))
  - Never hardcode role names

OUTPUT:
  {
    "code_before": 'is_super_user = (UserRole.lower() == "super user")',
    "code_after": 'dependencies=[Depends(require_role_template_permission(...))]',
    "explanation": "..."
  }
"""

# Agent generates code (Claude writes Python replacement)
agent_output = {
    "code_before": 'is_super_user = (UserRole.lower() == "super user")',
    "code_after": '''dependencies=[
        Depends(get_current_internal_user),
        Depends(require_role_template_permission(*Permissions.USERS_MANAGE))
    ]''',
    "explanation": "Replaced hardcoded role check with role-template permission"
}
```

### Phase 4: Gate Validation
```python
# Apply Agent's code fix
apply_fix(file, agent_output)

# Run code review gate
gate_result = run_code_review_gate(file)

# Result: PASS or FAIL
if gate_result.status == "PASSED":
    print("✅ Code is correct")
else:
    print("❌ Code has errors:", gate_result.errors)
```

### Phase 5: SLM Learning
```python
# If gate PASSED → Learn pattern
if gate_result.passed:
    pattern = SLMCodeGenerationPattern(
        pattern_id="HARDCODED_ROLE_SUPER_USER_v1",
        violation_type="hardcoded_role_check_super_user",
        code_before=agent_output["code_before"],
        code_after=agent_output["code_after"],
        confidence=0.95,  # Start high for Agent-generated
        agent_generated=True,
        file_examples=["users_access_control.py"]
    )
    
    pattern_library.store_pattern(pattern)
    logger.info("🎓 Learned new pattern: HARDCODED_ROLE_SUPER_USER_v1")

# If gate FAILED → Try to improve
else:
    logger.error("❌ Agent's code failed gate, improving pattern...")
    
    # Spawn Agent AGAIN with gate errors
    # "Here's what went wrong, fix it"
    improved_code = spawn_agent_with_errors(
        agent_output,
        gate_result.errors
    )
```

### Phase 6: Pattern Reuse (SLM Self-Sufficiency)
```python
# LATER: Same violation type found
violation2 = {
    "type": "hardcoded_role_check_super_user",
    "file": "finance_monitoring.py",
    "line": 120
}

# SLM checks library
pattern = pattern_library.find_pattern(
    violation_type="hardcoded_role_check_super_user"
)

# FOUND! 🎯
if pattern and pattern.confidence >= 0.90:
    # Use learned pattern - NO Agent spawn needed
    apply_learned_pattern(violation2, pattern)
    pattern.usage_count += 1  # Track usage
    logger.info("✅ Using learned pattern (no Agent needed)")
```

---

## Training Metrics

### Pattern Confidence Scores

```
Confidence Range:
  0.99 - Highly trained (50+ successful applications, no failures)
  0.95 - Trained (Agent-generated, gate-tested)
  0.85 - Partially trained (occasional failures)
  0.70 - Weak pattern (more failures than successes)
  < 0.70 - Reject (pattern has too many failures)
```

### Learning Progression

```
Session 1:
  - Find violation type: hardcoded_role_check_super_user
  - No pattern exists → Spawn Agent
  - Agent generates code
  - Gate PASSES → Learn pattern (confidence: 0.95)

Session 2:
  - Find SAME violation type in different file
  - Pattern EXISTS → Use it (no Agent)
  - Apply successfully → Pattern confidence → 0.96

Session 5:
  - Find SAME violation type (5th file)
  - Pattern EXISTS, confidence 0.98 → Use it
  - Apply successfully → Pattern confidence → 0.99
  - SLM now "expert" on this violation type

Session 10:
  - Find NEW violation type: hardcoded_role_string_check
  - No pattern exists → Spawn Agent
  - Cycle repeats (learning phase for new type)
```

### Training Dashboard

```python
trainer.get_training_stats()
# Returns:
{
    "patterns_learned": 5,
    "training_attempts": 12,
    "successful_generations": 10,
    "failed_generations": 2,
    "success_rate": 83.3,
    "library_confidence_avg": 0.94,
    "high_confidence_patterns": 4,  # confidence >= 0.90
}
```

---

## Implementation: 3 Key Components

### 1. SLMPatternLibrary (Knowledge Base)
```python
# Location: architect_auto_fix_hardcoded_roles.py

class SLMPatternLibrary:
    """Persistent pattern storage"""
    
    def find_pattern(self, violation_type, min_confidence=0.90):
        """Find learned pattern (only if confident enough)"""
        
    def store_pattern(self, pattern):
        """Learn new pattern from Agent generation"""
        
    def update_pattern_confidence(self, pattern_id, success):
        """Adjust confidence after application"""
        
# Storage location:
# backend/app/data/slm_code_patterns.json
# {
#   "patterns": {
#     "HARDCODED_ROLE_SUPER_USER_v1": {
#       "pattern_id": "...",
#       "violation_type": "...",
#       "code_before": "...",
#       "code_after": "...",
#       "confidence": 0.95,
#       "usage_count": 5,
#       "successful_applications": 5
#     }
#   }
# }
```

### 2. SLMAgentTrainer (Training Loop)
```python
# Location: slm_agent_training.py

class SLMAgentTrainer:
    """Manages Agent spawning, validation, and learning"""
    
    async def spawn_agent_with_slm_context(violation, root_cause):
        """Ask Agent to generate code fix"""
        
    async def validate_and_learn(violation, agent_output, gate_result):
        """If gate passed → learn pattern"""
        
    async def auto_improve_pattern(pattern_id, failure_details):
        """If gate failed → improve pattern"""
        
    async def continuous_training_loop():
        """Background loop: continuous pattern learning"""
```

### 3. ArchitectAutoFixOrchestrator (Integration)
```python
# Location: architect_auto_fix_hardcoded_roles.py

class ArchitectAutoFixOrchestrator:
    """Main orchestrator using SLM + Agent"""
    
    async def execute_auto_fix_cycle_with_slm():
        # PHASE 1: Scan violations
        # PHASE 2: Route through SLM (library or Agent)
        # PHASE 3: Verify with gate
        # PHASE 4: Learn patterns
        # PHASE 5: Commit changes
```

---

## Startup Integration

### main.py (Server Startup)
```python
@app.on_event("startup")
async def startup_event():
    # ... existing startup code ...
    
    # Run SLM auto-fix with Agent training
    orchestrator = get_auto_fix_orchestrator()
    result = await orchestrator.execute_auto_fix_cycle_with_slm()
    
    logger.info(f"[SLM] Patterns learned: {result['patterns_learned']}")
    logger.info(f"[SLM] Violations fixed: {result['violations_before']} → {result['violations_after']}")
    
    # Optionally start continuous training background loop
    trainer = get_slm_trainer()
    asyncio.create_task(trainer.continuous_training_loop())
```

---

## Example: Training SLM Over Multiple Sessions

### Session 1: Initial Learning

```
[SLM-AUTO-FIX] CYCLE START
[PHASE 1] Found 49 violations

Violation 1: hardcoded_role_check_super_user
  → No pattern found
  → Spawn Agent
  → Agent generates code_before → code_after
  → Gate PASSES ✅
  → Learn pattern: HARDCODED_ROLE_SUPER_USER_v1 (confidence: 0.95)
  
Violation 2-49: Same type
  → Pattern FOUND, confidence 0.95
  → Use learned pattern (no Agent)
  → Apply fix to each file
  → Each success → confidence increases (0.95 → 0.96 → 0.97 ...)

[PHASE 3] Verification: 49 → 0 violations ✅
[SLM-AUTO-FIX] Patterns learned: 1, Violations fixed: 49
```

### Session 2: New Violation Type

```
[SLM-AUTO-FIX] CYCLE START
[PHASE 1] Found 12 violations (new type)

Violation 1: UserRole.lower() in ["admin", "super user"]
  → No pattern found
  → Spawn Agent
  → Agent generates code
  → Gate PASSES ✅
  → Learn pattern: HARDCODED_ROLE_STRING_CHECK_v1 (confidence: 0.95)

Violations 2-12: Same type
  → Pattern FOUND, use it
  → All succeed

[PHASE 3] Verification: 12 → 0 violations ✅
[SLM-AUTO-FIX] Patterns learned: 2 total, Violations fixed: 12
```

### Session 10: SLM Becoming Autonomous

```
[SLM-AUTO-FIX] CYCLE START
[PHASE 1] Found 3 violations

Violation 1: hardcoded_role_check_super_user (type A)
  → Pattern FOUND, confidence 0.98
  → Use learned pattern (NO Agent spawn)
  
Violation 2: UserRole.lower() in [...] (type B)
  → Pattern FOUND, confidence 0.97
  → Use learned pattern (NO Agent spawn)

Violation 3: Depends(get_current_hr_or_admin) (type C)
  → Pattern FOUND, confidence 0.95
  → Use learned pattern (NO Agent spawn)

[PHASE 2] SLM Analysis & Routing: 3/3 from pattern library (100%)
[PHASE 3] Verification: 3 → 0 violations ✅
[SLM-AUTO-FIX] NO AGENTS SPAWNED (SLM fully autonomous)
```

---

## Critical Implementation Notes

### When to Spawn Agent
✅ Spawn Agent when:
- New violation type (pattern not in library)
- Pattern confidence < 0.90 (too uncertain)
- Pattern failed on last 3 applications (losing confidence)

### When to Use Learned Pattern
✅ Use pattern when:
- Pattern confidence >= 0.90 (confident enough)
- Pattern has 5+ successful applications
- Pattern hasn't failed recently

### When to Improve Pattern
✅ Improve pattern when:
- Gate validation FAILED
- Multiple consecutive failures
- Spawn Agent with gate errors as context

### Pattern Retirement
❌ Retire pattern when:
- Confidence drops below 0.50 (too unreliable)
- More failures than successes
- Code changes invalidate pattern (refactoring)

---

## Summary: Training Timeline

| Phase | Violations | Status | Agent Spawns | Patterns | Confidence |
|-------|-----------|--------|--------------|----------|-----------|
| 1 (Session 1) | 49 | Learning | 1 | 1 | 0.95 |
| 2 (Session 2) | 12 | Learning | 1 | 2 | 0.96 |
| 3 (Session 3) | 8 | Training | 1 | 3 | 0.95 |
| 5 (Session 5) | 5 | Trained | 0 | 5 | 0.97 |
| 10 (Session 10) | 3 | Autonomous | 0 | 5+ | 0.98 |

**Result:** SLM learns to generate Python code fixes autonomously, eliminating Agent spawn overhead after initial training.

---

## How It Works: The Brain

**SLM is NOT a language model (LLM) that learns like Claude.** It's a:
- Pattern database (code_before → code_after mappings)
- Decision engine (which pattern to apply)
- Confidence tracker (how sure are we)
- Learning loop (improve over time)

**Agent (Claude) is the code writer.** It:
- Generates initial code fixes
- Reasons about violation patterns
- Adapts to gate feedback
- Improves failed patterns

**SLM's job:** "I've seen this problem before. Here's how to fix it."
**Agent's job:** "Here's a fix I generated. Did it work?"
**Learning loop's job:** Remember what worked, apply it next time.
