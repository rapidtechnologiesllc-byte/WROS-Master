"""Cross-Module Intelligence - Real-time learning application across all modules

The moment Thunder learns something, every other module uses it to make better decisions.

Example: Thunder learns "Email works 65% better for senior Python engineers in NYC"
→ Flash immediately uses this: "Weight email-responsive candidates 65% higher for NYC Python roles"
→ Interview immediately uses this: "Candidates from email have 23% better interview pass rate, adjust screening"
→ Offer immediately uses this: "Email-sourced candidates accept 18% faster, offer 24h deadline instead of 72h"
→ Finance immediately uses this: "Email-sourced senior engineers have 35% higher project margins"

This is NOT delayed learning - this is IMMEDIATE decision improvement.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.learning_events import SegmentLearningProfile
from app.services.learning_event_collector import LearningEventCollector

logger = logging.getLogger(__name__)


class CrossModuleIntelligence:
    """Real-time learning sharing between modules."""

    @staticmethod
    def get_thunder_insights_for_flash(
        db: Session,
        tenant_id: str,
        candidate_segment: str,
    ) -> Dict[str, Any]:
        """
        Get Thunder's learned channel effectiveness for Flash to use in job matching.

        Called by Flash when matching candidates to jobs.
        Uses Thunder's learning to weight candidates by their engagement channel.

        Example output:
        {
            "best_channel": "whatsapp",
            "channel_weights": {
                "whatsapp": 1.35,  # 35% weight increase
                "email": 0.92,     # 8% weight decrease
                "sms": 1.15,       # 15% weight increase
            },
            "engagement_rate": 0.72,
            "confidence": 0.78,
        }

        Args:
            db: Database session
            tenant_id: Tenant ID
            candidate_segment: Candidate segment (e.g., "senior_us_python")

        Returns:
            Thunder insights for Flash to apply in job matching
        """
        try:
            # Get Thunder's learned profile for this segment
            profile = LearningEventCollector.get_segment_profile(
                db=db,
                tenant_id=tenant_id,
                module="thunder",
                segment_id=candidate_segment,
            )

            if not profile or not profile.get("learned_patterns"):
                # No learning yet, return neutral weights
                return {
                    "best_channel": "unknown",
                    "channel_weights": {
                        "whatsapp": 1.0,
                        "email": 1.0,
                        "sms": 1.0,
                    },
                    "engagement_rate": 0.50,
                    "confidence": 0.0,
                    "message": "No Thunder learning yet for this segment",
                }

            patterns = profile.get("learned_patterns", {})
            channel_rates = patterns.get("channel_success_rates", {})

            # Find best channel
            best_channel = max(channel_rates, key=channel_rates.get) if channel_rates else "unknown"
            best_rate = channel_rates.get(best_channel, 0.5)

            # Calculate weight adjustments (compared to baseline)
            baseline_rate = 0.50  # Neutral baseline
            channel_weights = {}
            for channel, rate in channel_rates.items():
                if baseline_rate > 0:
                    weight = rate / baseline_rate
                    channel_weights[channel] = round(weight, 2)

            return {
                "best_channel": best_channel,
                "channel_weights": channel_weights,
                "engagement_rate": round(best_rate, 3),
                "confidence": profile.get("confidence", 0.0),
                "recommendation": profile.get("recommendation"),
            }

        except Exception as e:
            logger.error(f"[CrossModule] Failed to get Thunder insights for Flash: {e}", exc_info=True)
            return {
                "best_channel": "unknown",
                "channel_weights": {},
                "engagement_rate": 0.50,
                "confidence": 0.0,
                "error": str(e),
            }

    @staticmethod
    def get_flash_candidate_quality_prediction(
        db: Session,
        tenant_id: str,
        candidate_segment: str,
        job_match_score: float,
    ) -> Dict[str, Any]:
        """
        Get Flash's predicted candidate quality for Interview to use in screening.

        Called by Interview when scheduling candidates.
        Uses Flash's learning to predict interview pass rate based on job match quality.

        Example output:
        {
            "predicted_interview_pass_rate": 0.78,
            "recommended_assessment_difficulty": "HARD",
            "estimated_offer_conversion": 0.72,
            "confidence": 0.85,
        }

        Args:
            db: Database session
            tenant_id: Tenant ID
            candidate_segment: Candidate segment
            job_match_score: Flash's job match score (0.0-1.0)

        Returns:
            Prediction of interview success based on match quality
        """
        try:
            # Get Flash's learned profile for this segment
            profile = LearningEventCollector.get_segment_profile(
                db=db,
                tenant_id=tenant_id,
                module="flash",
                segment_id=candidate_segment,
            )

            if not profile or not profile.get("learned_patterns"):
                # No learning yet - use job match score as proxy
                return {
                    "predicted_interview_pass_rate": job_match_score * 0.85,  # 85% of match score
                    "recommended_assessment_difficulty": "MEDIUM",
                    "estimated_offer_conversion": job_match_score * 0.65,
                    "confidence": 0.0,
                    "message": "No Flash learning yet - using match score as baseline",
                }

            patterns = profile.get("learned_patterns", {})

            # Use Flash's learned relationship between match quality and interview success
            match_to_interview_ratio = patterns.get("match_to_interview_conversion", 0.80)
            interview_to_offer_ratio = patterns.get("interview_to_offer_conversion", 0.65)

            predicted_pass_rate = min(1.0, job_match_score * match_to_interview_ratio)
            predicted_offer_conversion = min(1.0, predicted_pass_rate * interview_to_offer_ratio)

            # Assess difficulty (higher match = harder to recruit, more assessment needed)
            if job_match_score > 0.85:
                difficulty = "HARD"
            elif job_match_score > 0.70:
                difficulty = "MEDIUM"
            else:
                difficulty = "EASY"

            return {
                "predicted_interview_pass_rate": round(predicted_pass_rate, 3),
                "recommended_assessment_difficulty": difficulty,
                "estimated_offer_conversion": round(predicted_offer_conversion, 3),
                "confidence": profile.get("confidence", 0.0),
                "recommendation": patterns.get("recommendation_for_interview"),
            }

        except Exception as e:
            logger.error(f"[CrossModule] Failed to predict Flash candidate quality: {e}", exc_info=True)
            return {
                "predicted_interview_pass_rate": job_match_score * 0.80,
                "recommended_assessment_difficulty": "MEDIUM",
                "estimated_offer_conversion": job_match_score * 0.65,
                "confidence": 0.0,
                "error": str(e),
            }

    @staticmethod
    def get_interview_success_prediction(
        db: Session,
        tenant_id: str,
        candidate_segment: str,
        job_type: str,
    ) -> Dict[str, Any]:
        """
        Get Interview's predicted success for Offer to use in negotiation.

        Called by Offer when generating offer.
        Uses Interview's learning to predict offer acceptance based on interview performance.

        Example output:
        {
            "predicted_offer_acceptance_rate": 0.78,
            "recommended_offer_deadline": 24,  # hours
            "recommended_salary_premium": 1.12,  # 12% above base
            "confidence": 0.82,
        }

        Args:
            db: Database session
            tenant_id: Tenant ID
            candidate_segment: Candidate segment
            job_type: Job type for segment-specific predictions

        Returns:
            Offer strategy based on interview-learned patterns
        """
        try:
            # Get Interview's learned profile
            profile = LearningEventCollector.get_segment_profile(
                db=db,
                tenant_id=tenant_id,
                module="interview",
                segment_id=candidate_segment,
            )

            if not profile or not profile.get("learned_patterns"):
                # No learning yet - use safe defaults
                return {
                    "predicted_offer_acceptance_rate": 0.65,
                    "recommended_offer_deadline": 72,  # 3 days
                    "recommended_salary_premium": 1.0,   # market rate
                    "confidence": 0.0,
                    "message": "No Interview learning yet - using conservative offer strategy",
                }

            patterns = profile.get("learned_patterns", {})

            # Extract learned offer strategy
            acceptance_rate = patterns.get("offer_acceptance_rate", 0.65)

            # Faster deadline for high-confidence candidates
            if acceptance_rate > 0.80:
                deadline_hours = 24
                salary_premium = 1.05  # Only 5% premium needed
            elif acceptance_rate > 0.65:
                deadline_hours = 48
                salary_premium = 1.10  # 10% premium
            else:
                deadline_hours = 72
                salary_premium = 1.15  # 15% premium to secure

            return {
                "predicted_offer_acceptance_rate": round(acceptance_rate, 3),
                "recommended_offer_deadline": deadline_hours,
                "recommended_salary_premium": round(salary_premium, 2),
                "confidence": profile.get("confidence", 0.0),
                "recommendation": patterns.get("recommendation_for_offer"),
            }

        except Exception as e:
            logger.error(f"[CrossModule] Failed to predict interview success: {e}", exc_info=True)
            return {
                "predicted_offer_acceptance_rate": 0.65,
                "recommended_offer_deadline": 72,
                "recommended_salary_premium": 1.0,
                "confidence": 0.0,
                "error": str(e),
            }

    @staticmethod
    def get_project_profitability_prediction(
        db: Session,
        tenant_id: str,
        client_segment: str,
        project_type: str,
    ) -> Dict[str, Any]:
        """
        Get Finance's predicted project profitability for deal selection.

        Called by Offer when deciding whether to commit resources.
        Uses Finance's learning to predict project margins based on client/type.

        Example output:
        {
            "predicted_margin_percentage": 0.35,  # 35% margin
            "profitability_category": "HIGH",
            "resource_efficiency": 0.88,
            "confidence": 0.79,
            "recommendation": "Prioritize this project type",
        }

        Args:
            db: Database session
            tenant_id: Tenant ID
            client_segment: Client segment (e.g., "tech_startup_seed")
            project_type: Project type (e.g., "backend_development")

        Returns:
            Profitability prediction for deal selection
        """
        try:
            # Get Finance's learned profile
            profile = LearningEventCollector.get_segment_profile(
                db=db,
                tenant_id=tenant_id,
                module="finance",
                segment_id=client_segment,
            )

            if not profile or not profile.get("learned_patterns"):
                # No learning yet - use industry baseline
                return {
                    "predicted_margin_percentage": 0.30,  # 30% baseline
                    "profitability_category": "MEDIUM",
                    "resource_efficiency": 0.80,
                    "confidence": 0.0,
                    "message": "No Finance learning yet - using industry baseline",
                }

            patterns = profile.get("learned_patterns", {})

            # Extract margin data
            margin_factor = patterns.get("expected_margin_factor", 0.30)
            project_margins = patterns.get("project_type_margins", {})

            # Get margin for this specific project type
            type_margin = project_margins.get(project_type, margin_factor)

            # Categorize profitability
            if type_margin > 0.40:
                category = "HIGH"
            elif type_margin > 0.25:
                category = "MEDIUM"
            else:
                category = "LOW"

            return {
                "predicted_margin_percentage": round(type_margin, 3),
                "profitability_category": category,
                "resource_efficiency": patterns.get("resource_efficiency_ratio", 0.85),
                "confidence": profile.get("confidence", 0.0),
                "recommendation": patterns.get("recommendation_for_finance"),
            }

        except Exception as e:
            logger.error(f"[CrossModule] Failed to predict profitability: {e}", exc_info=True)
            return {
                "predicted_margin_percentage": 0.30,
                "profitability_category": "MEDIUM",
                "resource_efficiency": 0.80,
                "confidence": 0.0,
                "error": str(e),
            }

    @staticmethod
    def get_employee_retention_prediction(
        db: Session,
        tenant_id: str,
        employee_segment: str,
    ) -> Dict[str, Any]:
        """
        Get Employee module's predicted retention for hiring decisions.

        Called by Finance when allocating resources.
        Uses Employee learning to predict 6/12-month retention based on segment.

        Example output:
        {
            "predicted_6month_retention": 0.92,
            "predicted_12month_retention": 0.85,
            "risk_factors": ["remote_team_integration", "senior_boredom"],
            "confidence": 0.81,
        }

        Args:
            db: Database session
            tenant_id: Tenant ID
            employee_segment: Employee segment (e.g., "senior_us_remote")

        Returns:
            Retention prediction for hiring/resource decisions
        """
        try:
            # Get Employee module's learned profile
            profile = LearningEventCollector.get_segment_profile(
                db=db,
                tenant_id=tenant_id,
                module="employee",
                segment_id=employee_segment,
            )

            if not profile or not profile.get("learned_patterns"):
                # No learning yet - use conservative baseline
                return {
                    "predicted_6month_retention": 0.85,
                    "predicted_12month_retention": 0.72,
                    "risk_factors": [],
                    "confidence": 0.0,
                    "message": "No Employee learning yet - using industry baseline",
                }

            patterns = profile.get("learned_patterns", {})

            retention_6mo = patterns.get("retention_rate_6mo", 0.85)
            retention_12mo = patterns.get("retention_rate_12mo", 0.72)
            risk_factors = patterns.get("engagement_drivers", [])

            return {
                "predicted_6month_retention": round(retention_6mo, 3),
                "predicted_12month_retention": round(retention_12mo, 3),
                "risk_factors": risk_factors,
                "confidence": profile.get("confidence", 0.0),
                "recommendation": patterns.get("recommendation_for_retention"),
            }

        except Exception as e:
            logger.error(f"[CrossModule] Failed to predict retention: {e}", exc_info=True)
            return {
                "predicted_6month_retention": 0.85,
                "predicted_12month_retention": 0.72,
                "risk_factors": [],
                "confidence": 0.0,
                "error": str(e),
            }

    @staticmethod
    def get_cascade_success_prediction(
        db: Session,
        tenant_id: str,
        candidate_segment: str,
        job_type: str,
    ) -> Dict[str, Any]:
        """
        Get combined prediction across Thunder → Flash → Interview → Offer → Finance → Employee.

        This is the MASTER prediction: given a candidate and job, predict total success
        from initial contact to 6-month retention.

        Example output:
        {
            "thunder_engagement_rate": 0.75,
            "flash_match_quality": 0.82,
            "interview_pass_rate": 0.78,
            "offer_acceptance_rate": 0.72,
            "employee_6month_retention": 0.88,
            "cascade_success_probability": 0.24,  # 75% * 82% * 78% * 72% * 88%
            "critical_risks": ["flash_match_quality_low", "offer_acceptance_risk"],
        }

        Args:
            db: Database session
            tenant_id: Tenant ID
            candidate_segment: Candidate segment
            job_type: Job type

        Returns:
            Cascade-wide probability of successful hire from contact to retention
        """
        try:
            # Get each module's prediction
            thunder = CrossModuleIntelligence.get_thunder_insights_for_flash(
                db, tenant_id, candidate_segment
            )
            flash = CrossModuleIntelligence.get_flash_candidate_quality_prediction(
                db, tenant_id, candidate_segment, thunder.get("engagement_rate", 0.5)
            )
            interview = CrossModuleIntelligence.get_interview_success_prediction(
                db, tenant_id, candidate_segment, job_type
            )
            offer = {
                "predicted_acceptance": interview.get("predicted_offer_acceptance_rate", 0.65)
            }
            finance = CrossModuleIntelligence.get_project_profitability_prediction(
                db, tenant_id, candidate_segment, job_type
            )
            employee = CrossModuleIntelligence.get_employee_retention_prediction(
                db, tenant_id, candidate_segment
            )

            # Calculate cascade probability (product of all stages)
            cascade_prob = (
                thunder.get("engagement_rate", 0.5) *
                flash.get("predicted_interview_pass_rate", 0.7) *
                interview.get("predicted_offer_acceptance_rate", 0.65) *
                offer.get("predicted_acceptance", 0.65) *
                employee.get("predicted_6month_retention", 0.85)
            )

            # Identify critical risks
            risks = []
            if thunder.get("engagement_rate", 0.5) < 0.60:
                risks.append("thunder_engagement_low")
            if flash.get("predicted_interview_pass_rate", 0.7) < 0.70:
                risks.append("flash_match_quality_low")
            if interview.get("predicted_offer_acceptance_rate", 0.65) < 0.65:
                risks.append("interview_pass_rate_low")
            if offer.get("predicted_acceptance", 0.65) < 0.65:
                risks.append("offer_acceptance_risk")
            if employee.get("predicted_6month_retention", 0.85) < 0.80:
                risks.append("retention_risk")

            return {
                "thunder_engagement_rate": round(thunder.get("engagement_rate", 0.5), 3),
                "flash_match_quality": round(flash.get("predicted_interview_pass_rate", 0.7), 3),
                "interview_pass_rate": round(interview.get("predicted_offer_acceptance_rate", 0.65), 3),
                "offer_acceptance_rate": round(offer.get("predicted_acceptance", 0.65), 3),
                "employee_6month_retention": round(employee.get("predicted_6month_retention", 0.85), 3),
                "cascade_success_probability": round(cascade_prob, 4),
                "critical_risks": risks,
                "recommendation": (
                    f"RECOMMEND" if cascade_prob > 0.25 else
                    "PROCEED_WITH_CAUTION" if cascade_prob > 0.15 else
                    "NOT_RECOMMENDED"
                ),
            }

        except Exception as e:
            logger.error(f"[CrossModule] Failed to get cascade prediction: {e}", exc_info=True)
            return {
                "cascade_success_probability": 0.0,
                "critical_risks": ["system_error"],
                "recommendation": "CHECK_LOGS",
                "error": str(e),
            }

    @staticmethod
    def _infer_candidate_segment(candidate) -> str:
        """
        Infer candidate segment from profile for learning lookups.

        Format: {seniority}_{location}_{skills}
        Example: "senior_us_python"

        Args:
            candidate: Candidate model instance

        Returns:
            Segment string for learning profile lookup
        """
        try:
            seniority = (candidate.seniority_level or "mid").lower().replace("-level", "").replace(" ", "_")
            location = "unknown"
            if candidate.current_location:
                # Extract country code from location (e.g., "New York, USA" → "us")
                if "usa" in candidate.current_location.lower() or "united states" in candidate.current_location.lower():
                    location = "us"
                elif "uk" in candidate.current_location.lower():
                    location = "uk"
                elif "india" in candidate.current_location.lower():
                    location = "in"
                else:
                    # Use first word as location abbreviation
                    location = candidate.current_location.split(",")[0].lower()[:2]

            # Extract primary skill from specialization
            skill = "unknown"
            if candidate.specialization:
                skills = [s.strip().lower() for s in candidate.specialization.split(";")]
                if skills:
                    skill = skills[0].replace(" ", "_")

            segment = f"{seniority}_{location}_{skill}"
            return segment

        except Exception as e:
            logger.warning(f"[CrossModule] Failed to infer candidate segment: {e}")
            return "unknown_unknown_unknown"

    @staticmethod
    def _infer_job_segment(job) -> str:
        """
        Infer job segment from job posting for learning lookups.

        Format: {level}_{specialization}_{location}
        Example: "senior_python_us"

        Args:
            job: Job model instance

        Returns:
            Segment string for learning profile lookup
        """
        try:
            # Extract job level from title or use seniority if available
            level = "mid"
            if hasattr(job, "seniority_level") and job.seniority_level:
                level = job.seniority_level.lower().replace("-level", "").replace(" ", "_")
            elif hasattr(job, "job_title") and job.job_title:
                title = job.job_title.lower()
                if "senior" in title or "staff" in title or "principal" in title:
                    level = "senior"
                elif "junior" in title or "entry" in title:
                    level = "junior"

            # Extract specialization from job_description or other fields
            specialization = "unknown"
            if hasattr(job, "job_description") and job.job_description:
                if "python" in job.job_description.lower():
                    specialization = "python"
                elif "java" in job.job_description.lower():
                    specialization = "java"
                elif "javascript" in job.job_description.lower():
                    specialization = "javascript"
                elif "aws" in job.job_description.lower():
                    specialization = "aws"

            # Extract location
            location = "unknown"
            if hasattr(job, "location") and job.location:
                if "usa" in job.location.lower() or "united states" in job.location.lower():
                    location = "us"
                elif "uk" in job.location.lower():
                    location = "uk"
                elif "india" in job.location.lower():
                    location = "in"
                else:
                    location = job.location.split(",")[0].lower()[:2]

            segment = f"{level}_{specialization}_{location}"
            return segment

        except Exception as e:
            logger.warning(f"[CrossModule] Failed to infer job segment: {e}")
            return "mid_unknown_unknown"
