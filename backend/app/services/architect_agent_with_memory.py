"""
Architect Agent With Memory - Real Claude agent that reads/writes persistent memory

This is the actual architect that:
1. Reads its persistent memory
2. Analyzes codebase + recent failures
3. Generates specification
4. Later learns from outcomes and updates memory
"""
import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.services.architect_persistent_memory import (
    get_architect_memory,
    ArchitectMemoryEntry,
    LearningType,
)

logger = logging.getLogger(__name__)


class ArchitectSpecificationWithMemory:
    """Architect specification that includes memory-based insights"""

    def __init__(self, cycle_number: int):
        self.cycle_number = cycle_number
        self.generated_at = datetime.utcnow()
        self.changes: List[Dict[str, Any]] = []
        self.validation_criteria: List[str] = []
        self.rollback_plan: str = ""
        self.risk_level: str = ""
        self.pattern_violations: List[Dict[str, Any]] = []
        self.cascade_risks: List[Dict[str, Any]] = []
        self.memory_insights: List[str] = []  # Insights from persistent memory
        self.predictions: List[Dict[str, Any]] = []  # What architect predicts will break

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle": self.cycle_number,
            "generated_at": self.generated_at.isoformat(),
            "changes": self.changes,
            "validation_criteria": self.validation_criteria,
            "rollback_plan": self.rollback_plan,
            "risk_level": self.risk_level,
            "pattern_violations": self.pattern_violations,
            "cascade_risks": self.cascade_risks,
            "memory_insights": self.memory_insights,
            "predictions": self.predictions,
        }


def build_architect_prompt_with_memory(
    cycle_number: int,
    recent_failures: Optional[List[Dict]] = None,
    recent_commits: Optional[List[str]] = None,
    new_requirements: Optional[str] = None,
) -> str:
    """
    Build prompt for architect agent, including its persistent memory.

    Memory is injected into the prompt so the agent:
    1. Knows what it learned before
    2. Can apply those learnings
    3. Can validate predictions
    """

    memory = get_architect_memory()
    memory_summary = memory.get_memory_summary()

    prompt = f"""
# ARCHITECT SPECIFICATION REQUEST - CYCLE {cycle_number}

You are the system architect with PERSISTENT MEMORY.
You have analyzed this system {memory_summary['total_memories']} times before.
Your job: Learn from past mistakes and prevent them from happening again.

## YOUR PERSISTENT MEMORY (What you learned before):

### Cascade Failures You've Discovered:
{json.dumps(memory.cascade_matrix, indent=2)}

### Anti-Patterns You've Seen Repeatedly:
"""

    for pattern, count in memory.get_recurring_anti_patterns():
        prompt += f"- {pattern}: Found {count} times (fix ALL instances, not just one)\n"

    prompt += f"""

### Predictions That Came True (High Confidence):
"""
    for memory_entry in memory.get_relevant_memories("prediction_hit", limit=5):
        prompt += f"- {memory_entry.content} (Confidence: {memory_entry.confidence*100:.0f}%)\n"

    prompt += f"""

### Predictions That Failed (Watch Out For):
"""
    for memory_entry in memory.get_relevant_memories("prediction_miss", limit=5):
        prompt += f"- {memory_entry.content} (Need to update model)\n"

    prompt += f"""

### Root Cause Patterns (Same issue in multiple files):
"""
    for memory_entry in memory.get_relevant_memories("root_cause_pattern", limit=5):
        prompt += f"- {memory_entry.content}\n"

    prompt += f"""

## RECENT SYSTEM STATE:

### Recent Failures (Last 5 cycles):
"""
    if recent_failures:
        for failure in recent_failures[-5:]:
            prompt += f"- Cycle {failure.get('cycle')}: {failure['description']}\n"
    else:
        prompt += "- None\n"

    prompt += f"""

### Recent Commits:
"""
    if recent_commits:
        for commit in recent_commits[-5:]:
            prompt += f"- {commit}\n"
    else:
        prompt += "- None\n"

    prompt += f"""

### New Requirements:
{new_requirements if new_requirements else "None"}

## YOUR MANDATE FOR THIS CYCLE:

### PHASE 1: MEMORY-BASED ANALYSIS
1. Review your cascade failure map - apply it here
2. Check for recurring anti-patterns
3. Validate your past predictions against actual outcomes
4. Update your mental model based on what surprised you

### PHASE 2: ROOT CAUSE ANALYSIS
- Are recent failures related to patterns you've seen before?
- If anti-pattern recurred → fix ALL instances (not just one file)
- Are cascade risks the ones you predicted?

### PHASE 3: SPECIFICATION WITH PREDICTION
For each change:
1. File and line number
2. Exact code change
3. Why this fixes it
4. What tests will validate it
5. **Predicted cascade risks** (what else might break)

### PHASE 4: VALIDATION PLAN
Include in spec:
- How to test this change
- How to catch cascade failures
- Health check metrics to monitor
- Rollback procedure if prediction wrong

## CRITICAL RULES (NON-NEGOTIABLE):

1. **QUEUE ROUTING**: Candidate → THUNDER, Everything else → FLASH
2. **PERMISSIONS**: No hardcoded get_current_*, use require_role_template_permission
3. **ERROR HANDLING**: Never silent catch, always raise
4. **NO DUPLICATES**: One celery_app.py, one database.py
5. **SPARTAN FORMATION**: Flash monitors neighbor health, escalates on cascade risk
6. **NO HARDCODING**: Queue types, nav items from API, not constants
7. **IF ANTI-PATTERN RECURRING**: Fix all instances, not just one

## OUTPUT (MUST BE VALID JSON):

```json
{{
  "cycle": {cycle_number},
  "analysis": {{
    "root_causes": [
      {{"issue": "...", "why": "...", "recurring_in_cycles": [...]}}
    ],
    "memory_applied": [
      {{"memory_type": "cascade_discovery", "applied_to": "...", "confidence": 0.8}}
    ],
    "prediction_validations": [
      {{"past_prediction": "...", "outcome": "CONFIRMED|REFUTED|UNKNOWN"}}
    ]
  }},
  "changes": [
    {{
      "file": "backend/app/...",
      "line": "42",
      "old_code": "...",
      "new_code": "...",
      "why": "Fixes [ROOT_CAUSE]. Memory: Similar issue fixed in CYCLE X.",
      "cascade_risks": [
        {{"system": "Thunder", "risk": "...", "confidence": 0.8}}
      ],
      "test": "How to verify this works"
    }}
  ],
  "memory_updates": [
    {{
      "learning_type": "prediction_hit|prediction_miss|cascade_discovery|anti_pattern|root_cause_pattern",
      "content": "What to remember",
      "affected_systems": ["..."],
      "severity": "LOW|MEDIUM|HIGH|CRITICAL",
      "confidence": 0.8
    }}
  ],
  "validation_criteria": [
    "..."
  ],
  "rollback_plan": "..."
}}
```

---

## WHY MEMORY MATTERS:

Without memory: Same bugs fixed over and over
With memory: "I've seen this before in 3 other files - fix all of them"

Without memory: Cascade failures surprise us
With memory: "When Thunder fails, Flash cascade 100% of the time - design for it"

Without memory: Failed predictions wasted
With memory: "Last time I predicted X would break - it didn't - so update model"

## GO. Analyze. Learn. Specify. Predict.
"""

    return prompt


async def spawn_architect_agent_with_memory(
    cycle_number: int,
    recent_failures: Optional[List[Dict]] = None,
    recent_commits: Optional[List[str]] = None,
    new_requirements: Optional[str] = None,
) -> ArchitectSpecificationWithMemory:
    """
    Spawn architect agent with memory access.

    Agent will:
    1. Load memories
    2. Analyze codebase with memory context
    3. Generate specification
    4. Suggest memory updates
    """

    memory = get_architect_memory()
    memory_summary = memory.get_memory_summary()

    prompt = build_architect_prompt_with_memory(
        cycle_number=cycle_number,
        recent_failures=recent_failures,
        recent_commits=recent_commits,
        new_requirements=new_requirements,
    )

    logger.info(f"[ARCHITECT] CYCLE {cycle_number}: Spawning agent with memory context")
    logger.info(f"[ARCHITECT] Memory has {memory_summary['total_memories']} memories")

    # ACTUAL IMPLEMENTATION: Call Claude Agent
    # For now, return stub specification with memory placeholder

    spec = ArchitectSpecificationWithMemory(cycle_number)

    # Add insight from memory
    memory_summary = memory.get_memory_summary()
    if memory_summary["recurring_anti_patterns"] > 0:
        spec.memory_insights.append(
            f"Found {memory_summary['recurring_anti_patterns']} recurring anti-patterns - fix ALL instances"
        )

    if memory.cascade_matrix:
        spec.memory_insights.append(
            f"Using cascade map from {len(memory.cascade_matrix)} discovered patterns"
        )

    # In real implementation:
    # result = await Agent(
    #     description="Architect agent with persistent memory analysis",
    #     prompt=prompt,
    #     subagent_type="Plan",
    #     run_in_background=False,
    # )
    #
    # spec_data = json.loads(result)  # Parse JSON from agent
    # spec.changes = spec_data["changes"]
    # spec.predictions = spec_data.get("cascade_risks", [])
    #
    # # Process memory updates suggested by architect
    # for update in spec_data.get("memory_updates", []):
    #     entry = ArchitectMemoryEntry(
    #         cycle_number=cycle_number,
    #         learning_type=LearningType(update["learning_type"]),
    #         content=update["content"],
    #         affected_systems=update["affected_systems"],
    #         severity=update["severity"],
    #     )
    #     entry.confidence = update.get("confidence", 0.5)
    #     memory.remember(entry)

    return spec


async def architect_learns_from_cycle_outcome(
    cycle_number: int,
    specification: ArchitectSpecificationWithMemory,
    test_results: Dict[str, Any],
    cascade_failures: Optional[List[Dict]] = None,
):
    """
    Architect reviews cycle outcome and updates its memory.

    Called AFTER cycle completes with actual test results.
    Updates memory so future cycles avoid repeated mistakes.
    """

    memory = get_architect_memory()

    logger.info(f"[ARCHITECT-LEARN] CYCLE {cycle_number}: Analyzing outcomes")

    # PHASE 1: Validate predictions
    if specification.predictions and cascade_failures:
        for prediction in specification.predictions:
            predicted_system = prediction.get("system")
            if any(cf["system"] == predicted_system for cf in cascade_failures):
                # Prediction came true
                memory.record_prediction_hit(
                    cycle_number,
                    f"Predicted {predicted_system} cascade",
                    [predicted_system],
                )
                logger.info(f"[ARCHITECT-LEARN] Prediction HIT: {predicted_system} failed as expected")
            else:
                # Prediction missed
                memory.record_prediction_miss(
                    cycle_number,
                    f"Expected {predicted_system} to fail but didn't",
                    [predicted_system],
                )
                logger.warning(f"[ARCHITECT-LEARN] Prediction MISS: {predicted_system}")

    # PHASE 2: Discover new cascades
    if cascade_failures and len(cascade_failures) > 1:
        source_system = cascade_failures[0]["system"]
        affected = [cf["system"] for cf in cascade_failures[1:]]
        memory.record_cascade_discovery(cycle_number, source_system, affected)
        logger.info(f"[ARCHITECT-LEARN] Cascade discovered: {source_system} → {affected}")

    # PHASE 3: Check if anti-patterns recurred
    if test_results.get("gate_violations"):
        for violation in test_results["gate_violations"]:
            if "silent_catch" in violation.get("type", ""):
                memory.record_anti_pattern(
                    cycle_number,
                    "Silent catch in except block",
                    violation.get("file", "unknown"),
                )
                logger.warning(f"[ARCHITECT-LEARN] Anti-pattern recurred: silent catch")

    # PHASE 4: Log what we learned
    summary = memory.get_memory_summary()
    logger.info(f"[ARCHITECT-LEARN] Memory now has {summary['total_memories']} total memories")
    logger.info(f"[ARCHITECT-LEARN] Cascade patterns: {len(memory.cascade_matrix)}")
    logger.info(f"[ARCHITECT-LEARN] Recurring anti-patterns: {summary['recurring_anti_patterns']}")
