"""
FastAPI app with Architect Monitoring integrated at startup

When server starts:
1. Load architect persistent memory
2. Start production monitoring (background)
3. Ruthless architect runs every 5 minutes
4. If issues found, doctor agent spawned automatically
5. All findings logged and tracked

Example usage in backend/app/main.py:

```python
from app.main_with_architect_monitoring import create_app_with_monitoring

app = create_app_with_monitoring()
```

Then run:
```
uvicorn app.main:app --reload
```

Every 5 minutes:
- Architect analyzes system
- Findings logged
- Blocking issues trigger auto-fix attempts
"""
import logging
import asyncio
from fastapi import FastAPI, HTTPException
from typing import Dict, Any

logger = logging.getLogger(__name__)


def create_app_with_monitoring() -> FastAPI:
    """
    Create FastAPI app with architect monitoring enabled
    """

    # Import existing app or create new
    # For now, creating minimal example
    app = FastAPI(
        title="WROS with Production Architect Monitor",
        description="Autonomous recruitment system with continuous monitoring",
    )

    # ──────────────────────────────────────────────────────────────
    # ON STARTUP: Initialize architect system
    # ──────────────────────────────────────────────────────────────
    @app.on_event("startup")
    async def startup_architect_monitoring():
        """Initialize architect monitoring on server startup"""
        logger.info("\n" + "="*70)
        logger.info("STARTUP: Initializing Production Architect Monitor")
        logger.info("="*70)

        # Load architect memory from disk
        from app.services.architect_persistent_memory import get_architect_memory

        memory = get_architect_memory()
        logger.info(f"✓ Architect memory loaded: {len(memory.memories)} memories")
        logger.info(f"✓ Cascade patterns known: {len(memory.cascade_matrix)}")
        logger.info(f"✓ Anti-patterns tracked: {len(memory.get_recurring_anti_patterns())}")

        # Start production monitoring in background
        from app.services.production_architect_monitor import start_production_monitoring

        asyncio.create_task(start_production_monitoring())
        logger.info("✓ Production monitoring started (every 5 minutes)")

        logger.info("\n" + "="*70)
        logger.info("STARTUP COMPLETE: System running with autonomous monitoring")
        logger.info("="*70 + "\n")

    # ──────────────────────────────────────────────────────────────
    # HEALTH CHECK ENDPOINT
    # ──────────────────────────────────────────────────────────────
    @app.get("/health")
    async def health_check() -> Dict[str, Any]:
        """
        Health check endpoint that includes production status
        """
        from app.services.production_architect_monitor import get_production_status
        from app.services.architect_persistent_memory import get_architect_memory

        memory = get_architect_memory()
        status = get_production_status()

        return {
            "status": "healthy",
            "memory": {
                "total_memories": len(memory.memories),
                "cascade_patterns": len(memory.cascade_matrix),
            },
            "monitoring": status,
        }

    # ──────────────────────────────────────────────────────────────
    # ARCHITECT STATUS ENDPOINT
    # ──────────────────────────────────────────────────────────────
    @app.get("/api/v1/architect/status")
    async def get_architect_status() -> Dict[str, Any]:
        """Get architect system status"""
        from app.services.architect_persistent_memory import get_architect_memory
        from app.services.production_architect_monitor import get_production_monitor

        memory = get_architect_memory()
        monitor = get_production_monitor()

        return {
            "architect": {
                "total_memories": len(memory.memories),
                "memory_types": memory._count_by_type(),
                "cascade_patterns": len(memory.cascade_matrix),
                "recurring_anti_patterns": len(memory.get_recurring_anti_patterns()),
                "most_confident": [m.to_dict() for m in sorted(
                    memory.memories, key=lambda m: -m.confidence
                )[:3]],
            },
            "monitoring": {
                "blocking_issues": monitor.blocking_issue_count,
                "total_notes": len(monitor.notes),
                "recurring_patterns": monitor.patterns_detected,
                "last_check": monitor.last_check.isoformat() if monitor.last_check else None,
            },
        }

    # ──────────────────────────────────────────────────────────────
    # ARCHITECT MEMORY ENDPOINT
    # ──────────────────────────────────────────────────────────────
    @app.get("/api/v1/architect/memory")
    async def get_architect_memory_endpoint() -> Dict[str, Any]:
        """Get architect's complete memory"""
        from app.services.architect_persistent_memory import get_architect_memory

        memory = get_architect_memory()
        return memory.get_memory_summary()

    # ──────────────────────────────────────────────────────────────
    # PRODUCTION NOTES ENDPOINT
    # ──────────────────────────────────────────────────────────────
    @app.get("/api/v1/architect/notes")
    async def get_production_notes() -> Dict[str, Any]:
        """Get production monitoring notes"""
        from app.services.production_architect_monitor import get_production_monitor

        monitor = get_production_monitor()
        status = monitor.get_monitoring_status()

        return {
            "status": status,
            "blocking_issues": monitor.blocking_issue_count,
            "recent_events": [note.to_dict() for note in monitor.notes[-20:]],
        }

    # ──────────────────────────────────────────────────────────────
    # TRIGGER ARCHITECT ANALYSIS ENDPOINT (Manual)
    # ──────────────────────────────────────────────────────────────
    @app.post("/api/v1/architect/analyze")
    async def trigger_architect_analysis() -> Dict[str, Any]:
        """
        Manually trigger architect analysis (for testing/debugging)
        """
        from app.services.ruthless_architect import get_ruthless_architect

        logger.info("[API] Manual architect analysis triggered")

        architect = get_ruthless_architect()
        analysis = await architect.analyze_cycle(cycle_number=999)

        blocking = analysis.get_blocking_issues()
        high = [f for f in analysis.findings if "HIGH" in f.severity.value]

        return {
            "analysis_triggered": True,
            "total_findings": len(analysis.findings),
            "blocking_count": len(blocking),
            "high_count": len(high),
            "summary": {
                "blocking": [
                    {"title": f.title, "file": f.file} for f in blocking[:5]
                ],
                "high": [
                    {"title": f.title, "file": f.file} for f in high[:5]
                ],
            },
        }

    # ──────────────────────────────────────────────────────────────
    # RUN AUTONOMOUS CYCLE ENDPOINT (Manual)
    # ──────────────────────────────────────────────────────────────
    @app.post("/api/v1/sdlc/run-cycle")
    async def run_autonomous_cycle(num_cycles: int = 1) -> Dict[str, Any]:
        """
        Manually run autonomous SDLC cycle (for testing)
        Spawns in background
        """
        from app.services.sdlc_cycle_with_learning import AutonomousSDLCCycleWithLearning

        logger.info(f"[API] Spawning {num_cycles} autonomous cycles")

        runner = AutonomousSDLCCycleWithLearning()
        asyncio.create_task(runner.run_continuous_learning_cycles(num_cycles=num_cycles))

        return {
            "cycles_queued": num_cycles,
            "status": "running_in_background",
            "check_status_at": "/api/v1/architect/status",
        }

    return app


if __name__ == "__main__":
    import uvicorn

    app = create_app_with_monitoring()

    logger.info("\n" + "="*70)
    logger.info("STARTING SERVER WITH ARCHITECT MONITORING")
    logger.info("="*70)
    logger.info("Production architect monitor will:")
    logger.info("  1. Load architect memory from disk")
    logger.info("  2. Run ruthless analysis every 5 minutes")
    logger.info("  3. Log all findings")
    logger.info("  4. Spawn doctor agent for blocking issues")
    logger.info("  5. Track recurring patterns")
    logger.info("\nEndpoints:")
    logger.info("  GET  /health - Basic health check")
    logger.info("  GET  /api/v1/architect/status - Architect system status")
    logger.info("  GET  /api/v1/architect/memory - Architect's memory")
    logger.info("  GET  /api/v1/architect/notes - Production notes")
    logger.info("  POST /api/v1/architect/analyze - Manual analysis")
    logger.info("  POST /api/v1/sdlc/run-cycle - Manual SDLC cycle")
    logger.info("="*70 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8080)
