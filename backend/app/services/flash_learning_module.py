"""Flash Autonomous Learning Module - Job Matching & Interview Intelligence

Flash learns optimal job-candidate matching through analyzing:
1. Match quality (which profiles convert to interviews)
2. Interview scheduling patterns (optimal timing)
3. Offer generation strategy (what terms candidates accept)
4. Success profiles (which candidates become great hires)

Every job-candidate interaction updates the learning model. After 50+ operations,
Flash becomes significantly smarter about predicting interview success and offer acceptance rates.
"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.services.slm_learning_framework import SLMlearningFramework

logger = logging.getLogger(__name__)


class FlashLearningModule:
    """Autonomous learning system for Flash job orchestration"""

    # Job matching quality baseline
    DEFAULT_MATCH_QUALITY = 0.60  # 60% before learning

    # Interview scheduling baseline
    DEFAULT_INTERVIEW_SCHEDULING_SUCCESS = 0.70  # 70% can be scheduled
    DEFAULT_SHOW_UP_RATE = 0.85  # 85% show up to interviews

    # Offer acceptance baseline
    DEFAULT_OFFER_ACCEPTANCE_RATE = 0.75  # 75% accept offers

    @staticmethod
    def record_job_candidate_match(
        db: Session,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
        match_quality_score: float,  # 0-100%
        skills_match: float,  # 0-100%
        experience_match: float,  # 0-100%
        candidate_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record job-candidate match result.
        Called when Flash evaluates a candidate for a job.

        Args:
            db: Database session
            tenant_id: Tenant ID
            job_id: Job ID
            candidate_id: Candidate ID (for tracking)
            match_quality_score: Overall match quality (0-100%)
            skills_match: Skills alignment (0-100%)
            experience_match: Experience alignment (0-100%)
            candidate_profile: Candidate details for learning
        """
        try:
            # Record metric
            metric_result = SLMlearningFramework.collect_flash_metrics(
                db=db,
                tenant_id=tenant_id,
                job_id=job_id,
                metric_type="match_quality",
                value=match_quality_score,
                details={
                    "skills_match": skills_match,
                    "experience_match": experience_match,
                    "candidate_profile": candidate_profile.get("title", "") if candidate_profile else "",
                    "salary_range": candidate_profile.get("salary_expectation", "") if candidate_profile else "",
                },
            )

            logger.info(
                f"[Flash Learning] Recorded match: job={job_id}, candidate={candidate_id}, "
                f"quality={match_quality_score:.1f}%, skills={skills_match:.1f}%, exp={experience_match:.1f}%"
            )

            return {
                "status": "match_recorded",
                "match_quality": match_quality_score,
                "metric_id": metric_result.get("metric_id"),
            }

        except Exception as e:
            logger.error(f"Failed to record job-candidate match: {e}", exc_info=True)
            raise

    @staticmethod
    def record_interview_scheduled(
        db: Session,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
        interview_date: datetime,
        round_number: int = 1,
    ) -> Dict[str, Any]:
        """
        Record successful interview scheduling.
        Called when interview is scheduled with candidate.
        """
        try:
            logger.info(
                f"[Flash Learning] Interview scheduled: job={job_id}, "
                f"candidate={candidate_id}, round={round_number}"
            )

            # Just tracking for now - full metric recording happens after interview completion
            return {
                "status": "interview_scheduled",
                "job_id": str(job_id),
                "candidate_id": str(candidate_id),
                "interview_date": interview_date.isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to record interview scheduling: {e}", exc_info=True)
            raise

    @staticmethod
    def record_interview_result(
        db: Session,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
        success: bool,  # Did candidate complete interview?
        attended: bool = True,  # Did they show up?
        feedback_score: Optional[float] = None,  # Interviewer rating (0-100)
    ) -> Dict[str, Any]:
        """
        Record interview completion result.
        Called after interview is completed.

        Args:
            db: Database session
            tenant_id: Tenant ID
            job_id: Job ID
            success: Did interview happen successfully?
            attended: Did candidate attend?
            feedback_score: Interviewer feedback (0-100)
        """
        try:
            # Record interview conversion metric
            if success:
                conversion_value = 100.0 if feedback_score is None else feedback_score
            else:
                conversion_value = 0.0 if not attended else 50.0

            metric_result = SLMlearningFramework.collect_flash_metrics(
                db=db,
                tenant_id=tenant_id,
                job_id=job_id,
                metric_type="interview_conversion",
                value=conversion_value,
                details={"attended": attended, "feedback": feedback_score},
            )

            # Update show-up rate
            if success and attended:
                show_up_metric = SLMlearningFramework.collect_flash_metrics(
                    db=db,
                    tenant_id=tenant_id,
                    job_id=job_id,
                    metric_type="show_up_rate",
                    value=100.0,
                )

            logger.info(
                f"[Flash Learning] Interview result: job={job_id}, "
                f"success={success}, attended={attended}, feedback={feedback_score}"
            )

            return {
                "status": "interview_recorded",
                "success": success,
                "attended": attended,
                "metric_id": metric_result.get("metric_id"),
            }

        except Exception as e:
            logger.error(f"Failed to record interview result: {e}", exc_info=True)
            raise

    @staticmethod
    def record_offer_result(
        db: Session,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
        offer_extended: bool,
        offer_accepted: bool = None,
        salary_offered: Optional[float] = None,
        salary_expected: Optional[float] = None,
        negotiation_rounds: int = 0,
    ) -> Dict[str, Any]:
        """
        Record offer result (generated, accepted, negotiated, rejected).
        Called when offer is generated and then after candidate response.

        Args:
            db: Database session
            tenant_id: Tenant ID
            job_id: Job ID
            offer_extended: Was offer extended?
            offer_accepted: Was offer accepted? (None if still pending)
            salary_offered: Offered salary
            salary_expected: Candidate expected salary
            negotiation_rounds: Number of negotiation iterations
        """
        try:
            # Record offer acceptance metric
            if offer_extended and offer_accepted is not None:
                acceptance_value = 100.0 if offer_accepted else 0.0

                metric_result = SLMlearningFramework.collect_flash_metrics(
                    db=db,
                    tenant_id=tenant_id,
                    job_id=job_id,
                    metric_type="offer_acceptance",
                    value=acceptance_value,
                    details={
                        "salary_offered": salary_offered,
                        "salary_expected": salary_expected,
                        "negotiation_rounds": negotiation_rounds,
                    },
                )

                logger.info(
                    f"[Flash Learning] Offer result: job={job_id}, "
                    f"extended={offer_extended}, accepted={offer_accepted}, "
                    f"offered={salary_offered}, expected={salary_expected}, negotiations={negotiation_rounds}"
                )

                return {
                    "status": "offer_recorded",
                    "accepted": offer_accepted,
                    "negotiation_rounds": negotiation_rounds,
                    "metric_id": metric_result.get("metric_id"),
                }

            return {"status": "offer_pending"}

        except Exception as e:
            logger.error(f"Failed to record offer result: {e}", exc_info=True)
            raise

    @staticmethod
    def get_job_matching_strategy(
        db: Session,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Get Flash's job matching strategy based on learning.
        Returns candidate profile characteristics that match well for this job.
        """
        try:
            # Get Flash recommendations
            recommendations = SLMlearningFramework.get_flash_recommendations(
                db=db,
                tenant_id=tenant_id,
                job_id=job_id,
            )

            return {
                "job_id": str(job_id),
                "strategy": {
                    "top_candidate_profile": recommendations.get("top_candidate_profile"),
                    "match_quality_target": recommendations.get("match_quality", 0.75),
                    "confidence": recommendations.get("confidence", 0.5),
                    "expected_interview_to_offer_rate": recommendations.get(
                        "interview_to_offer_rate", 0.70
                    ),
                    "expected_offer_acceptance_rate": recommendations.get(
                        "offer_acceptance_rate", 0.75
                    ),
                    "optimal_interview_days_from_application": recommendations.get(
                        "optimal_interview_days", 3
                    ),
                    "typical_salary_range": recommendations.get("typical_salary_range"),
                    "offer_strategy": recommendations.get("offer_strategy", "standard"),
                },
                "recommendations": [
                    f"Target candidates matching: {recommendations.get('top_candidate_profile')}",
                    f"Expect {recommendations.get('interview_to_offer_rate', 0.70)*100:.0f}% of interviews → offers",
                    f"Expect {recommendations.get('offer_acceptance_rate', 0.75)*100:.0f}% of offers accepted",
                    f"Schedule interview within {recommendations.get('optimal_interview_days', 3)} days of application",
                    f"Use {recommendations.get('offer_strategy', 'standard')} offer strategy",
                ],
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get job matching strategy: {e}", exc_info=True)
            raise

    @staticmethod
    def get_interview_scheduling_insights(
        db: Session, tenant_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Get insights on optimal interview scheduling based on learning.
        Shows when candidates are most available and most likely to accept.
        """
        try:
            from app.models.slm_learning_metrics import FlashLearningMetrics

            metrics = (
                db.query(FlashLearningMetrics)
                .filter(FlashLearningMetrics.tenant_id == tenant_id)
                .all()
            )

            if not metrics or len(metrics) < 5:
                return {
                    "status": "insufficient_data",
                    "show_up_rate": 0.85,
                    "optimal_days_delay": 3,
                    "confidence": 0.3,
                }

            show_up_rates = [m.candidate_show_up_rate for m in metrics if m.candidate_show_up_rate > 0]
            optimal_days = [
                m.optimal_interview_slot_days
                for m in metrics
                if m.optimal_interview_slot_days is not None
            ]

            avg_show_up = sum(show_up_rates) / len(show_up_rates) if show_up_rates else 0.85
            avg_days = sum(optimal_days) / len(optimal_days) if optimal_days else 3

            return {
                "status": "success",
                "average_show_up_rate": avg_show_up,
                "optimal_days_from_application": round(avg_days),
                "confidence": min(len(metrics) / 50.0, 1.0),
                "recommendation": f"Schedule interviews {round(avg_days)} days after application "
                f"for best show-up rate (~{avg_show_up*100:.0f}%)",
                "metrics_analyzed": len(metrics),
            }

        except Exception as e:
            logger.error(f"Failed to get interview insights: {e}", exc_info=True)
            raise

    @staticmethod
    def get_offer_generation_strategy(
        db: Session, tenant_id: uuid.UUID, job_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Get offer generation strategy based on what works for this job.
        Learns from salary ranges, negotiation patterns, and acceptance rates.
        """
        try:
            from app.models.slm_learning_metrics import FlashLearningMetrics

            metric = (
                db.query(FlashLearningMetrics)
                .filter(
                    and_(
                        FlashLearningMetrics.tenant_id == tenant_id,
                        FlashLearningMetrics.job_id == job_id,
                    )
                )
                .first()
            )

            if not metric:
                return {
                    "status": "insufficient_data",
                    "offer_strategy": "standard",
                    "confidence": 0.3,
                }

            return {
                "status": "success",
                "offer_strategy": metric.offer_strategy or "standard"
                if hasattr(metric, "offer_strategy")
                else "standard",
                "typical_salary_range": metric.typical_offer_salary_range,
                "expected_acceptance_rate": metric.offer_acceptance_rate,
                "average_negotiation_rounds": metric.average_negotiation_rounds,
                "confidence": metric.recommendation_confidence / 100.0,
                "recommendations": [
                    f"Use {metric.offer_strategy or 'standard'} offer strategy",
                    f"Salary range: {metric.typical_offer_salary_range}",
                    f"Expect {metric.offer_acceptance_rate*100:.0f}% acceptance rate",
                    f"Budget for ~{metric.average_negotiation_rounds:.1f} negotiation rounds",
                ],
            }

        except Exception as e:
            logger.error(f"Failed to get offer strategy: {e}", exc_info=True)
            raise
