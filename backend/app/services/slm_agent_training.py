"""
SLM Agent Training Loop - Teach SLM to Generate Python Code

When architect detects violation:
1. SLM checks pattern library
2. If pattern missing OR confidence too low → Spawn Agent
3. Agent generates Python code fix (with SLM-provided context)
4. Code reviewed by gate
5. If gate passes → SLM learns the pattern (stores in library, increases confidence)
6. If gate fails → SLM marks pattern as failed (decreases confidence, tries next approach)

After N successful patterns learned → SLM can solve similar violations WITHOUT Agent
"""
import logging
from typing import Dict, Optional, Any
from app.services.architect_auto_fix_hardcoded_roles import (
    SLMPatternLibrary,
    SLMCodeGenerationPattern,
)

logger = logging.getLogger(__name__)


class SLMAgentTrainer:
    """Trains SLM to generate Python code through Agent feedback loop"""

    def __init__(self):
        self.pattern_library = SLMPatternLibrary()
        self.training_history = []

    async def spawn_agent_with_slm_context(
        self,
        violation: Dict[str, Any],
        root_cause_analysis: str,
    ) -> Optional[Dict[str, str]]:
        """
        Spawn Agent to generate code fix with SLM context.

        Returns: {
            "code_before": str,
            "code_after": str,
            "explanation": str
        }
        """
        logger.info(f"[SLM-TRAIN] Spawning Agent to generate code for: {violation['type']}")

        # Prepare context for Agent
        agent_prompt = f"""You are an expert Python code fixer. Generate EXACT code replacement for this violation.

VIOLATION TYPE: {violation['type']}
FILE: {violation['file']}
LINE: {violation['line']}

ROOT CAUSE ANALYSIS:
{root_cause_analysis}

CURRENT CODE (WRONG):
{violation['pattern']}

YOUR TASK:
1. Generate EXACT Python code replacement
2. Use role-template permission system (require_role_template_permission)
3. Format as JSON with "code_before" and "code_after"
4. Include brief explanation

RULES:
- code_before: Exact pattern from current code (as regex-safe string)
- code_after: Replacement using require_role_template_permission(...)
- Never use hardcoded role names or string comparisons
- Always use: dependencies=[Depends(require_role_template_permission(...))]

OUTPUT JSON:
{{
    "code_before": "...",
    "code_after": "...",
    "explanation": "..."
}}
"""

        try:
            # TODO: Spawn Agent tool here
            # agent_result = await Agent(
            #     description="Generate Python code fix for hardcoded role check",
            #     prompt=agent_prompt,
            #     subagent_type="claude"  # Code-writing agent
            # )
            # agent_output = agent_result.get("output")

            # For now, placeholder
            logger.warning("[SLM-TRAIN] Agent spawning not yet implemented")
            return None

        except Exception as e:
            logger.error(f"[SLM-TRAIN] Agent generation failed: {e}")
            return None

    async def validate_and_learn(
        self,
        violation: Dict[str, Any],
        agent_output: Dict[str, str],
        gate_result: Dict[str, Any],
    ) -> bool:
        """
        Validate Agent's generated code and learn from result.

        Returns: True if pattern learned successfully
        """
        logger.info(f"[SLM-TRAIN] Validating Agent output for {violation['type']}...")

        # Check if gate passed
        gate_passed = gate_result.get("status") == "PASSED"

        if gate_passed:
            logger.info("[SLM-TRAIN] ✅ Gate passed - Learning pattern from successful code generation")

            # Create new pattern from Agent output
            pattern = SLMCodeGenerationPattern(
                pattern_id=f"LEARNED_{violation['type']}_{len(self.pattern_library.patterns)}",
                violation_type=violation["type"],
                code_before=agent_output["code_before"],
                code_after=agent_output["code_after"],
                confidence=0.95,  # Start high confidence for Agent-generated code
                agent_generated=True,
                file_examples=[violation["file"]],
            )

            # Store in library
            self.pattern_library.store_pattern(pattern)

            # Record training
            self.training_history.append({
                "violation_type": violation["type"],
                "pattern_id": pattern.pattern_id,
                "success": True,
                "gate_result": gate_result,
            })

            logger.info(
                f"[SLM-TRAIN] 🎓 Learned new pattern: {pattern.pattern_id} "
                f"(confidence: 0.95, agent_generated: true)"
            )

            return True

        else:
            logger.error(f"[SLM-TRAIN] ❌ Gate failed - Agent output rejected")
            logger.error(f"[SLM-TRAIN] Gate errors: {gate_result.get('errors', [])}")

            # Record failed training attempt
            self.training_history.append({
                "violation_type": violation["type"],
                "success": False,
                "gate_result": gate_result,
            })

            return False

    async def auto_improve_pattern(
        self,
        pattern_id: str,
        failure_details: Dict[str, Any],
    ):
        """
        Auto-improve failing pattern by spawning Agent with failure details.

        If pattern keeps failing → Ask Agent for better approach
        """
        logger.info(f"[SLM-TRAIN] Auto-improving failing pattern: {pattern_id}")

        if pattern_id not in self.pattern_library.patterns:
            logger.error(f"[SLM-TRAIN] Pattern not found: {pattern_id}")
            return

        pattern = self.pattern_library.patterns[pattern_id]

        # Generate improvement prompt
        improvement_prompt = f"""The following Python code pattern is failing code review gate.

FAILING PATTERN:
ID: {pattern_id}
code_before: {pattern.code_before}
code_after: {pattern.code_after}

GATE ERRORS:
{failure_details.get('gate_errors', [])}

USAGE COUNT: {pattern.usage_count}
CURRENT CONFIDENCE: {pattern.confidence}

YOUR TASK:
Generate IMPROVED code replacement that will pass the gate.

Focus on:
1. Permission check correctness
2. Dependency import validity
3. FastAPI decorator format
4. No hardcoded values

Output JSON as before: {{"code_before": "...", "code_after": "...", "explanation": "..."}}
"""

        try:
            # TODO: Spawn Agent with improvement prompt
            # improved_output = await Agent(improvement_prompt)

            # For now, placeholder
            logger.warning("[SLM-TRAIN] Agent improvement spawning not implemented")

        except Exception as e:
            logger.error(f"[SLM-TRAIN] Pattern improvement failed: {e}")

    def get_training_stats(self) -> Dict[str, Any]:
        """Get SLM training statistics"""
        successful = sum(1 for h in self.training_history if h["success"])
        failed = sum(1 for h in self.training_history if not h["success"])
        success_rate = (successful / len(self.training_history) * 100) if self.training_history else 0

        return {
            "patterns_learned": len(self.pattern_library.patterns),
            "training_attempts": len(self.training_history),
            "successful_generations": successful,
            "failed_generations": failed,
            "success_rate": success_rate,
            "library_confidence_avg": sum(p.confidence for p in self.pattern_library.patterns.values()) / len(self.pattern_library.patterns) if self.pattern_library.patterns else 0,
            "high_confidence_patterns": sum(1 for p in self.pattern_library.patterns.values() if p.confidence >= 0.90),
        }

    async def continuous_training_loop(self):
        """
        Continuous training loop: Monitor for new violations, train SLM patterns.

        Runs in background, continuous learning.
        """
        logger.info("[SLM-TRAIN] Starting continuous training loop...")

        # Every 1 hour, check for new violations and train patterns
        # Every new violation type → spawn Agent → get pattern → store in library
        # Result: SLM gradually learns all violation types → can fix them without Agent

        while True:
            try:
                # Get all violations
                from app.services.architect_codebase_audit import CodebaseAuditScanner
                scanner = CodebaseAuditScanner()
                audit = await scanner.audit_complete_codebase()

                # For each violation type without learned pattern → train
                for violation_type, count in audit.get("by_type", {}).items():
                    pattern = self.pattern_library.find_pattern(violation_type, min_confidence=0.90)

                    if not pattern and count > 0:
                        logger.info(f"[SLM-TRAIN] Training pattern for new violation: {violation_type} ({count} instances)")
                        # TODO: Spawn training for this type

                import asyncio
                await asyncio.sleep(3600)  # Train every hour

            except Exception as e:
                logger.error(f"[SLM-TRAIN] Continuous training loop error: {e}")
                import asyncio
                await asyncio.sleep(60)  # Retry in 1 minute


# Global trainer
_trainer: Optional[SLMAgentTrainer] = None


def get_slm_trainer() -> SLMAgentTrainer:
    """Get global SLM trainer"""
    global _trainer
    if _trainer is None:
        _trainer = SLMAgentTrainer()
    return _trainer
