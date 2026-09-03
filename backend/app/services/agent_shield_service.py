import logging
from app.core.logging import logger
"""Agent Shield Service - Spartan Phalanx formation monitoring and integrity checks."""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from app.models.agent_phalanx import (
    AgentInFormation, ShieldWatch, PhalanxAlert, FormationIntegrity, AgentPhalanxFormation
)
from app.services.agent_registry_service import AGENT_REGISTRY

logger = logging.getLogger(__name__)

class ShieldStrengthCalculator:
    """Calculate shield strength using Spartan phalanx metrics."""

    @staticmethod
    def calculate_shield_strength(
        success_rate: float,
        latency_ms: int,
        quality_score: float,
        confidence: float,
        sla_latency_ms: int = 2000,
    ) -> float:
        """
        Calculate how strong an agent's shield is (0-100%).

        Shield Strength = (success_rate * 0.40) + (latency_compliance * 0.30) +
                         (quality * 0.20) + (confidence * 0.10)

        Weighted priorities:
        - Reliability (success rate): 40% — the shield must hold
        - Speed (latency): 30% — must protect quickly
        - Quality: 20% — must be trustworthy
        - Confidence: 10% — must be certain
        """

        # Success rate: primary metric
        reliability = min(success_rate / 100.0, 1.0)

        # Latency: 1.0 if within SLA, 0.5 if exceeded
        latency_compliance = 1.0 if latency_ms <= sla_latency_ms else 0.5

        # Quality: 0-100 scale
        quality = min(quality_score / 100.0, 1.0)

        # Confidence: 0-100 scale
        confidence_norm = min(confidence / 100.0, 1.0)

        # Calculate weighted shield strength
        shield = (
            reliability * 0.40 +
            latency_compliance * 0.30 +
            quality * 0.20 +
            confidence_norm * 0.10
        )

        return min(shield * 100.0, 100.0)  # Return 0-100

    @staticmethod
    def get_shield_status(shield_strength: float) -> str:
        """Classify shield status based on strength."""
        if shield_strength >= 90:
            return "HEALTHY"
        elif shield_strength >= 70:
            return "WEAKENING"
        elif shield_strength >= 50:
            return "FAILING"
        else:
            return "BROKEN"


class PhalanxFormationService:
    """Service for managing Spartan phalanx formations."""

    # The three main phalanxes
    PHALANXES = {
        "Recruitment": {
            "agents": ["Thunder", "Recruitment Agent", "Interview Reminder Agent", "HR Agent", "Onboarding Agent"],
            "formation_sla": 0.95,  # 95% formation integrity required
        },
        "Resource": {
            "agents": ["Resource Management Agent", "Utilization Agent", "Revenue Agent"],
            "formation_sla": 0.90,
        },
        "Finance": {
            "agents": ["Opportunity Tracker Agent", "CFO Agent", "Revenue Recognition Agent", "Margin Agent", "KPI Agent"],
            "formation_sla": 0.92,
        },
    }

    @staticmethod
    def initialize_phalanx_formation(db: Session, phalanx_name: str, agents: List[str]) -> bool:
        """Initialize a phalanx formation with agent positions."""

        try:
            # Create formation record
            formation = AgentPhalanxFormation(
                formation_id=f"phalanx_{phalanx_name.lower().replace(' ', '_')}_001",
                phalanx_name=phalanx_name,
                position_count=len(agents),
            )
            db.add(formation)
            db.flush()

            # Assign agents to positions
            for position, agent_name in enumerate(agents, start=1):
                left_neighbor = agents[position - 2] if position > 1 else None
                right_neighbor = agents[position] if position < len(agents) else None

                # Get agent config from registry
                agent_config = AGENT_REGISTRY.get(agent_name, {})

                assignment = AgentInFormation(
                    assignment_id=f"aif_{agent_name.lower().replace(' ', '_')}_001",
                    phalanx_name=phalanx_name,
                    agent_name=agent_name,
                    position=position,
                    left_neighbor=left_neighbor,
                    right_neighbor=right_neighbor,
                    shield_sla=agent_config.get("shield_sla", "Unknown SLA"),
                    shield_failure_action=agent_config.get("shield_failure_action", "KILL_SWITCH"),
                    flank_vulnerabilities=agent_config.get("flank_vulnerabilities", []),
                    flank_coverage_expected=agent_config.get("flank_coverage_expected", ""),
                    monitor_left_neighbor=agent_config.get("monitor_left_neighbor", False),
                    monitor_right_neighbor=agent_config.get("monitor_right_neighbor", False),
                    shield_watch_interval=agent_config.get("shield_watch_interval", 60),
                )
                db.add(assignment)

            db.commit()
            return True

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            print(f"Error initializing phalanx formation: {e}")
            return False

    @staticmethod
    def update_shield_strength(
        db: Session,
        phalanx_name: str,
        agent_name: str,
        success_rate: float,
        latency_ms: int,
        quality_score: float,
        confidence: float,
    ) -> Dict:
        """Update an agent's shield strength and check formation integrity."""

        try:
            # Find agent in formation
            agent_in_formation = db.query(AgentInFormation).filter(
                AgentInFormation.phalanx_name == phalanx_name,
                AgentInFormation.agent_name == agent_name,
            ).first()

            if not agent_in_formation:
                return {"status": "error", "message": "Agent not found in formation"}

            # Calculate shield strength
            agent_config = AGENT_REGISTRY.get(agent_name, {})
            sla_latency = agent_config.get("sla_latency_ms", 2000)

            shield_strength = ShieldStrengthCalculator.calculate_shield_strength(
                success_rate, latency_ms, quality_score, confidence, sla_latency
            )
            shield_status = ShieldStrengthCalculator.get_shield_status(shield_strength)

            # Update agent record
            agent_in_formation.shield_strength = shield_strength
            agent_in_formation.shield_status = shield_status
            agent_in_formation.last_shield_check = datetime.utcnow()

            # Check for alert conditions
            alerts = []
            if shield_strength < 50:  # BROKEN
                alerts.append(
                    PhalanxFormationService._create_phalanx_alert(
                        db, phalanx_name, agent_name, shield_strength, "shield_failing"
                    )
                )
            elif shield_strength < 70:  # FAILING
                alerts.append(
                    PhalanxFormationService._create_phalanx_alert(
                        db, phalanx_name, agent_name, shield_strength, "shield_weakening"
                    )
                )

            # Check neighbor exposure
            if agent_in_formation.left_neighbor:
                PhalanxFormationService._check_neighbor_exposure(
                    db, phalanx_name, agent_name, agent_in_formation.left_neighbor, shield_strength
                )

            db.commit()

            return {
                "status": "updated",
                "agent_name": agent_name,
                "shield_strength": shield_strength,
                "shield_status": shield_status,
                "alerts": len(alerts),
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            return {"status": "error", "message": str(e)}

    @staticmethod
    def _create_phalanx_alert(
        db: Session,
        phalanx_name: str,
        agent_name: str,
        shield_strength: float,
        alert_type: str,
    ) -> PhalanxAlert:
        """Create a phalanx alert when shield weakens."""

        severity = "CRITICAL" if shield_strength < 50 else "WARNING"
        description = f"{agent_name}'s shield at {shield_strength:.0f}% - ({alert_type})"

        alert = PhalanxAlert(
            alert_id=f"alert_{phalanx_name.lower()}_{agent_name.lower()}_001",
            phalanx_name=phalanx_name,
            source_agent=agent_name,
            alert_type=alert_type,
            severity=severity,
            description=description,
            metrics={"shield_strength": shield_strength},
            detected_at=datetime.utcnow(),
        )

        db.add(alert)
        return alert

    @staticmethod
    def _check_neighbor_exposure(
        db: Session,
        phalanx_name: str,
        agent_name: str,
        left_neighbor: str,
        shield_strength: float,
    ) -> None:
        """Check if agent's shield failure exposes left neighbor."""

        if shield_strength < 70:  # Shield weakening
            # Left neighbor is exposed
            alert = PhalanxAlert(
                alert_id=f"alert_{phalanx_name.lower()}_{left_neighbor.lower()}_exposed_001",
                phalanx_name=phalanx_name,
                source_agent=agent_name,
                alert_type="neighbor_down",
                severity="CRITICAL",
                description=f"{left_neighbor} is EXPOSED - {agent_name}'s shield failing",
                affected_agents=[left_neighbor],
                impact_description=f"If {agent_name} shield fails, {left_neighbor} has no defense",
                detected_at=datetime.utcnow(),
            )
            db.add(alert)

    @staticmethod
    def calculate_formation_integrity(db: Session, phalanx_name: str) -> Dict:
        """Calculate overall phalanx formation integrity (0-100%)."""

        try:
            # Get all agents in formation
            agents = db.query(AgentInFormation).filter(
                AgentInFormation.phalanx_name == phalanx_name
            ).all()

            if not agents:
                return {"status": "error", "message": "No agents in formation"}

            # Calculate statistics
            shield_strengths = [a.shield_strength for a in agents]
            healthy = sum(1 for s in shield_strengths if s >= 90)
            weakening = sum(1 for s in shield_strengths if 70 <= s < 90)
            failing = sum(1 for s in shield_strengths if 50 <= s < 70)
            broken = sum(1 for s in shield_strengths if s < 50)

            # Formation integrity = weighted average
            formation_strength = sum(shield_strengths) / len(agents)

            # Determine status
            if broken > 0:
                overall_status = "BROKEN"
            elif failing > 0:
                overall_status = "WEAKENING"
            else:
                overall_status = "OPERATIONAL"

            # Find weakest and strongest
            weakest = min(agents, key=lambda a: a.shield_strength)
            strongest = max(agents, key=lambda a: a.shield_strength)

            # Create/update formation integrity record
            integrity = db.query(FormationIntegrity).filter(
                FormationIntegrity.phalanx_name == phalanx_name
            ).first() or FormationIntegrity(
                integrity_id=f"fi_{phalanx_name.lower()}_001",
                phalanx_name=phalanx_name,
            )

            integrity.formation_strength = formation_strength
            integrity.overall_status = overall_status
            integrity.healthy_shields = healthy
            integrity.weakening_shields = weakening
            integrity.failing_shields = failing
            integrity.weakest_position = weakest.position
            integrity.weakest_shield_strength = weakest.shield_strength
            integrity.strongest_position = strongest.position
            integrity.strongest_shield_strength = strongest.shield_strength
            integrity.breach_risk_score = 100 - formation_strength

            db.add(integrity)
            db.commit()

            return {
                "status": "calculated",
                "phalanx_name": phalanx_name,
                "formation_strength": formation_strength,
                "overall_status": overall_status,
                "healthy_shields": healthy,
                "weakening_shields": weakening,
                "failing_shields": failing,
                "broken_shields": broken,
                "weakest_position": weakest.position,
                "weakest_shield_strength": weakest.shield_strength,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

    @staticmethod
    def get_phalanx_status(db: Session, phalanx_name: str) -> Dict:
        """Get complete phalanx formation status."""

        try:
            # Get all agents in formation
            agents = db.query(AgentInFormation).filter(
                AgentInFormation.phalanx_name == phalanx_name
            ).order_by(AgentInFormation.position).all()

            # Get formation integrity
            integrity = db.query(FormationIntegrity).filter(
                FormationIntegrity.phalanx_name == phalanx_name
            ).first()

            # Get recent alerts
            recent_alerts = db.query(PhalanxAlert).filter(
                PhalanxAlert.phalanx_name == phalanx_name,
                PhalanxAlert.detected_at > datetime.utcnow() - timedelta(hours=24),
            ).all()

            # Build response
            agent_status = [
                {
                    "position": a.position,
                    "agent_name": a.agent_name,
                    "left_neighbor": a.left_neighbor,
                    "right_neighbor": a.right_neighbor,
                    "shield_strength": a.shield_strength,
                    "shield_status": a.shield_status,
                    "sla": a.shield_sla,
                }
                for a in agents
            ]

            return {
                "status": "retrieved",
                "phalanx_name": phalanx_name,
                "formation_strength": integrity.formation_strength if integrity else 0,
                "overall_status": integrity.overall_status if integrity else "UNKNOWN",
                "agents": agent_status,
                "alerts": len(recent_alerts),
                "recent_alert_types": [a.alert_type for a in recent_alerts],
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}
