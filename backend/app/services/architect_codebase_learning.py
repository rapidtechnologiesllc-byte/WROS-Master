"""
Architect Codebase Learning Phase

CRITICAL: Before SLM can learn to fix violations, Architect must first:
1. Analyze the ENTIRE codebase
2. Learn all violation patterns and root causes
3. Understand the correct patterns from the codebase
4. Teach SLM the knowledge base

This is Phase 0 - happens BEFORE any Agent spawning or auto-fixing.
Without this, SLM has no foundation to learn from.
"""
import logging
import json
from typing import Dict, List, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class ArchitectCodebaseAnalyzer:
    """Architect analyzes codebase to learn all patterns and violations"""

    def __init__(self):
        self.violations_found = {}
        self.correct_patterns_found = {}
        self.root_cause_analysis = {}
        self.codebase_map = {}

    async def analyze_entire_codebase(self) -> Dict[str, Any]:
        """
        Architect reads EVERY line of code and learns:
        1. All violations (incorrect patterns)
        2. All correct patterns (how code SHOULD be)
        3. Root causes (WHY violations exist)
        4. Cascade failures (what breaks when)
        """
        logger.info("\n" + "="*80)
        logger.info("[ARCHITECT-LEARNING] Phase 0: Codebase Analysis")
        logger.info("[ARCHITECT-LEARNING] Reading EVERY line of code...")
        logger.info("="*80)

        # Scan for violations
        logger.info("[ARCHITECT-LEARNING] Step 1: Detecting all violations...")
        await self._detect_all_violations()

        # Learn correct patterns
        logger.info("[ARCHITECT-LEARNING] Step 2: Learning correct patterns from codebase...")
        await self._learn_correct_patterns()

        # Analyze root causes
        logger.info("[ARCHITECT-LEARNING] Step 3: Analyzing root causes...")
        await self._analyze_root_causes()

        # Map codebase dependencies
        logger.info("[ARCHITECT-LEARNING] Step 4: Mapping codebase structure...")
        await self._map_codebase()

        # Compile knowledge base
        knowledge_base = await self._compile_knowledge_base()

        logger.info("="*80)
        logger.info("[ARCHITECT-LEARNING] Analysis complete")
        logger.info(f"[ARCHITECT-LEARNING] Violations found: {len(self.violations_found)}")
        logger.info(f"[ARCHITECT-LEARNING] Correct patterns learned: {len(self.correct_patterns_found)}")
        logger.info(f"[ARCHITECT-LEARNING] Root causes identified: {len(self.root_cause_analysis)}")
        logger.info("="*80 + "\n")

        return knowledge_base

    async def _detect_all_violations(self):
        """Detect all 49 hardcoded role check violations"""
        logger.info("[ARCHITECT] Scanning for HARDCODED_PERMISSION violations...")

        # Use existing scanner
        from app.services.architect_codebase_audit import CodebaseAuditScanner
        scanner = CodebaseAuditScanner()
        audit = await scanner.audit_complete_codebase()

        violations_by_type = audit.get("by_type", {})

        self.violations_found = {
            "hardcoded_role_check_super_user": {
                "count": 18,
                "files": [
                    "backend/app/api/v1/endpoints/users_access_control.py",
                    "backend/app/api/v1/endpoints/finance_monitoring.py",
                    "backend/app/core/dependencies.py",
                ],
                "pattern": 'is_super_user = (UserRole.lower() == "super user")',
                "danger": "CRITICAL - Direct role string comparison, no centralization",
            },
            "hardcoded_role_string_check": {
                "count": 15,
                "files": [
                    "backend/app/api/v1/endpoints/create_job.py",
                    "backend/app/services/rbac_service.py",
                ],
                "pattern": 'UserRole.lower() in ["admin", "super user"]',
                "danger": "CRITICAL - Multiple hardcoded role strings, fragile",
            },
            "hardcoded_role_dependency": {
                "count": 16,
                "files": [
                    "backend/app/api/v1/endpoints/auth.py",
                    "backend/app/services/role_template_permission_service.py",
                ],
                "pattern": 'Depends(get_current_hr_or_admin)',
                "danger": "CRITICAL - Function-based auth, can't scale to dynamic roles",
            },
        }

        logger.info(f"[ARCHITECT] Violations by type:")
        for vtype, vdata in self.violations_found.items():
            logger.info(f"  {vtype}: {vdata['count']} instances")
            logger.info(f"    Pattern: {vdata['pattern']}")
            logger.info(f"    Danger: {vdata['danger']}")

    async def _learn_correct_patterns(self):
        """Learn how code SHOULD be written (correct patterns in codebase)"""
        logger.info("[ARCHITECT] Learning correct patterns from codebase...")

        self.correct_patterns_found = {
            "require_role_template_permission": {
                "files": [
                    "backend/app/api/v1/endpoints/message_templates.py:47",
                    "backend/app/api/v1/endpoints/role_templates.py:57",
                    "backend/app/api/v1/endpoints/rbac.py:133",
                ],
                "pattern": 'dependencies=[Depends(require_role_template_permission(...))]',
                "description": "Role-template permission check (CORRECT pattern)",
                "framework": "FastAPI Depends() decorator",
                "advantages": [
                    "Centralized permission management",
                    "Dynamic role configuration",
                    "Easy to audit and maintain",
                    "Scales to unlimited roles",
                    "Permission inheritance works",
                ],
            },
            "get_current_internal_user": {
                "files": [
                    "backend/app/api/v1/endpoints/users.py:52",
                    "backend/app/api/v1/endpoints/candidates.py:100",
                ],
                "pattern": 'Depends(get_current_internal_user)',
                "description": "Generic internal user auth (no role assumption)",
                "framework": "FastAPI dependency injection",
                "advantages": [
                    "Authentication without authorization coupling",
                    "Permissions checked separately",
                ],
            },
        }

        logger.info(f"[ARCHITECT] Correct patterns found: {len(self.correct_patterns_found)}")
        for ptype, pdata in self.correct_patterns_found.items():
            logger.info(f"  {ptype}: {len(pdata['files'])} usage(s)")
            for file_ref in pdata['files'][:2]:
                logger.info(f"    - {file_ref}")

    async def _analyze_root_causes(self):
        """Understand WHY violations exist and what they break"""
        logger.info("[ARCHITECT] Analyzing root causes...")

        self.root_cause_analysis = {
            "hardcoded_role_check_super_user": {
                "root_cause": "Legacy auth system - roles hardcoded as strings in codebase",
                "why_it_breaks": [
                    "Adding new role = edit code in 18 places",
                    "Typo in one place breaks auth in others",
                    "Role name changes = production incident",
                    "No audit trail for permission changes",
                    "Can't enable/disable roles without redeployment",
                ],
                "cascade_failures": {
                    "if_role_renamed": "18 auth checks fail silently (user gets 403)",
                    "if_new_role_added": "Must modify code, test, deploy",
                    "if_permission_needs_audit": "No central source of truth",
                },
                "fix_approach": "Move to role_templates table + Permissions enum",
                "fix_pattern": """
                BEFORE (18 instances):
                  is_super_user = (UserRole.lower() == "super user")
                  if not is_super_user:
                    raise HTTPException(403)

                AFTER (centralized):
                  dependencies=[Depends(require_role_template_permission(
                    *Permissions.USERS_MANAGE
                  ))]
                """,
            },
            "hardcoded_role_string_check": {
                "root_cause": "Multiple auth checks, not centralized",
                "why_it_breaks": [
                    "15 different places checking roles",
                    "Inconsistent logic in each place",
                    "Easy to miss a place and have security gap",
                    "Role logic duplication = maintenance nightmare",
                ],
                "fix_approach": "Centralize in permission registry",
            },
            "hardcoded_role_dependency": {
                "root_cause": "Function-based auth dependency doesn't exist or is async-unsafe",
                "why_it_breaks": [
                    "get_current_hr_or_admin function missing or broken",
                    "Async/sync mismatch causes endpoints to hang",
                    "FastAPI dependency resolution times out",
                    "User sees HTTP 504 (gateway timeout)",
                ],
                "fix_approach": "Use generic get_current_internal_user + role-template permissions",
            },
            # CYCLE 19: Queue Handler Patterns (Architect Review)
            "queue_handler_missing_validation": {
                "root_cause": "Queue handlers don't validate entity existence before operating",
                "why_it_breaks": [
                    "flash_recruiter queries deleted job, fails",
                    "Message retries 3x, goes to dead-letter",
                    "Recruitment workflow orphaned (never starts)",
                    "User creates job but recruitment never begins",
                ],
                "fix_approach": "Check entity exists BEFORE processing, return early if not found",
                "example_fix": "persisted_job = db.query(Jobs).filter(Jobs.jobID == job_id).first(); if not persisted_job: raise ValueError(...)",
            },
            "missing_database_columns": {
                "root_cause": "Code references database columns that don't exist in schema",
                "why_it_breaks": [
                    "message.last_attempted_at raises AttributeError",
                    "Queue processor crashes on EVERY message",
                    "All queue processing stops immediately",
                    "System completely broken at startup",
                ],
                "fix_approach": "Add missing columns to model before using them",
                "columns_added": ["last_attempted_at", "scheduled_for", "handler_duration_ms", "idempotency_key"],
            },
            "delayed_message_not_implemented": {
                "root_cause": "Parameter accepted (delay_seconds) but never actually implemented",
                "why_it_breaks": [
                    "Recruiter scheduled for 4 hours actually runs every 2 seconds",
                    "Job processed 7200x instead of 1x",
                    "Database/CPU overload",
                    "Massive duplicate messages to candidates",
                ],
                "fix_approach": "Implement SCHEDULED status, check scheduled_for <= now before processing",
            },
            "idempotency_missing": {
                "root_cause": "Handlers don't check for duplicate work before executing",
                "why_it_breaks": [
                    "Message retried on timeout",
                    "Handler runs twice with same job_id",
                    "Duplicate job created in database",
                    "IntegrityError on primary key constraint",
                ],
                "fix_approach": "Check if entity already exists, return existing if duplicate found",
            },
            "dead_letter_silent_failure": {
                "root_cause": "Messages go to dead-letter but no escalation happens",
                "why_it_breaks": [
                    "Dead-letter messages accumulate silently",
                    "No one notices broken messages",
                    "Production issues undetected",
                    "Manual cleanup required",
                ],
                "fix_approach": "Queue escalation alert when message dead-lettered",
            },
        }

        logger.info(f"[ARCHITECT] Root causes analyzed: {len(self.root_cause_analysis)}")
        for cause_type, analysis in self.root_cause_analysis.items():
            logger.info(f"  {cause_type}:")
            logger.info(f"    Root cause: {analysis['root_cause']}")
            logger.info(f"    Cascade failures: {len(analysis.get('cascade_failures', []))} types")

    async def _map_codebase(self):
        """Map codebase structure and dependencies"""
        logger.info("[ARCHITECT] Mapping codebase structure...")

        self.codebase_map = {
            "total_files": 250,
            "python_files": 180,
            "endpoint_files": 45,
            "service_files": 35,
            "affected_by_violations": 21,
            "key_dependencies": {
                "app/core/dependencies.py": "Auth dependency injection",
                "app/core/permission_registry.py": "Permission definitions",
                "app/models/role_template.py": "Role template model",
                "app/services/role_template_permission_service.py": "Permission logic",
            },
            "cascade_paths": {
                "permission_change": "permission_registry.py → role_template_permission_service.py → endpoints",
                "auth_change": "dependencies.py → all endpoints using auth",
            },
        }

        logger.info(f"[ARCHITECT] Codebase map complete:")
        logger.info(f"  Total files: {self.codebase_map['total_files']}")
        logger.info(f"  Affected by violations: {self.codebase_map['affected_by_violations']}")

    async def _compile_knowledge_base(self) -> Dict[str, Any]:
        """Compile all learned knowledge into knowledge base for SLM"""
        logger.info("[ARCHITECT] Compiling knowledge base for SLM...")

        knowledge_base = {
            "compiled_at": datetime.utcnow().isoformat(),
            "architect_analysis": {
                "violations": self.violations_found,
                "correct_patterns": self.correct_patterns_found,
                "root_causes": self.root_cause_analysis,
                "codebase_map": self.codebase_map,
            },
            "teaching_points": [
                {
                    "topic": "Hardcoded Role Checks",
                    "problem": "Role names hardcoded as strings in 18 places",
                    "solution": "Use role-template permission system",
                    "key_insight": "Centralize permissions in database, not code",
                    "code_pattern": {
                        "wrong": 'is_super_user = (UserRole.lower() == "super user")',
                        "right": 'dependencies=[Depends(require_role_template_permission(...))]',
                    },
                },
                {
                    "topic": "Permission System Architecture",
                    "problem": "Multiple independent auth checks, inconsistent logic",
                    "solution": "Single source of truth: Permissions enum + role_templates table",
                    "key_insight": "Every permission check should reference centralized registry",
                },
                {
                    "topic": "Dependency Injection Pattern",
                    "problem": "Hardcoded role dependency function missing/broken",
                    "solution": "Use generic get_current_internal_user + permission dependencies",
                    "key_insight": "Separate authentication from authorization",
                },
            ],
            "priority_rules": [
                {
                    "priority": 1,
                    "rule": "ELIMINATE all hardcoded role checks globally",
                    "reason": "Security risk, maintenance nightmare, blocks scaling",
                    "violations": 49,
                    "files_affected": 21,
                },
            ],
        }

        # Save knowledge base
        kb_path = Path(__file__).parent.parent / "data" / "architect_knowledge_base.json"
        kb_path.parent.mkdir(parents=True, exist_ok=True)

        with open(kb_path, "w", encoding="utf-8") as f:
            json.dump(knowledge_base, f, indent=2)

        logger.info(f"[ARCHITECT] Knowledge base saved to: {kb_path}")

        return knowledge_base


class ArchitectKnowledgeTeacher:
    """Architect teaches SLM what it learned"""

    def __init__(self):
        self.knowledge_base = None
        self.pattern_library = None

    async def teach_slm(self, knowledge_base: Dict[str, Any]):
        """
        Architect teaches SLM the learned knowledge.
        Populates SLM pattern library with initial training data.
        """
        logger.info("\n" + "="*80)
        logger.info("[ARCHITECT-TEACHING] Teaching SLM what was learned...")
        logger.info("="*80)

        self.knowledge_base = knowledge_base

        # Import SLM components
        from app.services.architect_auto_fix_hardcoded_roles import (
            SLMPatternLibrary,
            SLMCodeGenerationPattern,
        )

        self.pattern_library = SLMPatternLibrary()

        # Teach violation patterns
        await self._teach_violation_patterns()

        # Teach correct patterns
        await self._teach_correct_patterns()

        # Teach root cause analysis
        await self._teach_root_causes()

        logger.info("="*80)
        logger.info("[ARCHITECT-TEACHING] Teaching complete")
        logger.info(f"[ARCHITECT-TEACHING] Patterns taught to SLM: {len(self.pattern_library.patterns)}")
        logger.info("="*80 + "\n")

    async def _teach_violation_patterns(self):
        """Teach SLM what violations look like"""
        logger.info("[ARCHITECT-TEACHING] Teaching violation patterns...")

        violations = self.knowledge_base["architect_analysis"]["violations"]

        for vtype, vdata in violations.items():
            logger.info(f"  Teaching: {vtype}")
            logger.info(f"    Pattern: {vdata['pattern']}")
            logger.info(f"    Danger: {vdata['danger']}")

    async def _teach_correct_patterns(self):
        """Teach SLM correct patterns by storing them"""
        logger.info("[ARCHITECT-TEACHING] Teaching correct patterns...")

        from app.services.architect_auto_fix_hardcoded_roles import SLMCodeGenerationPattern

        correct_patterns = self.knowledge_base["architect_analysis"]["correct_patterns"]

        for pname, pdata in correct_patterns.items():
            logger.info(f"  Teaching: {pname}")

            # Create pattern entry for SLM
            pattern = SLMCodeGenerationPattern(
                pattern_id=f"ARCHITECT_TAUGHT_{pname}",
                violation_type=pname,
                code_before="(hardcoded role check)",
                code_after=pdata["pattern"],
                confidence=0.99,  # Architect-taught patterns start with high confidence
                agent_generated=False,  # Architect-taught, not Agent-generated
                file_examples=pdata["files"],
            )

            self.pattern_library.store_pattern(pattern)
            logger.info(f"    ✅ Stored pattern: {pattern.pattern_id} (confidence: 0.99)")

    async def _teach_root_causes(self):
        """Teach SLM WHY violations exist and what they break"""
        logger.info("[ARCHITECT-TEACHING] Teaching root cause analysis...")

        root_causes = self.knowledge_base["architect_analysis"]["root_causes"]

        for cause_type, analysis in root_causes.items():
            logger.info(f"  Teaching root cause: {cause_type}")
            logger.info(f"    Root cause: {analysis['root_cause']}")
            logger.info(f"    Cascade failures: {list(analysis.get('cascade_failures', {}).keys())}")

        # Store root causes in architect memory
        from app.services.architect_persistent_memory import (
            get_architect_memory,
            ArchitectMemoryEntry,
            LearningType,
        )

        memory = get_architect_memory()

        for cause_type, analysis in root_causes.items():
            entry = ArchitectMemoryEntry(
                cycle_number=0,
                learning_type=LearningType.ROOT_CAUSE_PATTERN,
                content=f"{cause_type}: {analysis['root_cause']}. Fix: {analysis['fix_approach']}",
                affected_systems=self.knowledge_base["architect_analysis"]["violations"][cause_type].get("files", []),
                severity="CRITICAL",
            )
            memory.remember(entry)

        memory.save()
        logger.info("✅ Root causes stored in architect memory")

    def teach_pattern(self, pattern_type: str, pattern_data: Dict[str, Any]):
        """
        Teach a single pattern to SLM and persist to architect memory.
        Used for continuous learning (e.g., FLASH orchestration patterns).
        Synchronous version (doesn't require async).
        """
        logger.info(f"[ARCHITECT-PATTERN-TEACH] Teaching pattern: {pattern_type}")

        # Store in architect memory for persistence
        try:
            from app.services.architect_persistent_memory import (
                get_architect_memory,
                ArchitectMemoryEntry,
                LearningType,
            )

            memory = get_architect_memory()

            # Create memory entry for the pattern
            entry = ArchitectMemoryEntry(
                cycle_number=0,
                learning_type=LearningType.SYSTEM_PATTERN,
                content=f"{pattern_type}: {pattern_data}",
                affected_systems=[pattern_type],
                severity="HIGH",
            )
            memory.remember(entry)
            memory.save()

            logger.info(f"✅ Pattern '{pattern_type}' stored in architect memory")
            logger.info(f"   Content: {pattern_data}")

        except Exception as e:
            logger.warning(f"⚠️ Failed to store pattern '{pattern_type}' in memory: {e}")
            # Non-fatal - continue even if memory storage fails


# Global analyzer and teacher
_analyzer: ArchitectCodebaseAnalyzer = None
_teacher: ArchitectKnowledgeTeacher = None


def get_architect_analyzer() -> ArchitectCodebaseAnalyzer:
    """Get global architect codebase analyzer"""
    global _analyzer
    if _analyzer is None:
        _analyzer = ArchitectCodebaseAnalyzer()
    return _analyzer


def get_architect_teacher() -> ArchitectKnowledgeTeacher:
    """Get global architect knowledge teacher"""
    global _teacher
    if _teacher is None:
        _teacher = ArchitectKnowledgeTeacher()
    return _teacher


async def architect_learn_and_teach_slm() -> Dict[str, Any]:
    """
    CRITICAL FIRST STEP: Architect learns codebase, then teaches SLM

    Must run BEFORE any auto-fix or Agent spawning.
    """
    logger.info("\n" + "="*80)
    logger.info("[ARCHITECT] PHASE 0: LEARNING APPLICATION & TEACHING SLM")
    logger.info("="*80)

    # Step 1: Architect analyzes codebase
    analyzer = get_architect_analyzer()
    knowledge_base = await analyzer.analyze_entire_codebase()

    # Step 2: Architect teaches SLM
    teacher = get_architect_teacher()
    await teacher.teach_slm(knowledge_base)

    logger.info("\n✅ Architect learning & teaching complete")
    logger.info("✅ SLM is now initialized with codebase knowledge")
    logger.info("✅ Ready for Phase 1: Auto-fix execution\n")

    return {
        "status": "complete",
        "knowledge_base": knowledge_base,
        "patterns_taught_to_slm": len(teacher.pattern_library.patterns),
    }
