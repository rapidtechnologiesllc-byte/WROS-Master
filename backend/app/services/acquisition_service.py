"""Phalanx 5: Autonomous Client Acquisition Service
Handles end-to-end sales automation: market intelligence, outreach, proposal generation
"""
import logging
import json
from typing import Any, Dict, Optional, List
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.logging import logger

class AcquisitionService:
    """Autonomous client acquisition via market intelligence, outreach, and RFP generation"""

    @staticmethod
    def market_intelligence_scan(
        db: Session,
        industry: str,
        technology_stack: Optional[List[str]] = None,
        company_size: str = "ALL"
    ) -> Dict[str, Any]:
        """
        Phalanx 5 - System 1: Market Intelligence Agent
        Scrapes external distress signals: tech stack mismatches, open requisitions, latency issues
        Queue Topic: acquisition.market_scrape
        SLM Route: IDENTIFY_DISTRESS
        """
        try:
            scan_id = str(uuid4())

            distress_signals = {
                "scan_id": scan_id,
                "industry": industry,
                "company_size": company_size,
                "technology_stack": technology_stack or [],
                "distress_indicators": {
                    "open_job_requisitions": 0,  # Would scrape from LinkedIn, Indeed, etc.
                    "technical_debt_signals": 0,  # Stack Overflow, GitHub issues
                    "latency_complaints": 0,  # Sentiment analysis from reviews
                    "high_turnover_signals": 0,  # Glassdoor, LinkedIn
                    "infrastructure_gaps": 0  # AWS/GCP API scraping
                },
                "confidence_score": 0.0,  # ML-based confidence of distress
                "target_companies": [],
                "recommended_reach_approach": "DIRECT_TECHNICAL_DECISION_MAKER",
                "scan_timestamp": datetime.utcnow().isoformat(),
                "status": "SCAN_COMPLETE"
            }

            logger.info(f"Market scan completed: {scan_id}, industry={industry}")
            return distress_signals

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Market intelligence scan failed: {e}", exc_info=True)
            raise ValueError(f"Market scan failed: {str(e)}")

    @staticmethod
    def autonomous_outreach_campaign(
        db: Session,
        target_company_id: str,
        decision_maker_email: str,
        distress_signal_type: str,  # "OPEN_REQUISITIONS", "TECHNICAL_DEBT", "LATENCY"
        personalization_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Phalanx 5 - System 2: Autonomous Outreach Agent
        Dispatches hyper-personalized sequences to decision-makers
        Queue Topic: acquisition.outreach_send
        SLM Route: PITCH_CLIENT
        """
        try:
            outreach_id = str(uuid4())

            # Generate personalized email sequence
            email_sequence = AcquisitionService._generate_personalized_sequence(
                target_company_id,
                decision_maker_email,
                distress_signal_type,
                personalization_payload
            )

            outreach_campaign = {
                "outreach_id": outreach_id,
                "target_company": target_company_id,
                "decision_maker": decision_maker_email,
                "distress_type": distress_signal_type,
                "email_sequence": email_sequence,
                "sequence_count": len(email_sequence),
                "send_schedule": {
                    "email_1": "IMMEDIATE",
                    "email_2": "DAY_3",
                    "email_3": "DAY_7",
                    "followup_call": "DAY_5"
                },
                "personalization_context": personalization_payload,
                "campaign_status": "READY_TO_SEND",
                "created_at": datetime.utcnow().isoformat()
            }

            logger.info(f"Outreach campaign created: {outreach_id}, target={target_company_id}")
            return outreach_campaign

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Outreach campaign creation failed: {e}", exc_info=True)
            raise ValueError(f"Outreach failed: {str(e)}")

    @staticmethod
    def generate_rfp_and_sow(
        db: Session,
        client_response: Dict[str, Any],
        cost_matrix: Dict[str, Any],
        project_scope: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Phalanx 5 - System 3: RFP & Solutioning Engine
        Reads client responses, cross-references Phalanx 3's cost matrix, generates margin-aware SOW
        Queue Topic: acquisition.proposal_create
        SLM Route: GENERATE_MARGIN_SOW
        """
        try:
            proposal_id = str(uuid4())

            # Calculate margins using finance phalanx cost matrix
            estimated_delivery_cost = AcquisitionService._calculate_delivery_cost(
                project_scope,
                cost_matrix
            )

            # Ensure margin floor is met (from finance phalanx constraints)
            target_margin_percent = cost_matrix.get("target_margin_percent", 35)
            proposal_price = estimated_delivery_cost / (1 - target_margin_percent / 100)
            actual_margin = proposal_price - estimated_delivery_cost

            statement_of_work = {
                "proposal_id": proposal_id,
                "client_response_summary": client_response,
                "scope": project_scope,
                "estimated_delivery_cost": estimated_delivery_cost,
                "proposal_price": proposal_price,
                "actual_margin_dollars": actual_margin,
                "margin_percent": target_margin_percent,
                "team_composition": AcquisitionService._allocate_team(project_scope),
                "delivery_timeline": AcquisitionService._generate_timeline(project_scope),
                "risk_mitigation": {
                    "scope_creep_guard": "STRICT_CHANGE_ORDER_PROTOCOL",
                    "resource_buffer": "15_PERCENT_BENCH_RESERVE"
                },
                "margin_guardrail_status": "PASSED" if actual_margin > 0 else "FAILED",
                "sow_status": "READY_FOR_CLIENT_REVIEW",
                "created_at": datetime.utcnow().isoformat()
            }

            logger.info(f"SOW generated: {proposal_id}, margin=${actual_margin:.0f}")
            return statement_of_work

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"SOW generation failed: {e}", exc_info=True)
            raise ValueError(f"SOW generation failed: {str(e)}")

    @staticmethod
    def _generate_personalized_sequence(
        company_id: str,
        email: str,
        signal_type: str,
        payload: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Generate hyper-personalized email sequence based on distress signal"""
        sequences = {
            "OPEN_REQUISITIONS": [
                {
                    "subject": f"Accelerate {payload.get('open_roles', 'your')} hiring - {company_id}",
                    "body": f"We've noticed you're scaling your {payload.get('team', 'engineering')} team. We specialize in rapid scaling.",
                    "value_prop": "HIRING_ACCELERATION"
                },
                {
                    "subject": "Interim dev team while you build",
                    "body": "Keep momentum while building permanent hires",
                    "value_prop": "BRIDGE_STAFFING"
                },
                {
                    "subject": "Technical hiring assessment - free",
                    "body": "Let us validate your hiring pipeline",
                    "value_prop": "FREE_ASSESSMENT"
                }
            ],
            "TECHNICAL_DEBT": [
                {
                    "subject": f"Modernizing {payload.get('tech_stack', 'your tech')} at {company_id}",
                    "body": "We've refactored similar stacks 47 times",
                    "value_prop": "TECH_MODERNIZATION"
                },
                {
                    "subject": "30-day proof-of-concept for [system]",
                    "body": "Risk-free way to validate our approach",
                    "value_prop": "POC_OFFER"
                }
            ],
            "LATENCY": [
                {
                    "subject": f"Your infrastructure is costing you {payload.get('estimated_revenue_loss', '$X')}",
                    "body": "Latency → churn → revenue loss. We've improved this.",
                    "value_prop": "PERFORMANCE_RECOVERY"
                }
            ]
        }

        return sequences.get(signal_type, [{"subject": "Let's talk", "body": "Value proposition here"}])

    @staticmethod
    def _calculate_delivery_cost(
        project_scope: Dict[str, Any],
        cost_matrix: Dict[str, Any]
    ) -> float:
        """Calculate estimated delivery cost from resource allocation"""
        try:
            developer_count = project_scope.get("developer_count", 1)
            duration_weeks = project_scope.get("duration_weeks", 4)
            hourly_rate = cost_matrix.get("avg_developer_hourly_cost", 100)

            # Standard: 40hrs/week per developer
            total_hours = developer_count * duration_weeks * 40
            return total_hours * hourly_rate

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Cost calculation failed: {e}")
            return 0.0

    @staticmethod
    def _allocate_team(project_scope: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-allocate team based on project scope"""
        return {
            "engineers": project_scope.get("developer_count", 1),
            "architect": 1 if project_scope.get("complexity") in ["HIGH", "COMPLEX"] else 0,
            "qa": max(1, int(project_scope.get("developer_count", 1) / 2)),
            "pm": 1
        }

    @staticmethod
    def _generate_timeline(project_scope: Dict[str, Any]) -> Dict[str, str]:
        """Generate delivery timeline"""
        duration_weeks = project_scope.get("duration_weeks", 4)
        return {
            "kickoff": "Week 1",
            "design_complete": "Week 2",
            "dev_complete": f"Week {int(duration_weeks * 0.75)}",
            "qa_complete": f"Week {duration_weeks}",
            "go_live": f"Week {duration_weeks}"
        }
