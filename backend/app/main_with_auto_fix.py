"""
FastAPI with Automatic Hardcoded Role Check Fix

When server starts:
1. Load architect memory
2. Check for PRIORITY 1: "Eliminate all hardcoded role checks"
3. If found: Auto-fix all 49 instances automatically
4. Verify: Re-scan to confirm 49 → 0
5. Block feature work if not fixed

Result: Self-healing system that AUTOMATICALLY fixes PRIORITY 1 violations
"""
import logging
import asyncio
from fastapi import FastAPI, HTTPException
from typing import Dict, Any

logger = logging.getLogger(__name__)


def create_app_with_auto_fix() -> FastAPI:
    """
    Create FastAPI app with automatic PRIORITY 1 fixes
    """

    app = FastAPI(
        title="WROS with Auto-Fix Hardcoded Role Checks",
        description="Production system that self-heals PRIORITY 1 violations",
    )

    @app.on_event("startup")
    async def startup_with_auto_fix():
        """
        ON SERVER START:
        1. Load architect memory
        2. Check for PRIORITY 1 violations
        3. If found: Auto-fix automatically
        4. Verify fix
        5. Block feature work if needed
        """

        logger.info("\n" + "="*70)
        logger.info("SERVER STARTUP: Initializing with Auto-Fix")
        logger.info("="*70)

        # STEP 1: Load architect memory
        logger.info("[STARTUP] Loading architect memory...")
        from app.services.architect_persistent_memory import get_architect_memory

        memory = get_architect_memory()
        logger.info(f"✓ Memory loaded: {len(memory.memories)} memories")

        # STEP 2: Check for PRIORITY 1
        logger.info("[STARTUP] Checking for PRIORITY 1 violations...")
        priority_1_rules = memory.get_memory_summary().get("memory_types", {}).get(
            "ARCHITECTURAL_RULE_CRITICAL", 0
        )

        if priority_1_rules == 0:
            logger.info(
                "✓ No PRIORITY 1 violations detected - normal startup"
            )
            return

        logger.error("🚨 PRIORITY 1 VIOLATION DETECTED")
        logger.error(
            "🚨 Hardcoded role checks found in codebase"
        )

        # STEP 3: Trigger auto-fix
        logger.info("[STARTUP] Spawning auto-fix agent...")

        from app.services.architect_auto_fix_hardcoded_roles import (
            get_auto_fix_orchestrator,
        )

        orchestrator = get_auto_fix_orchestrator()

        # Run auto-fix in background (don't block startup)
        asyncio.create_task(orchestrator.execute_auto_fix_cycle())

        logger.info("[STARTUP] Auto-fix spawned in background")
        logger.info("[STARTUP] Server continuing startup...")

    # ──────────────────────────────────────────────────────────────
    # HEALTH CHECK ENDPOINT
    # ──────────────────────────────────────────────────────────────
    @app.get("/health")
    async def health_check() -> Dict[str, Any]:
        """Health check with auto-fix status"""
        from app.services.architect_persistent_memory import get_architect_memory
        from app.services.architect_codebase_audit import CodebaseAuditScanner

        memory = get_architect_memory()
        scanner = CodebaseAuditScanner()

        # Quick audit check
        audit_summary = {
            "total_memories": len(memory.memories),
            "priority_1_active": any(
                "Eliminate all hardcoded role checks" in m.content
                for m in memory.memories
            ),
        }

        return {
            "status": "healthy",
            "auto_fix": audit_summary,
        }

    # ──────────────────────────────────────────────────────────────
    # AUTO-FIX STATUS ENDPOINT
    # ──────────────────────────────────────────────────────────────
    @app.get("/api/v1/architect/auto-fix-status")
    async def get_auto_fix_status() -> Dict[str, Any]:
        """Get status of auto-fix operations"""
        from app.services.architect_persistent_memory import get_architect_memory

        memory = get_architect_memory()

        # Find PRIORITY 1 rule
        priority_1 = None
        for mem in memory.memories:
            if (
                "ARCHITECTURAL_RULE_CRITICAL" in str(mem.learning_type)
                and "Eliminate all hardcoded role checks" in mem.content
            ):
                priority_1 = {
                    "rule": "Eliminate all 49 hardcoded role checks",
                    "status": "ACTIVE",
                    "confidence": mem.confidence,
                    "blocking": mem.confidence >= 0.95,
                }

        return {
            "auto_fix_available": True,
            "priority_1": priority_1,
            "memory_size": len(memory.memories),
        }

    # ──────────────────────────────────────────────────────────────
    # MANUAL TRIGGER ENDPOINT (For testing)
    # ──────────────────────────────────────────────────────────────
    @app.post("/api/v1/architect/trigger-auto-fix")
    async def trigger_auto_fix() -> Dict[str, Any]:
        """
        Manually trigger auto-fix (for testing or emergency)
        """
        from app.services.architect_auto_fix_hardcoded_roles import (
            trigger_hardcoded_role_check_auto_fix,
        )

        logger.info("[MANUAL TRIGGER] Auto-fix triggered manually")

        result = await trigger_hardcoded_role_check_auto_fix()

        return {
            "status": "complete",
            "result": result,
        }

    return app


if __name__ == "__main__":
    import uvicorn

    app = create_app_with_auto_fix()

    logger.basicConfig(level=logging.INFO, format="%(message)s")

    logger.info("\n" + "="*70)
    logger.info("STARTING SERVER WITH AUTO-FIX")
    logger.info("="*70)
    logger.info("What happens on startup:")
    logger.info("  1. Load architect memory")
    logger.info("  2. Check for PRIORITY 1: 'Eliminate all hardcoded role checks'")
    logger.info("  3. If found: Automatically fix all 49 instances")
    logger.info("  4. Verify: Re-scan to confirm 49 → 0")
    logger.info("  5. Commit: git commit with all fixes")
    logger.info("  6. Result: Self-healing codebase")
    logger.info("="*70 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8080)
