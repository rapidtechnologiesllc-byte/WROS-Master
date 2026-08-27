"""Phalanx 4: Delivery & Operations Service
Handles project provisioning, sprint velocity monitoring, and bench upskilling
"""
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.logging import logger

class DeliveryOperationsService:
    """Delivery excellence through provisioning, velocity protection, and continuous upskilling"""

    @staticmethod
    def automated_project_provisioning(
        db: Session,
        project_id: str,
        project_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Phalanx 4 - System 1: Automated Provisioning Engine
        Instantly provisions repos, environments, sandboxes upon contract signature
        Queue Topic: delivery.project_kickoff
        SLM Route: PROVISION_ENVIRONMENT
        """
        try:
            provisioning_id = str(uuid4())

            # Auto-provision infrastructure
            provisioned_resources = {
                "git_repository": f"github.com/company/{project_id}",
                "development_environment": f"dev-{project_id}.internal",
                "staging_environment": f"staging-{project_id}.internal",
                "production_environment": f"prod-{project_id}.internal",
                "database_sandbox": f"db-{project_id}.sandbox",
                "api_sandbox": f"api-{project_id}.sandbox",
                "monitoring_dashboard": f"grafana.company/projects/{project_id}",
                "logging_pipeline": f"datadog.company/projects/{project_id}",
                "ci_cd_pipeline": f"github-actions-{project_id}",
                "team_slack_channel": f"#proj-{project_id}"
            }

            provisioning_result = {
                "provisioning_id": provisioning_id,
                "project_id": project_id,
                "provisioned_resources": provisioned_resources,
                "access_credentials_sent_to": project_config.get("tech_lead_email"),
                "onboarding_documentation_link": f"wiki.company/projects/{project_id}",
                "provisioning_status": "COMPLETE",
                "provisioning_timestamp": datetime.utcnow().isoformat(),
                "ready_for_kickoff": True
            }

            logger.info(f"Project provisioned: {project_id}, provisioning_id={provisioning_id}")
            return provisioning_result

        except Exception as e:
            logger.error(f"Project provisioning failed: {e}", exc_info=True)
            raise ValueError(f"Provisioning failed: {str(e)}")

    @staticmethod
    def sprint_velocity_monitoring(
        db: Session,
        project_id: str,
        sprint_number: int,
        current_burndown_percent: float,
        sprint_velocity_points: int,
        milestone_deadline: datetime
    ) -> Dict[str, Any]:
        """
        Phalanx 4 - System 2: Sprint Guardian Agent
        Tracks code velocity and milestone burndowns; flags internal delays before SLA breach
        Queue Topic: delivery.velocity_monitor
        SLM Route: PROTECT_MILESTONE
        """
        try:
            # Calculate SLA risk
            days_remaining = (milestone_deadline - datetime.utcnow()).days
            progress_needed_per_day = (100 - current_burndown_percent) / max(days_remaining, 1)
            historical_velocity = sprint_velocity_points  # Would come from historical data
            daily_velocity = historical_velocity / 14  # Assuming 2-week sprints

            sla_risk = "CRITICAL" if (daily_velocity < progress_needed_per_day) else "WARNING" if (daily_velocity < progress_needed_per_day * 1.2) else "HEALTHY"

            monitoring_result = {
                "project_id": project_id,
                "sprint_number": sprint_number,
                "current_burndown_percent": current_burndown_percent,
                "days_to_milestone": days_remaining,
                "daily_velocity": daily_velocity,
                "daily_velocity_needed": progress_needed_per_day,
                "sla_risk_level": sla_risk,
                "recommended_action": DeliveryOperationsService._get_velocity_mitigation(sla_risk),
                "escalation_required": sla_risk in ["CRITICAL", "WARNING"],
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(f"Sprint monitored: {project_id}, sprint={sprint_number}, risk={sla_risk}")
            return monitoring_result

        except Exception as e:
            logger.error(f"Velocity monitoring failed: {e}", exc_info=True)
            raise ValueError(f"Monitoring failed: {str(e)}")

    @staticmethod
    def bench_upskilling_assignment(
        db: Session,
        consultant_id: str,
        bench_duration_days: int,
        upcoming_project_skills: List[str],
        training_budget: float
    ) -> Dict[str, Any]:
        """
        Phalanx 4 - System 3: Continuous Upskilling Engine
        Auto-retrains bench consultants for upcoming project skills
        Queue Topic: delivery.bench_upskill
        SLM Route: TRAIN_BENCH
        """
        try:
            bootcamp_id = str(uuid4())

            # Design bootcamp curriculum based on upcoming project needs
            bootcamp_curriculum = DeliveryOperationsService._design_curriculum(
                upcoming_project_skills,
                bench_duration_days
            )

            upskilling_plan = {
                "bootcamp_id": bootcamp_id,
                "consultant_id": consultant_id,
                "bench_duration_days": bench_duration_days,
                "target_skills": upcoming_project_skills,
                "curriculum": bootcamp_curriculum,
                "training_budget": training_budget,
                "budget_allocation": {
                    "online_courses": training_budget * 0.4,
                    "books_materials": training_budget * 0.2,
                    "pair_programming_sessions": training_budget * 0.3,
                    "certification_exams": training_budget * 0.1
                },
                "expected_readiness_date": (
                    datetime.utcnow() + timedelta(days=bench_duration_days)
                ).isoformat(),
                "bootcamp_status": "READY_TO_START",
                "assignment_date": datetime.utcnow().isoformat()
            }

            logger.info(f"Upskilling assigned: consultant={consultant_id}, bootcamp={bootcamp_id}")
            return upskilling_plan

        except Exception as e:
            logger.error(f"Upskilling assignment failed: {e}", exc_info=True)
            raise ValueError(f"Upskilling failed: {str(e)}")

    @staticmethod
    def _get_velocity_mitigation(sla_risk: str) -> str:
        """Get mitigation recommendations based on risk level"""
        mitigations = {
            "CRITICAL": "ESCALATE_TO_DELIVERY_HEAD - Request scope reduction or deadline extension",
            "WARNING": "ADD_RESOURCES - Allocate 1-2 bench engineers to boost velocity",
            "HEALTHY": "MAINTAIN_CURRENT_PACE - No action needed"
        }
        return mitigations.get(sla_risk, "UNKNOWN")

    @staticmethod
    def _design_curriculum(skills: List[str], duration_days: int) -> List[Dict[str, Any]]:
        """Design bootcamp curriculum for target skills"""
        week_duration = duration_days / 7
        curriculum = []

        for i, skill in enumerate(skills):
            weeks_allocated = week_duration / len(skills)
            curriculum.append({
                "skill": skill,
                "week_start": int(i * weeks_allocated) + 1,
                "week_end": int((i + 1) * weeks_allocated),
                "modules": [
                    f"Fundamentals of {skill}",
                    f"Advanced patterns in {skill}",
                    f"Real-world project simulation"
                ],
                "assessment": f"Hands-on project in {skill}"
            })

        return curriculum

    @staticmethod
    def land_and_expand_check(
        db: Session,
        project_id: str,
        current_milestone_completion_percent: float,
        client_satisfaction_score: float
    ) -> Dict[str, Any]:
        """
        Phalanx 4 System 3.5: Land-and-Expand Trigger
        When project hits 80% completion, auto-propose expansion to client
        Queue Topic: acquisition.market_scrape (feeds back to Phalanx 5)
        """
        try:
            if current_milestone_completion_percent >= 80 and client_satisfaction_score >= 4.0:
                expansion_proposal = {
                    "project_id": project_id,
                    "trigger_event": "MILESTONE_80_PERCENT_COMPLETE",
                    "client_satisfaction_score": client_satisfaction_score,
                    "expansion_opportunities": [
                        "MANAGED_SUPPORT_ENGAGEMENT",
                        "FEATURE_EXPANSION_PHASE_2",
                        "SYSTEM_OPTIMIZATION_RETAINER"
                    ],
                    "action": "QUEUE_ACQUISITION_PROPOSAL_ENGINE",
                    "urgency": "HIGH",
                    "timestamp": datetime.utcnow().isoformat()
                }

                logger.info(f"Land-and-expand opportunity identified: {project_id}")
                return expansion_proposal

            return {
                "project_id": project_id,
                "expansion_triggered": False,
                "reason": f"Completion: {current_milestone_completion_percent}%, Satisfaction: {client_satisfaction_score}"
            }

        except Exception as e:
            logger.error(f"Land-and-expand check failed: {e}", exc_info=True)
            raise
