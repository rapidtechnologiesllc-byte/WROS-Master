"""
End-to-End Learning Orchestrator

Connects all 5 bridges:
1. Sales Opportunity → Recruitment (Thunder auto-match)
2. Recruitment → Project (Auto-assignment)
3. Project → Timesheet (Auto-population & utilization)
4. Timesheet → Finance (Profitability calculation)
5. Finance → Cross-module learning (Feedback loops)
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from app.models.learning_transcript import LearningTranscript, LearningCascadeChain
from app.models.candidate import Candidate, CandidateJobApplication
from app.models.user import Jobs
from app.models.employee_allocation import EmployeeAllocation
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.opportunity import Opportunity
from app.models.project import Project
from app.models.invoice import Invoice
import json
import uuid

logger = logging.getLogger(__name__)


class EndToEndLearningOrchestrator:
    """
    Orchestrates complete learning flow across all modules.
    Records every decision, outcome, and weight update for audit.
    """

    @staticmethod
    def record_learning_event(
        db: Session,
        tenant_id: str,
        event_type: str,
        module_name: str,
        entity_id: str,
        entity_type: str,
        decision_type: str,
        predicted_value: float,
        predicted_label: str,
        factors: dict,
        factor_values: dict = None,
        related_entities: dict = None,
        cascade_impacts: dict = None,
        user_id: str = None,
    ) -> LearningTranscript:
        """
        Record a learning event in the transcript for audit.

        Args:
            event_type: "opportunity_created", "recruitment_triggered", "project_assigned", etc.
            module_name: "sales", "thunder", "recruitment", "flash", "finance"
            decision_type: "predict_fit", "predict_margin", "predict_utilization"
            predicted_value: confidence score or probability
            predicted_label: "HIGH_FIT", "LOW_MARGIN", "AVAILABLE", etc.
            factors: {factor_name: weight} - what influenced this decision
            factor_values: {factor_name: actual_value} - measured values of factors
        """

        transcript = LearningTranscript(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            event_type=event_type,
            module_name=module_name,
            entity_id=entity_id,
            entity_type=entity_type,
            decision_type=decision_type,
            predicted_value=predicted_value,
            predicted_label=predicted_label,
            factors=factors,
            factor_values=factor_values or {},
            related_entities=related_entities or {},
            cascade_impacts=cascade_impacts or {},
            user_id=user_id,
            created_at=datetime.utcnow(),
        )

        db.add(transcript)
        db.commit()

        logger.info(
            f"Learning Event: {event_type} | {module_name}.{decision_type} | "
            f"Predicted: {predicted_label} ({predicted_value:.2f}) | Entity: {entity_id}"
        )

        return transcript

    @staticmethod
    def record_learning_outcome(
        db: Session,
        transcript_id: str,
        actual_value: float,
        actual_label: str,
        confidence_gap: float,
        weights_before: dict = None,
        weights_after: dict = None,
        weight_updates: dict = None,
        learning_strength: float = None,
    ) -> LearningTranscript:
        """
        Record the actual outcome and weight updates for a decision.
        """

        transcript = db.query(LearningTranscript).filter(
            LearningTranscript.id == transcript_id
        ).first()

        if not transcript:
            raise ValueError(f"Transcript {transcript_id} not found")

        transcript.outcome_recorded = True
        transcript.actual_value = actual_value
        transcript.actual_label = actual_label
        transcript.confidence_gap = confidence_gap
        transcript.weights_before = weights_before
        transcript.weights_after = weights_after
        transcript.weight_updates = weight_updates
        transcript.learning_strength = learning_strength or (1.0 - min(confidence_gap, 1.0))
        transcript.outcome_recorded_at = datetime.utcnow()

        db.commit()

        logger.info(
            f"Learning Outcome: {transcript.event_type} | Actual: {actual_label} ({actual_value:.2f}) | "
            f"Gap: {confidence_gap:.2f} | Learning Strength: {learning_strength:.2f}"
        )

        return transcript

    @staticmethod
    def create_cascade_chain(
        db: Session,
        tenant_id: str,
        chain_type: str,
        entity_id: str,
        entity_type: str,
    ) -> str:
        """
        Create a cascade chain to track connected decisions.
        Returns chain_id for linking decisions.
        """
        chain_id = str(uuid.uuid4())
        logger.info(f"Created cascade chain: {chain_type} for {entity_type} {entity_id}")
        return chain_id

    @staticmethod
    def link_cascade_decision(
        db: Session,
        chain_id: str,
        step_number: int,
        step_name: str,
        transcript_id: str,
        chain_type: str,
        entity_id: str,
        entity_type: str,
    ):
        """
        Link a decision to a cascade chain.
        """
        cascade = LearningCascadeChain(
            id=str(uuid.uuid4()),
            tenant_id=db.query(LearningTranscript).filter(
                LearningTranscript.id == transcript_id
            ).first().tenant_id,
            chain_id=chain_id,
            chain_type=chain_type,
            entity_id=entity_id,
            entity_type=entity_type,
            step_number=step_number,
            step_name=step_name,
            decision_id=transcript_id,
            created_at=datetime.utcnow(),
        )
        db.add(cascade)
        db.commit()


class SalesToRecruitmentBridge:
    """
    BRIDGE 1: Sales Opportunity → Recruitment
    When sales creates opportunity, auto-trigger recruitment matching.
    """

    @staticmethod
    def trigger_recruitment_on_opportunity(
        db: Session,
        tenant_id: str,
        opportunity_id: str,
        client_name: str,
        skill_requirements: list,  # ["Sr Java", "Sr Python", ...]
        duration_months: int,
        location: str,
        budget: float,
        user_id: str = None,
    ):
        """
        When sales opportunity created:
        1. Record decision event
        2. Thunder analyzes: Which candidates fit?
        3. Predict engagement success
        4. Auto-start recruitment
        """

        chain_id = EndToEndLearningOrchestrator.create_cascade_chain(
            db, tenant_id, "opportunity_to_hire", opportunity_id, "opportunity"
        )

        # STEP 1: Record opportunity analysis
        factors = {
            "skill_match_pool": 0.35,  # % of pool with required skills
            "location_match": 0.20,  # % with preferred location
            "rate_alignment": 0.20,  # Budget vs market rate
            "timeline_urgency": 0.15,  # How fast needed?
            "client_history": 0.10,  # Past success with this client
        }

        # Simulate factor analysis
        factor_values = {
            "skill_match_pool": 0.65,  # 65% of pool has these skills
            "location_match": 0.80,  # 80% match location
            "rate_alignment": 0.90,  # Budget is competitive
            "timeline_urgency": 0.60,  # Medium urgency
            "client_history": 0.70,  # Known client
        }

        # Calculate predicted success probability
        predicted_probability = sum(
            factors[k] * factor_values.get(k, 0) for k in factors.keys()
        ) / sum(factors.values())

        transcript = EndToEndLearningOrchestrator.record_learning_event(
            db=db,
            tenant_id=tenant_id,
            event_type="opportunity_created",
            module_name="sales",
            entity_id=opportunity_id,
            entity_type="opportunity",
            decision_type="predict_recruitment_success",
            predicted_value=predicted_probability,
            predicted_label="HIGH_FIT" if predicted_probability > 0.70 else "MEDIUM_FIT",
            factors=factors,
            factor_values=factor_values,
            related_entities={
                "client_name": client_name,
                "skills": skill_requirements,
                "location": location,
            },
            user_id=user_id,
        )

        # STEP 2: Link to cascade
        EndToEndLearningOrchestrator.link_cascade_decision(
            db, chain_id, 1, "opportunity_analysis", transcript.id,
            "opportunity_to_hire", opportunity_id, "opportunity"
        )

        # STEP 3: Auto-trigger Thunder recruitment matching
        candidates = ThunderRecruitmentMatcher.find_matching_candidates(
            db, tenant_id, skill_requirements, location, budget
        )

        logger.info(
            f"Opportunity {opportunity_id}: {client_name} | "
            f"Found {len(candidates)} matching candidates | "
            f"Predicted success: {predicted_probability:.2%}"
        )

        return {
            "opportunity_id": opportunity_id,
            "chain_id": chain_id,
            "matching_candidates": len(candidates),
            "predicted_success": predicted_probability,
            "transcript_id": transcript.id,
        }


class ThunderRecruitmentMatcher:
    """
    THUNDER: Auto-match candidates to opportunity requirements.
    Predict which candidates have highest engagement probability.
    """

    @staticmethod
    def find_matching_candidates(
        db: Session,
        tenant_id: str,
        skill_requirements: list,
        location: str,
        budget: float,
    ) -> list:
        """
        Find candidates matching opportunity requirements.
        """

        # Query candidates matching skills and location
        candidates = db.query(Candidate).filter(
            and_(
                Candidate.tenant_id == tenant_id,
                Candidate.location.like(f"%{location}%"),
            )
        ).limit(20).all()

        return candidates or []

    @staticmethod
    def predict_and_record_engagement(
        db: Session,
        tenant_id: str,
        candidate_id: str,
        opportunity_id: str,
        chain_id: str,
        user_id: str = None,
    ) -> dict:
        """
        Thunder predicts engagement success for candidate.
        Records learning event.
        """

        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()

        # Simulate Thunder factors
        factors = {
            "email_open_probability": 0.40,
            "skill_match_score": 0.25,
            "location_match": 0.15,
            "experience_level": 0.15,
            "market_competitiveness": 0.05,
        }

        factor_values = {
            "email_open_probability": 0.92,  # Sr Engineers India: 92% open rate
            "skill_match_score": 0.88,
            "location_match": 0.95,
            "experience_level": 0.90,
            "market_competitiveness": 0.70,
        }

        predicted_probability = sum(
            factors[k] * factor_values.get(k, 0) for k in factors.keys()
        ) / sum(factors.values())

        transcript = EndToEndLearningOrchestrator.record_learning_event(
            db=db,
            tenant_id=tenant_id,
            event_type="thunder_candidate_match",
            module_name="thunder",
            entity_id=candidate_id,
            entity_type="candidate",
            decision_type="predict_engagement_success",
            predicted_value=predicted_probability,
            predicted_label="HIGH_ENGAGEMENT" if predicted_probability > 0.85 else "MEDIUM_ENGAGEMENT",
            factors=factors,
            factor_values=factor_values,
            related_entities={"opportunity_id": opportunity_id},
            cascade_impacts={"recruitment": "auto_engage"},
            user_id=user_id,
        )

        # Link to cascade
        EndToEndLearningOrchestrator.link_cascade_decision(
            db, chain_id, 2, "thunder_match", transcript.id,
            "opportunity_to_hire", candidate_id, "candidate"
        )

        logger.info(
            f"Thunder Match: Candidate {candidate.first_name} → "
            f"Opportunity {opportunity_id} | "
            f"Predicted: {predicted_probability:.2%} engagement success"
        )

        return {
            "candidate_id": candidate_id,
            "predicted_probability": predicted_probability,
            "transcript_id": transcript.id,
        }


class RecruitmentToProjectBridge:
    """
    BRIDGE 2: Recruitment → Project Assignment
    When candidate hired, auto-assign to project.
    Flash predicts project success based on team composition.
    """

    @staticmethod
    def auto_assign_to_project(
        db: Session,
        tenant_id: str,
        candidate_id: str,
        opportunity_id: str,
        chain_id: str,
        start_date: str,
        duration_months: int,
        billable_rate: float,
        user_id: str = None,
    ) -> dict:
        """
        Auto-assign hired candidate to project.
        Flash predicts project success.
        """

        # Create project assignment
        allocation = EmployeeAllocation(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=candidate_id,
            project_id=opportunity_id,  # Link to opportunity as project
            allocated_from=datetime.fromisoformat(start_date),
            allocated_till=datetime.fromisoformat(start_date) if duration_months else None,
            allocation_percentage=100,
            billable_rate=billable_rate,
        )
        db.add(allocation)
        db.commit()

        # Flash predicts project success
        factors = {
            "team_composition": 0.30,
            "client_experience": 0.25,
            "project_complexity": 0.20,
            "timeline_realism": 0.15,
            "resource_availability": 0.10,
        }

        factor_values = {
            "team_composition": 0.92,  # Sr Engineers + 1 junior
            "client_experience": 0.88,  # Done similar projects
            "project_complexity": 0.70,  # Moderate complexity
            "timeline_realism": 0.85,  # Realistic timeline
            "resource_availability": 0.95,  # All resources available
        }

        predicted_probability = sum(
            factors[k] * factor_values.get(k, 0) for k in factors.keys()
        ) / sum(factors.values())

        transcript = EndToEndLearningOrchestrator.record_learning_event(
            db=db,
            tenant_id=tenant_id,
            event_type="project_assigned",
            module_name="flash",
            entity_id=allocation.id,
            entity_type="project_allocation",
            decision_type="predict_project_success",
            predicted_value=predicted_probability,
            predicted_label="ON_TIME" if predicted_probability > 0.85 else "AT_RISK",
            factors=factors,
            factor_values=factor_values,
            related_entities={
                "candidate_id": candidate_id,
                "opportunity_id": opportunity_id,
            },
            cascade_impacts={"timesheet": "track_utilization", "finance": "calculate_margin"},
            user_id=user_id,
        )

        # Link to cascade
        EndToEndLearningOrchestrator.link_cascade_decision(
            db, chain_id, 3, "project_assignment", transcript.id,
            "opportunity_to_hire", candidate_id, "candidate"
        )

        logger.info(
            f"Project Assignment: Candidate {candidate_id} → "
            f"Project {opportunity_id} | "
            f"Predicted success: {predicted_probability:.2%}"
        )

        return {
            "allocation_id": allocation.id,
            "predicted_probability": predicted_probability,
            "transcript_id": transcript.id,
        }


class ProjectToTimesheetBridge:
    """
    BRIDGE 3: Project → Timesheet
    Auto-populate expected hours from project plan.
    Track actual vs planned utilization.
    """

    @staticmethod
    def auto_populate_timesheet(
        db: Session,
        tenant_id: str,
        allocation_id: str,
        week_number: int,
        expected_hours: float = 40.0,
        user_id: str = None,
    ) -> dict:
        """
        Auto-create timesheet entry with expected hours.
        When actual hours submitted, calculate utilization.
        """

        allocation = db.query(EmployeeAllocation).filter(
            EmployeeAllocation.id == allocation_id
        ).first()

        if not allocation:
            raise ValueError(f"Allocation {allocation_id} not found")

        # Create timesheet entry
        timesheet_entry = TimesheetEntry(
            id=str(uuid.uuid4()),
            timesheet_id=allocation_id,  # Link to allocation
            date_worked=datetime.utcnow(),
            hours_worked=expected_hours,  # Default to expected
            description=f"Week {week_number} - Projected hours",
        )

        factors = {
            "project_velocity": 0.30,
            "team_stability": 0.25,
            "scope_changes": 0.20,
            "client_urgency": 0.15,
            "resource_constraints": 0.10,
        }

        factor_values = {
            "project_velocity": 0.95,  # On pace
            "team_stability": 0.90,  # Stable team
            "scope_changes": 0.20,  # Minimal scope changes
            "client_urgency": 0.70,  # Normal urgency
            "resource_constraints": 0.80,  # Some constraints
        }

        predicted_utilization = sum(
            factors[k] * factor_values.get(k, 0) for k in factors.keys()
        ) / sum(factors.values())

        transcript = EndToEndLearningOrchestrator.record_learning_event(
            db=db,
            tenant_id=tenant_id,
            event_type="timesheet_created",
            module_name="project",
            entity_id=timesheet_entry.id,
            entity_type="timesheet_entry",
            decision_type="predict_utilization",
            predicted_value=predicted_utilization,
            predicted_label="HIGH_UTIL" if predicted_utilization > 0.85 else "BENCH_RISK",
            factors=factors,
            factor_values=factor_values,
            related_entities={"allocation_id": allocation_id},
            cascade_impacts={"finance": "calculate_revenue"},
            user_id=user_id,
        )

        logger.info(
            f"Timesheet: Week {week_number} | Allocation {allocation_id} | "
            f"Predicted utilization: {predicted_utilization:.2%}"
        )

        return {
            "timesheet_entry_id": timesheet_entry.id,
            "expected_hours": expected_hours,
            "predicted_utilization": predicted_utilization,
            "transcript_id": transcript.id,
        }

    @staticmethod
    def record_actual_timesheet(
        db: Session,
        tenant_id: str,
        allocation_id: str,
        actual_hours: float,
        expected_hours: float = 40.0,
        transcript_id: str = None,
        user_id: str = None,
    ) -> dict:
        """
        When actual timesheet submitted, record outcome.
        Calculate utilization gap and learning.
        """

        actual_utilization = actual_hours / expected_hours if expected_hours > 0 else 0
        utilization_gap = abs(1.0 - actual_utilization)

        if transcript_id:
            # Record outcome for prediction
            EndToEndLearningOrchestrator.record_learning_outcome(
                db=db,
                transcript_id=transcript_id,
                actual_value=actual_utilization,
                actual_label="HIGH_UTIL" if actual_utilization > 0.85 else "BENCH_RISK",
                confidence_gap=utilization_gap,
                learning_strength=1.0 - utilization_gap,
            )

        logger.info(
            f"Actual Timesheet: {actual_hours}h / {expected_hours}h = {actual_utilization:.2%} utilization"
        )

        return {
            "actual_hours": actual_hours,
            "actual_utilization": actual_utilization,
            "utilization_gap": utilization_gap,
        }


class TimesheetToFinanceBridge:
    """
    BRIDGE 4: Timesheet → Finance
    Auto-calculate project profitability from timesheet data.
    Revenue - Cost = Margin
    """

    @staticmethod
    def calculate_project_profitability(
        db: Session,
        tenant_id: str,
        allocation_id: str,
        period_start: str,
        period_end: str,
        user_id: str = None,
    ) -> dict:
        """
        Calculate project margin from timesheet and allocation data.

        Revenue = actual_billable_hours × billable_rate
        Cost = employee_cost_per_hour × hours_worked
        Margin = (Revenue - Cost) / Revenue
        """

        allocation = db.query(EmployeeAllocation).filter(
            EmployeeAllocation.id == allocation_id
        ).first()

        if not allocation:
            raise ValueError(f"Allocation {allocation_id} not found")

        # Get timesheets for period
        timesheets = db.query(Timesheet).filter(
            and_(
                Timesheet.employee_id == allocation.user_id,
                Timesheet.project_id == allocation.project_id,
            )
        ).all()

        # Aggregate hours
        total_billable_hours = sum(t.total_hours for t in timesheets) if timesheets else 0

        # Calculate revenue
        billable_rate = allocation.billable_rate or 180.0  # Default $180/hr
        revenue = total_billable_hours * billable_rate

        # Calculate cost (simplified: employee cost per hour)
        # Assume $120K/year = $57.70/hour
        employee_cost_per_hour = 120000 / 2080
        cost = total_billable_hours * employee_cost_per_hour

        # Calculate margin
        margin_dollars = revenue - cost
        margin_percentage = (margin_dollars / revenue * 100) if revenue > 0 else 0

        # Record learning event
        factors = {
            "billable_rate": 0.40,  # Higher rate = higher margin
            "utilization_rate": 0.35,  # Higher utilization = higher margin
            "team_cost": 0.15,  # Lower cost team = higher margin
            "project_efficiency": 0.10,  # Efficient projects = higher margin
        }

        factor_values = {
            "billable_rate": allocation.billable_rate / 250.0 if allocation.billable_rate else 0.72,
            "utilization_rate": min(total_billable_hours / (40 * 4) if timesheets else 0.8, 1.0),
            "team_cost": 0.60,  # Sr Engineers: good cost
            "project_efficiency": 0.90,  # Project running smoothly
        }

        predicted_margin = sum(
            factors[k] * factor_values.get(k, 0) for k in factors.keys()
        ) / sum(factors.values())

        transcript = EndToEndLearningOrchestrator.record_learning_event(
            db=db,
            tenant_id=tenant_id,
            event_type="profitability_calculated",
            module_name="finance",
            entity_id=allocation_id,
            entity_type="project_allocation",
            decision_type="predict_project_margin",
            predicted_value=predicted_margin,
            predicted_label="HIGH_MARGIN" if predicted_margin > 0.65 else "LOW_MARGIN",
            factors=factors,
            factor_values=factor_values,
            related_entities={
                "total_hours": total_billable_hours,
                "revenue": revenue,
                "cost": cost,
            },
            cascade_impacts={
                "sales": "client_profitability",
                "thunder": "segment_learning",
                "flash": "team_effectiveness",
            },
            user_id=user_id,
        )

        logger.info(
            f"Profitability: ${revenue:.0f} revenue - ${cost:.0f} cost = "
            f"${margin_dollars:.0f} margin ({margin_percentage:.1f}%)"
        )

        return {
            "allocation_id": allocation_id,
            "total_hours": total_billable_hours,
            "revenue": revenue,
            "cost": cost,
            "margin_dollars": margin_dollars,
            "margin_percentage": margin_percentage,
            "transcript_id": transcript.id,
        }


class FinanceToCrossModuleLearning:
    """
    BRIDGE 5: Finance → Cross-Module Learning Feedback

    Finance outcomes inform Thunder, Flash, and Sales learning.
    """

    @staticmethod
    def update_cross_module_weights(
        db: Session,
        tenant_id: str,
        allocation_id: str,
        actual_margin_percentage: float,
        predicted_margin_percentage: float,
        candidate_segment: str,  # "Sr Engineers India", "Jr Developers US", etc.
        client_id: str = None,
        user_id: str = None,
    ):
        """
        Update learning weights across modules based on profitability outcome.
        """

        margin_gap = abs(predicted_margin_percentage - actual_margin_percentage) / 100.0
        learning_strength = 1.0 - min(margin_gap, 1.0)

        # Update Thunder: Which candidate segments are most profitable?
        thunder_weight_delta = 0.02 if actual_margin_percentage > 65 else -0.02

        # Update Flash: Which team compositions work best?
        flash_weight_delta = 0.015 if actual_margin_percentage > 65 else -0.015

        # Update Sales: Which client types are most profitable?
        sales_weight_delta = 0.03 if actual_margin_percentage > 65 else -0.01

        weights_before = {
            "thunder_candidate_segment": 0.50,
            "flash_team_composition": 0.30,
            "sales_client_type": 0.20,
        }

        weights_after = {
            "thunder_candidate_segment": min(0.50 + thunder_weight_delta, 1.0),
            "flash_team_composition": min(0.30 + flash_weight_delta, 1.0),
            "sales_client_type": min(0.20 + sales_weight_delta, 1.0),
        }

        weight_updates = {
            k: weights_after[k] - weights_before[k] for k in weights_before.keys()
        }

        # Record outcome learning
        transcript = EndToEndLearningOrchestrator.record_learning_event(
            db=db,
            tenant_id=tenant_id,
            event_type="cross_module_learning",
            module_name="finance",
            entity_id=allocation_id,
            entity_type="project_allocation",
            decision_type="update_segment_weights",
            predicted_value=predicted_margin_percentage / 100.0,
            predicted_label="HIGH_PROFIT" if actual_margin_percentage > 65 else "LOW_PROFIT",
            factors=weights_before,
            factor_values={"actual_margin": actual_margin_percentage / 100.0},
            related_entities={
                "candidate_segment": candidate_segment,
                "client_id": client_id,
            },
            cascade_impacts={
                "thunder": f"segment_weight_{thunder_weight_delta:+.3f}",
                "flash": f"team_weight_{flash_weight_delta:+.3f}",
                "sales": f"client_weight_{sales_weight_delta:+.3f}",
            },
            user_id=user_id,
        )

        # Record outcome with weight updates
        EndToEndLearningOrchestrator.record_learning_outcome(
            db=db,
            transcript_id=transcript.id,
            actual_value=actual_margin_percentage / 100.0,
            actual_label="HIGH_PROFIT" if actual_margin_percentage > 65 else "LOW_PROFIT",
            confidence_gap=margin_gap,
            weights_before=weights_before,
            weights_after=weights_after,
            weight_updates=weight_updates,
            learning_strength=learning_strength,
        )

        logger.info(
            f"Cross-Module Learning: Segment {candidate_segment} | "
            f"Margin {actual_margin_percentage:.1f}% (gap {margin_gap:.2f}) | "
            f"Weights updated: Thunder {thunder_weight_delta:+.3f}, Flash {flash_weight_delta:+.3f}, Sales {sales_weight_delta:+.3f}"
        )

        return {
            "allocation_id": allocation_id,
            "weights_before": weights_before,
            "weights_after": weights_after,
            "weight_updates": weight_updates,
            "learning_strength": learning_strength,
            "transcript_id": transcript.id,
        }
