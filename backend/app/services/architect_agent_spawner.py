"""
Architect Agent Spawner - Actually invoke Claude as architect via Agent tool

This is the bridge between the orchestration system and real Claude agents.
Shows how to spawn architect agent from Python code.
"""
import logging
import json
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


async def spawn_architect_agent_for_cycle(
    cycle_number: int,
    recent_failures: Optional[List[Dict]] = None,
    recent_commits: Optional[List[str]] = None,
    new_requirements: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Spawn Claude as architect agent for specification generation.

    ACTUAL IMPLEMENTATION:
    This would be called from sdlc_cycle_with_learning.py
    and would use the Agent() tool to invoke Claude with full context.

    In Python/backend, the pattern would be:
    1. Build comprehensive prompt with memory
    2. Invoke Agent(description, prompt, subagent_type="Plan", run_in_background=False)
    3. Parse response JSON
    4. Extract specification + memory updates
    5. Return to orchestration

    Example usage in async context:
    ```python
    spec_data = await spawn_architect_agent_for_cycle(
        cycle_number=5,
        recent_failures=[
            {"cycle": 4, "description": "Flash cascade in Thunder"},
        ],
        recent_commits=["abc123: Fix permission check"],
        new_requirements="Add new interview scheduling feature"
    )
    ```
    """

    # Build the full prompt with memory context
    from app.services.architect_agent_with_memory import build_architect_prompt_with_memory

    prompt = build_architect_prompt_with_memory(
        cycle_number=cycle_number,
        recent_failures=recent_failures,
        recent_commits=recent_commits,
        new_requirements=new_requirements,
    )

    logger.info(f"[ARCHITECT-SPAWN] Building agent spawn for CYCLE {cycle_number}")
    logger.info(f"[ARCHITECT-SPAWN] Prompt length: {len(prompt)} characters")

    # IN REAL IMPLEMENTATION, THIS WOULD USE THE Agent() TOOL:
    #
    # from ... import Agent  # (hypothetical import)
    #
    # result = await Agent(
    #     description=f"Architect specification generation - CYCLE {cycle_number}",
    #     prompt=prompt,
    #     subagent_type="Plan",  # Use Plan agent for architectural decisions
    #     run_in_background=False,  # Need result before proceeding
    #     timeout_seconds=120,  # 120-second architect response timeout
    # )
    #
    # # Parse JSON response
    # spec_data = json.loads(result)
    #
    # Return specification data

    # STUB: Return mock specification for demonstration
    return {
        "cycle": cycle_number,
        "status": "STUB - Need Agent tool integration",
        "changes": [],
        "cascade_risks": [],
        "memory_updates": [],
        "validation_criteria": [],
    }


def format_agent_spawn_instruction() -> str:
    """
    Returns the exact instruction for Claude to spawn architect agent.
    Can be included in documentation or prompts.
    """

    instruction = """
# HOW TO SPAWN ARCHITECT AGENT

The architect agent can be spawned from Claude Code frontend or from Python backend.

## From Claude Code Frontend (Interactive)

When you're working on this project and need architect analysis:

```
Use the Agent tool:

Agent(
    description: "Architect code analysis and specification for CYCLE 5",
    prompt: [FULL PROMPT WITH MEMORY FROM architect_agent_with_memory.py],
    subagent_type: "Plan",
    run_in_background: false
)
```

## From Python Backend (Automated)

In sdlc_cycle_with_learning.py, the spawn happens like this:

```python
async def _architect_phase(self, cycle_number: int, description: str):
    '''Spawn architect agent with memory context'''

    spec = await asyncio.wait_for(
        spawn_architect_agent_for_cycle(
            cycle_number=cycle_number,
            recent_failures=self.recent_failures[-10:],
            recent_commits=self.recent_commits[-10:],
            new_requirements=description,
        ),
        timeout=120  # 120-second timeout
    )

    return spec
```

## Agent Capabilities Required

The architect agent should:

1. **Read Code** - Access backend Python files
2. **Understand Architecture** - Know Spartan formation, queue routing, permissions
3. **Analyze Patterns** - Identify what's working vs what's broken
4. **Generate JSON** - Return structured specification
5. **Learn from History** - Use memory injected in prompt
6. **Predict Cascades** - Say what might break

## Memory-Based Prompt Format

Architect receives prompt that includes:

```
[ESTABLISHED ARCHITECTURAL RULES]
- Queue routing
- Permission checks
- Error handling
- Spartan formation
- etc.

[YOUR PERSISTENT MEMORY]
### Cascade Patterns You've Discovered:
- Flash → [Thunder, Interviews, Offers]
- Thunder → [Flash]

### Anti-Patterns You've Seen:
- try/except with return [] (found 4 times)
- Hardcoded values (found 6 times)

### Predictions That Came True:
- "Flash cascade" (95% confidence)

### Predictions That Failed:
- "API timeout would cascade" (REFUTED)

[RECENT SYSTEM STATE]
[NEW REQUIREMENTS]

[YOUR MANDATE]
- Analyze with memory context
- Predict cascade failures
- Generate specification
- Output JSON with changes, risks, memory_updates
```

## Response Format (Must Be Valid JSON)

Architect agent returns:

```json
{
  "cycle": 5,
  "analysis": {
    "root_causes": [...],
    "memory_applied": [...],
    "prediction_validations": [...]
  },
  "changes": [
    {
      "file": "backend/app/...",
      "line": "42",
      "old_code": "...",
      "new_code": "...",
      "why": "...",
      "cascade_risks": [...],
      "test": "..."
    }
  ],
  "memory_updates": [
    {
      "learning_type": "cascade_discovery",
      "content": "...",
      "affected_systems": [...],
      "severity": "CRITICAL",
      "confidence": 0.95
    }
  ],
  "validation_criteria": [...]
}
```

## Integration Path

1. Architect agent spawned with memory context
2. Returns JSON spec + memory updates
3. Memory stored in architect_persistent_memory.py
4. Claude implements per spec
5. Tests run
6. Results sent back to architect
7. Architect learns, updates memory
8. Cycle repeats (architect now smarter)
"""

    return instruction


def generate_architect_memory_prompt_injection(cycle_number: int) -> str:
    """
    Generate the memory injection portion of architect prompt.
    Shows exactly what memory looks like when injected.
    """

    from app.services.architect_persistent_memory import get_architect_memory

    memory = get_architect_memory()
    summary = memory.get_memory_summary()

    injection = f"""
# YOUR PERSISTENT MEMORY (What you learned before)

## Summary
- Total memories: {summary['total_memories']}
- Cascade patterns discovered: {summary['cascade_patterns']}
- Recurring anti-patterns: {summary['recurring_anti_patterns']}

## Cascade Failures You've Discovered (Use when predicting failures):
{json.dumps(memory.cascade_matrix, indent=2)}

## Anti-Patterns You've Seen Repeatedly (Fix ALL instances if found):
"""

    for pattern, count in memory.get_recurring_anti_patterns():
        injection += f"- {pattern}: Found {count} times (fix all, not just one)\n"

    injection += "\n## Predictions That Came True (High Confidence):\n"
    for mem_entry in memory.get_relevant_memories("prediction_hit", limit=5):
        injection += f"- {mem_entry.content} (Confidence: {mem_entry.confidence*100:.0f}%)\n"

    injection += "\n## Predictions That Failed (Update Model):\n"
    for mem_entry in memory.get_relevant_memories("prediction_miss", limit=5):
        injection += f"- {mem_entry.content}\n"

    injection += "\n## Root Cause Patterns (Same issue in multiple files):\n"
    for mem_entry in memory.get_relevant_memories("root_cause_pattern", limit=5):
        injection += f"- {mem_entry.content}\n"

    return injection


if __name__ == "__main__":
    # Print instructions for spawning architect agent
    print(format_agent_spawn_instruction())
