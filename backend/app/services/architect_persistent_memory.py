"""
Architect Persistent Memory - Learns from every cycle, stores knowledge, improves predictions

The architect's long-term memory:
- What patterns work
- What cascade failures happen
- How systems interact
- What rules were violated most
- How to prevent recurring issues
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class LearningType(Enum):
    """Types of learnings the architect stores"""
    PREDICTION_HIT = "prediction_hit"  # Predicted failure happened
    PREDICTION_MISS = "prediction_miss"  # Didn't predict something that broke
    PATTERN_EFFECTIVENESS = "pattern_effectiveness"  # Fix worked/didn't work
    CASCADE_DISCOVERY = "cascade_discovery"  # Found new cascade pattern
    ANTI_PATTERN = "anti_pattern"  # Found recurring violation
    REQUIREMENT_INTERACTION = "requirement_interaction"  # Requirements conflict
    ROOT_CAUSE_PATTERN = "root_cause_pattern"  # Same root cause appears repeatedly


class ArchitectMemoryEntry:
    """Single memory: what was learned and when"""

    def __init__(
        self,
        cycle_number: int,
        learning_type: LearningType,
        content: str,
        affected_systems: List[str],
        severity: str = "MEDIUM",
    ):
        self.cycle_number = cycle_number
        self.learning_type = learning_type
        self.content = content
        self.affected_systems = affected_systems
        self.severity = severity  # LOW, MEDIUM, HIGH, CRITICAL
        self.created_at = datetime.utcnow()
        self.retrieval_count = 0  # How many times this memory was used
        self.confidence = 0.5  # 0.0-1.0 based on evidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_number": self.cycle_number,
            "learning_type": self.learning_type.value,
            "content": self.content,
            "affected_systems": self.affected_systems,
            "severity": self.severity,
            "created_at": self.created_at.isoformat(),
            "retrieval_count": self.retrieval_count,
            "confidence": self.confidence,
        }


class ArchitectPersistentMemory:
    """
    Architect's long-term memory store.

    Persists:
    - Pattern discoveries (what works, what doesn't)
    - Cascade failure maps (System A breaks → Systems B,C,D fail)
    - Anti-patterns (code violations that recur)
    - Root cause patterns (same issue in multiple files)
    - Requirement interactions (features that conflict)
    - Prediction accuracy (what predictions were right/wrong)

    Used by:
    - Architect agent (reads before analysis, updates after)
    - Future cycles (learns from past mistakes)
    - Cascade risk prediction (knows which systems fail together)
    - Code review gate (knows what violations matter most)
    """

    def __init__(self, memory_file: str = "backend/app/data/architect_memory.json"):
        self.memory_file = memory_file
        self.memories: List[ArchitectMemoryEntry] = []
        self.pattern_library: Dict[str, Any] = {}
        self.cascade_matrix: Dict[str, List[str]] = {}  # System → [dependent systems]
        self.anti_patterns: Dict[str, int] = {}  # Pattern → occurrence count
        self.last_updated = datetime.utcnow()
        self.load()

    def load(self):
        """Load memories from disk"""
        try:
            import os
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r') as f:
                    data = json.load(f)
                    self.memories = [
                        ArchitectMemoryEntry(
                            cycle_number=m["cycle_number"],
                            learning_type=LearningType(m["learning_type"]),
                            content=m["content"],
                            affected_systems=m["affected_systems"],
                            severity=m["severity"],
                        )
                        for m in data.get("memories", [])
                    ]
                    self.pattern_library = data.get("pattern_library", {})
                    self.cascade_matrix = data.get("cascade_matrix", {})
                    self.anti_patterns = data.get("anti_patterns", {})
                    logger.info(f"[MEMORY] Loaded {len(self.memories)} memories")
        except Exception as e:
            logger.warning(f"[MEMORY] Could not load memories: {e}")
            self.memories = []

    def save(self):
        """Save memories to disk"""
        try:
            import os
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)

            data = {
                "last_updated": datetime.utcnow().isoformat(),
                "memories": [m.to_dict() for m in self.memories],
                "pattern_library": self.pattern_library,
                "cascade_matrix": self.cascade_matrix,
                "anti_patterns": self.anti_patterns,
            }

            with open(self.memory_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"[MEMORY] Saved {len(self.memories)} memories")
        except Exception as e:
            logger.error(f"[MEMORY] Could not save memories: {e}")

    def remember(self, entry: ArchitectMemoryEntry):
        """Store a new memory"""
        self.memories.append(entry)
        logger.info(f"[MEMORY] CYCLE {entry.cycle_number}: {entry.learning_type.value}")
        logger.info(f"[MEMORY] Content: {entry.content}")
        self.save()

    def record_prediction_hit(self, cycle: int, prediction: str, systems: List[str]):
        """Record when architect's prediction came true"""
        entry = ArchitectMemoryEntry(
            cycle_number=cycle,
            learning_type=LearningType.PREDICTION_HIT,
            content=f"Prediction confirmed: {prediction}",
            affected_systems=systems,
            severity="MEDIUM",
        )
        entry.confidence = 0.95  # Very confident this pattern repeats
        self.remember(entry)

    def record_prediction_miss(self, cycle: int, missed: str, systems: List[str]):
        """Record when architect failed to predict something"""
        entry = ArchitectMemoryEntry(
            cycle_number=cycle,
            learning_type=LearningType.PREDICTION_MISS,
            content=f"Prediction missed: {missed}. Need to update model.",
            affected_systems=systems,
            severity="HIGH",  # Prediction misses are critical to learn from
        )
        entry.confidence = 0.5  # Low confidence until confirmed multiple times
        self.remember(entry)

    def record_cascade_discovery(self, cycle: int, source_system: str, affected_systems: List[str]):
        """Record new cascade failure pattern discovered"""
        entry = ArchitectMemoryEntry(
            cycle_number=cycle,
            learning_type=LearningType.CASCADE_DISCOVERY,
            content=f"{source_system} failure cascades to: {', '.join(affected_systems)}",
            affected_systems=[source_system] + affected_systems,
            severity="CRITICAL",
        )
        entry.confidence = 0.7
        self.remember(entry)

        # Update cascade matrix
        if source_system not in self.cascade_matrix:
            self.cascade_matrix[source_system] = []
        for sys in affected_systems:
            if sys not in self.cascade_matrix[source_system]:
                self.cascade_matrix[source_system].append(sys)

    def record_anti_pattern(self, cycle: int, pattern: str, file: str, frequency: int = 1):
        """Record recurring anti-pattern"""
        key = f"{pattern}::{file}"
        self.anti_patterns[key] = self.anti_patterns.get(key, 0) + frequency

        entry = ArchitectMemoryEntry(
            cycle_number=cycle,
            learning_type=LearningType.ANTI_PATTERN,
            content=f"Anti-pattern found {frequency} times in {file}: {pattern}",
            affected_systems=[file],
            severity="HIGH" if self.anti_patterns[key] > 1 else "MEDIUM",
        )
        entry.confidence = min(0.5 + (self.anti_patterns[key] * 0.1), 0.95)
        self.remember(entry)

    def record_root_cause_pattern(self, cycle: int, root_cause: str, files: List[str]):
        """Record when same root cause appears in multiple files"""
        if len(files) > 1:
            entry = ArchitectMemoryEntry(
                cycle_number=cycle,
                learning_type=LearningType.ROOT_CAUSE_PATTERN,
                content=f"Root cause '{root_cause}' found in {len(files)} files: {', '.join(files[:3])}...",
                affected_systems=files,
                severity="CRITICAL",
            )
            entry.confidence = 0.8
            self.remember(entry)

    def get_relevant_memories(self, context: str, limit: int = 10) -> List[ArchitectMemoryEntry]:
        """
        Retrieve memories relevant to current context.

        Context examples:
        - "Thunder failure"
        - "Permission cascade"
        - "Silent catch pattern"
        """
        relevant = []

        for memory in sorted(self.memories, key=lambda m: (-m.confidence, -m.retrieval_count)):
            # Match by affected systems or learning type
            if any(ctx.lower() in memory.content.lower() for ctx in context.split()):
                relevant.append(memory)
                memory.retrieval_count += 1

            if len(relevant) >= limit:
                break

        return relevant

    def get_cascade_risks(self, system: str) -> List[str]:
        """Get list of systems that fail when 'system' fails"""
        return self.cascade_matrix.get(system, [])

    def get_recurring_anti_patterns(self, min_occurrences: int = 2) -> Dict[str, int]:
        """Get anti-patterns that appear multiple times"""
        return {
            pattern: count
            for pattern, count in self.anti_patterns.items()
            if count >= min_occurrences
        }

    def get_memory_summary(self) -> Dict[str, Any]:
        """Get summary of all memories"""
        return {
            "total_memories": len(self.memories),
            "by_type": self._count_by_type(),
            "cascade_patterns": len(self.cascade_matrix),
            "recurring_anti_patterns": len(self.get_recurring_anti_patterns()),
            "most_confident": [m.to_dict() for m in sorted(
                self.memories, key=lambda m: -m.confidence
            )[:5]],
            "most_used": [m.to_dict() for m in sorted(
                self.memories, key=lambda m: -m.retrieval_count
            )[:5]],
        }

    def _count_by_type(self) -> Dict[str, int]:
        """Count memories by type"""
        counts = {}
        for memory in self.memories:
            key = memory.learning_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts


# Global singleton
_architect_memory: Optional[ArchitectPersistentMemory] = None


def get_architect_memory() -> ArchitectPersistentMemory:
    """Get global architect memory instance"""
    global _architect_memory
    if _architect_memory is None:
        _architect_memory = ArchitectPersistentMemory()
    return _architect_memory
