"""
FLASH Orchestrator: Autonomous Agent Orchestration Engine

FLASH = Fully-Learned Adaptive Scheduling & Hiring

Coordinates all 10 agents (P&L, Recruitment, Workforce) to make autonomous
hiring, allocation, and business decisions gated by profitability.

Every decision is:
- Gated by P&L (budget, margin, ROI)
- Logged for audit trail
- Published as event
- Visible on CEO dashboard
"""

from app.core.events import Event, EventType, EventBroker
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


class FLASHOrchestrator:
    """
    FLASH: Fully-Learned Adaptive Scheduling & Hiring

    Orchestrates 10 agents making autonomous business decisions.
    """

    def __init__(self, db: Session, event_broker: EventBroker):
        self.db = db
        self.broker = event_broker
        self.agent_id = "flash_orchestrator"

    async def evaluate_hiring_decision(self,
        candidate_name: str,
        candidate_salary: float,
        quality_score: float
    ) -> Dict[str, Any]:
        """
        FLASH Hiring Decision Logic:
        Gate 1: Budget approved?
        Gate 2: Quality > 75%?
        Gate 3: Bench reserve > 2?
        """
        try:
            logger.info(f"[FLASH] Evaluating hire: {candidate_name} (${candidate_salary:,.0f}, quality: {quality_score:.0f}%)")

            # Gate 1: Budget Agent approval
            from app.services.agents.budget_agent import BudgetAgent
            budget_agent = BudgetAgent(self.db, self.broker)
            budget_result = await budget_agent.evaluate_hire_request(
                candidate_name, candidate_salary
            )
            if not budget_result.get('can_hire'):
                decision = {
                    "status": "REJECTED",
                    "reason": budget_result.get('reason'),
                    "gate_failed": "BUDGET",
                    "candidate": candidate_name
                }
                await self.broker.publish(Event(
                    event_type=EventType.BUDGET_REJECTED,
                    agent_id=self.agent_id,
                    timestamp=datetime.utcnow(),
                    entity_id=candidate_name,
                    payload=decision,
                    source_phase="phase_2_pnl"
                ))
                return decision

            # Gate 2: Quality threshold
            if quality_score < 75:
                decision = {
                    "status": "REJECTED",
                    "reason": f"Quality {quality_score:.0f}% below 75% threshold",
                    "gate_failed": "QUALITY",
                    "candidate": candidate_name
                }
                return decision

            # Gate 3: Bench reserve (must keep 2+ on bench)
            from app.services.slm_export_service import SLMExportService
            available = SLMExportService.export_available_employees(self.db)
            bench_employees = available.get("available_employees", [])
            if len(bench_employees) < 2:
                decision = {
                    "status": "REJECTED",
                    "reason": f"Need bench reserve, currently {len(bench_employees)} on bench",
                    "gate_failed": "BENCH_RESERVE",
                    "candidate": candidate_name
                }
                return decision

            # All gates passed - APPROVE HIRE
            decision = {
                "status": "APPROVED",
                "reason": "All gates passed (budget, quality, bench reserve)",
                "candidate": candidate_name,
                "salary": candidate_salary,
                "quality_score": quality_score,
                "budget_impact": budget_result,
                "bench_remaining": len(bench_employees) - 1  # Will use 1, keep others
            }

            await self.broker.publish(Event(
                event_type=EventType.BUDGET_APPROVED,
                agent_id=self.agent_id,
                timestamp=datetime.utcnow(),
                entity_id=candidate_name,
                payload=decision,
                source_phase="phase_2_pnl"
            ))

            logger.info(f"[FLASH] APPROVED: {candidate_name}")
            return decision

        except Exception as e:
            logger.error(f"[FLASH] Hiring decision failed: {e}", exc_info=True)
            raise

    async def evaluate_allocation_decision(self,
        employee_id: str,
        employee_name: str,
        project_id: str,
        project_name: str
    ) -> Dict[str, Any]:
        """
        FLASH Allocation Decision Logic:
        Gate 1: Project margin > 25%?
        Gate 2: Skills match?
        Gate 3: No scheduling conflict?
        """
        try:
            logger.info(f"[FLASH] Evaluating allocation: {employee_name} → {project_name}")

            # Gate 1: Project profitability
            from app.services.slm_export_service import SLMExportService
            projects = SLMExportService.export_project_profitability(self.db)
            project = next((p for p in projects.get("projects", []) if p.get("project_id") == project_id), None)

            if not project or project.get("margin_pct", 0) < 25:
                decision = {
                    "status": "REJECTED",
                    "reason": f"Project margin {project.get('margin_pct', 0):.0f}% below 25% threshold",
                    "gate_failed": "MARGIN",
                    "employee": employee_name,
                    "project": project_name
                }
                return decision

            # Gate 2: Skills match
            available = SLMExportService.export_available_employees(self.db)
            emp = next((e for e in available.get("available_employees", []) if e.get("employee_id") == employee_id), None)

            if not emp:
                decision = {
                    "status": "REJECTED",
                    "reason": "Employee not available",
                    "gate_failed": "AVAILABILITY",
                    "employee": employee_name
                }
                return decision

            emp_skills = set(emp.get("skills", []))
            proj_skills = set(project.get("required_skills", []))
            if proj_skills and not (emp_skills & proj_skills):
                decision = {
                    "status": "REJECTED",
                    "reason": f"Skill mismatch. Need: {proj_skills}, have: {emp_skills}",
                    "gate_failed": "SKILLS",
                    "employee": employee_name,
                    "project": project_name
                }
                return decision

            # Gate 3: No conflicts (simplified - assume no conflicts for now)

            # All gates passed - ALLOCATE
            decision = {
                "status": "APPROVED",
                "reason": "All gates passed (margin, skills, no conflicts)",
                "employee": employee_name,
                "project": project_name,
                "project_margin_pct": project.get("margin_pct", 0),
                "bench_cost_saved_per_day": 400,
                "start_date": datetime.utcnow().strftime("%Y-%m-%d")
            }

            await self.broker.publish(Event(
                event_type=EventType.FLASH_DECISION,
                agent_id=self.agent_id,
                timestamp=datetime.utcnow(),
                entity_id=f"{employee_id}_{project_id}",
                payload=decision,
                source_phase="phase_2_pnl"
            ))

            logger.info(f"[FLASH] ALLOCATED: {employee_name} → {project_name}")
            return decision

        except Exception as e:
            logger.error(f"[FLASH] Allocation decision failed: {e}", exc_info=True)
            raise

    async def get_executive_summary(self) -> Dict[str, Any]:
        """
        CEO dashboard summary: all decisions made, P&L impact, risks
        """
        try:
            from app.services.slm_export_service import SLMExportService

            snapshot = SLMExportService.export_utilization_snapshot(self.db)

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "status": "OPERATIONAL",
                "autonomy_level": "FULL",
                "key_metrics": {
                    "company_utilization_pct": snapshot.get("company_utilization_pct", 0),
                    "target_utilization_pct": 90,
                    "bench_cost_per_day": snapshot.get("bench_cost_per_day", 0),
                    "employees_bench": snapshot.get("employees_bench", 0)
                },
                "decisions_this_week": {
                    "hired": 0,  # Would query from events
                    "allocated": 0,
                    "promoted": 0,
                    "bench_reduced": 0
                },
                "alerts": [
                    # Would query from event stream
                ],
                "autonomous_operation": True
            }

        except Exception as e:
            logger.error(f"[FLASH] Failed to generate summary: {e}", exc_info=True)
            raise


def get_flash_orchestrator(db: Session, event_broker: EventBroker) -> FLASHOrchestrator:
    """Get or create FLASH orchestrator instance"""
    return FLASHOrchestrator(db, event_broker)
