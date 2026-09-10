"""
Architect Learning Demo - Shows how memory learns and improves across cycles

Real example of:
- CYCLE 1: Architect finds pattern, makes prediction, learns from failure
- CYCLE 2: Architect uses memory to prevent same failure
- CYCLE 3: Architect predicts cascade correctly, memory confirms
"""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from app.services.architect_persistent_memory import (
    get_architect_memory,
    ArchitectMemoryEntry,
    LearningType,
)

def demo_architect_learning():
    """
    Real example showing memory accumulation and learning
    """

    memory = get_architect_memory()
    print("\n" + "="*70)
    print("ARCHITECT LEARNING DEMONSTRATION")
    print("="*70)

    # ────────────────────────────────────────────────────────────────────
    # CYCLE 1: Discovery Phase
    # ────────────────────────────────────────────────────────────────────
    print("\n[CYCLE 1] Architect discovers silent catch pattern\n")

    # Architect finds anti-pattern
    memory.record_anti_pattern(
        cycle=1,
        pattern="try/except with return [] (silent failure)",
        file="backend/app/services/flash_service.py",
        frequency=3
    )

    # Makes prediction about cascade
    memory.record_cascade_discovery(
        cycle=1,
        source_system="Flash",
        affected_systems=["Thunder", "Interviews", "Offers"]
    )

    print("[MEMORY] Recorded anti-pattern: silent catch in flash_service.py")
    print("[MEMORY] Predicted cascade: Flash failure → Thunder/Interview/Offer cascade")

    # ────────────────────────────────────────────────────────────────────
    # CYCLE 2: Validation Phase
    # ────────────────────────────────────────────────────────────────────
    print("\n[CYCLE 2] Architect's prediction comes true\n")

    # Tests ran, prediction was correct
    memory.record_prediction_hit(
        cycle=2,
        prediction="Flash silent failures cause Thunder cascades",
        systems=["Flash", "Thunder"]
    )

    # Finds same pattern in another file
    memory.record_anti_pattern(
        cycle=2,
        pattern="try/except with return {} (silent failure)",
        file="backend/app/services/thunder_service.py",
        frequency=2
    )

    print("[MEMORY] Prediction confirmed: Flash failure caused Thunder cascade")
    print("[MEMORY] Found same anti-pattern in thunder_service.py")
    print("[MEMORY] Confidence increased to 95% that this pattern causes cascades")

    # ────────────────────────────────────────────────────────────────────
    # CYCLE 3: Prevention Phase
    # ────────────────────────────────────────────────────────────────────
    print("\n[CYCLE 3] Architect uses memory to prevent recurring issue\n")

    # Before implementing, architect retrieves relevant memories
    relevant = memory.get_relevant_memories("silent catch", limit=10)
    print(f"[MEMORY] Retrieved {len(relevant)} relevant memories")

    for mem in relevant:
        print(f"  - {mem.learning_type.value}: {mem.content} (Confidence: {mem.confidence*100:.0f}%)")

    # Root cause pattern: same issue across files
    memory.record_root_cause_pattern(
        cycle=3,
        root_cause="Silent exception catches returning empty data",
        files=[
            "backend/app/services/flash_service.py",
            "backend/app/services/thunder_service.py",
            "backend/app/api/v1/endpoints/candidates.py",
            "backend/app/api/v1/endpoints/jobs/crud.py",
        ]
    )

    print("[MEMORY] Root cause identified in 4+ files")
    print("[MEMORY] Decision: Fix ALL instances, not just one")

    # ────────────────────────────────────────────────────────────────────
    # CYCLE 4: Prediction Validation
    # ────────────────────────────────────────────────────────────────────
    print("\n[CYCLE 4] Cascade prediction accuracy validation\n")

    # Get cascade map
    cascade_risks = memory.get_cascade_risks("Flash")
    print(f"[MEMORY] Known cascade risks for Flash: {cascade_risks}")

    # Architect correctly predicted this would affect Thunder
    memory.record_prediction_hit(
        cycle=4,
        prediction="Flash changes affect Thunder recruitment pipeline",
        systems=["Flash", "Thunder"]
    )

    print("[MEMORY] Cascade prediction validated again")

    # ────────────────────────────────────────────────────────────────────
    # Display Memory Summary
    # ────────────────────────────────────────────────────────────────────
    print("\n" + "="*70)
    print("MEMORY SUMMARY AFTER 4 CYCLES")
    print("="*70 + "\n")

    summary = memory.get_memory_summary()
    print(f"Total Memories: {summary['total_memories']}")
    print(f"\nMemories by Type:")
    for mem_type, count in summary['by_type'].items():
        print(f"  - {mem_type}: {count}")

    print(f"\nCascade Patterns Discovered: {summary['cascade_patterns']}")
    for source, affected in memory.cascade_matrix.items():
        print(f"  - {source} → {affected}")

    print(f"\nRecurring Anti-Patterns: {summary['recurring_anti_patterns']}")
    for pattern, count in memory.get_recurring_anti_patterns():
        print(f"  - {pattern}: {count} occurrences")

    print(f"\nMost Confident Memories:")
    for mem in summary['most_confident']:
        print(f"  - [{mem['learning_type']}] {mem['content']}")
        print(f"    Confidence: {mem['confidence']*100:.0f}% | Used: {mem['retrieval_count']} times")

    # ────────────────────────────────────────────────────────────────────
    # Show How Memory Prevents Future Mistakes
    # ────────────────────────────────────────────────────────────────────
    print("\n" + "="*70)
    print("ARCHITECT DECISION: PREVENT RECURRING ISSUE")
    print("="*70 + "\n")

    print("NEW REQUIREMENT: Add new async operation to candidates API\n")

    print("ARCHITECT WITHOUT MEMORY:")
    print("  1. Add async operation (maybe missing error handling)")
    print("  2. Tests pass locally")
    print("  3. Deploy")
    print("  4. Cascade failure in production")
    print("  Result: 2 hours to debug and fix\n")

    print("ARCHITECT WITH MEMORY:")
    print("  1. Retrieve memories about 'silent catch' patterns")
    print("  2. See that 4 files had this issue")
    print("  3. See that it causes Flash → Thunder → Offers cascade")
    print("  4. Requirement: Must have explicit error handling with raise")
    print("  5. Review specification with: error handlers, cascade tests, monitoring")
    print("  6. Deploy with 99% confidence it won't break")
    print("  Result: Prevented cascade before deployment\n")

    # ────────────────────────────────────────────────────────────────────
    # Save memory for persistence
    # ────────────────────────────────────────────────────────────────────
    print("="*70)
    print("MEMORY PERSISTENCE")
    print("="*70 + "\n")

    memory.save()
    print("✓ Memory saved to backend/app/data/architect_memory.json")
    print("✓ On next cycle, architect will load this memory automatically")
    print("✓ Learning persists across sessions and deployments")

    print("\n" + "="*70 + "\n")


def show_memory_in_next_cycle():
    """
    Show how architect uses saved memory in next cycle
    """
    print("\n" + "="*70)
    print("NEXT CYCLE - ARCHITECT LOADS MEMORY")
    print("="*70 + "\n")

    memory = get_architect_memory()

    print(f"Loaded {len(memory.memories)} memories from disk")
    print(f"Cascade matrix: {memory.cascade_matrix}")
    print(f"Anti-patterns: {memory.get_recurring_anti_patterns()}\n")

    print("ARCHITECT'S PROMPT FOR NEXT CYCLE includes:\n")
    print("---MEMORY INJECTION START---")
    print("## YOUR PERSISTENT MEMORY (What you learned before):\n")
    print("### Cascade Failures You've Discovered:")
    print(json.dumps(memory.cascade_matrix, indent=2))
    print("\n### Anti-Patterns You've Seen Repeatedly:")
    for pattern, count in memory.get_recurring_anti_patterns():
        print(f"- {pattern}: Found {count} times (fix ALL instances, not just one)")
    print("---MEMORY INJECTION END---\n")

    print("Result: Architect starts NEXT cycle with full context of previous learnings")


if __name__ == "__main__":
    # Run the demo
    demo_architect_learning()

    # Show what happens in next cycle
    show_memory_in_next_cycle()
