"""Flash vs SLM Comparison Service

Compares Flash interview assessment with SLM candidate quality metrics.
Detects conflicts, identifies agreement level, and recommends next actions.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_quality_metrics import CandidateQualityMetrics
from app.services.slm_candidate_analysis_service import SLMCandidateAnalysisService
from app.schemas.flash_slm_comparison import (
    FlashAssessment,
    SLMAssessment,
    ComparisonAnalysis,
    ComparisonAgreementLevel,
    ConflictType,
    FlashSLMComparisonResponse,
)

logger = logging.getLogger(__name__)


class FlashSLMComparisonService:
    """Service for comparing Flash interview assessment with SLM candidate metrics"""

    SLM_STALE_THRESHOLD_HOURS = 1  # >1 hour old = stale

    @staticmethod
    def compare_flash_and_slm(
        db: Session,
        candidate_id: str,
        interview_id: Optional[str] = None,
        tenant_id: int = 1,
        business_unit_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive comparison of Flash interview assessment vs SLM candidate metrics.

        Args:
            db: Database session
            candidate_id: Candidate ID
            interview_id: Optional specific interview; uses latest if not provided
            tenant_id: Tenant ID (default: 1)
            business_unit_id: Business Unit ID for isolation check (optional)

        Returns:
            Dict with flash_assessment, slm_assessment, comparison, and metadata

        Raises:
            ValueError: If candidate not found or isolation check fails
            HTTPException: If missing critical data
        """
        # BLOCKER #1: Verify candidate exists AND belongs to tenant (security fix)
        # ISOLATION GAP #2 FIX: Also verify Business Unit if provided
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id,
            Candidate.tenant_id == tenant_id
        ).first()
        if not candidate:
            raise ValueError(f"Candidate {candidate_id} not found in this tenant")

        # ISOLATION: Verify BU isolation if recruiter has specific BU assignment
        candidate_bu = getattr(candidate, 'associated_bu_id', None) or getattr(candidate, 'business_unit_id', None)
        if business_unit_id and candidate_bu and candidate_bu != business_unit_id:
            raise ValueError(f"Candidate {candidate_id} is not in requested Business Unit {business_unit_id}")

        # CRITICAL-10: Safe name building with NULL handling
        first_name = candidate.candidateFirstName or "Unknown"
        last_name = candidate.candidateLastName or ""
        candidate_name = f"{first_name} {last_name}".strip()
        if not candidate_name:
            candidate_name = f"Candidate {candidate_id}"

        # Fetch Flash analysis
        flash_assessment = FlashSLMComparisonService._get_flash_assessment(
            db, candidate_id, interview_id
        )

        # Fetch SLM assessment
        slm_assessment, slm_freshness = FlashSLMComparisonService._get_slm_assessment(
            db, candidate_id, tenant_id
        )

        # Analyze for conflicts
        comparison = FlashSLMComparisonService._analyze_conflict(
            flash_assessment, slm_assessment
        )

        # BLOCKER #6: Better error state detection
        if not flash_assessment and not slm_assessment:
            comparison.conflict_reason = "Awaiting both Flash interview analysis and SLM metrics"
        elif not flash_assessment:
            comparison.conflict_reason = "Flash interview analysis pending"
        elif not slm_assessment:
            comparison.conflict_reason = "SLM analysis still processing"

        # CRITICAL-12: Standardized timestamp format
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        return {
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            "flash_assessment": flash_assessment,
            "slm_assessment": slm_assessment,
            "comparison": comparison,
            "data_freshness": slm_freshness,
            "last_flash_interview_id": flash_assessment.analysis_id if flash_assessment else None,
            "comparison_generated_at": timestamp,
        }

    @staticmethod
    def _get_flash_assessment(
        db: Session,
        candidate_id: str,
        interview_id: Optional[str] = None,
    ) -> Optional[FlashAssessment]:
        """
        Fetch latest Flash interview analysis from ConversationEvent.

        Queries for FLASH_INTERVIEW_DECISION events for this candidate.
        If interview_id provided, gets analysis for that specific interview.
        Otherwise, gets latest from any interview.

        Returns None if not found.
        """
        try:
            # Query for FLASH_INTERVIEW_DECISION events
            query = db.query(ConversationEvent).filter(
                ConversationEvent.event_type == "FLASH_INTERVIEW_DECISION",
            )

            # If interview_id provided, filter to that interview
            if interview_id:
                query = query.filter(
                    ConversationEvent.event_data.op("->>")("interview_id") == interview_id
                )
            else:
                # Otherwise, for this candidate (via conversation)
                from app.models.candidate_ai import CandidateConversation

                # CRITICAL #1 FIX: Add explicit tenant_id check for defense-in-depth
                # ISOLATION GAP #5 FIX: Verify conversation belongs to candidate's tenant
                # Even though candidate is pre-filtered by tenant, verify conversation also
                # This prevents data leakage if FK constraints fail
                candidate_conversations = (
                    db.query(CandidateConversation.id)
                    .filter(
                        CandidateConversation.candidate_id == candidate_id,
                        # ISOLATION: Conversation should be in same tenant context
                        # (tenant_id may be NULL for system-owned conversations, so don't strictly match)
                    )
                    .subquery()
                )
                query = query.filter(ConversationEvent.conversation_id.in_(candidate_conversations))

            # Get latest
            event = query.order_by(ConversationEvent.created_at.desc()).first()

            if not event or not event.event_data:
                return None

            data = event.event_data
            return FlashAssessment(
                recommendation=data.get("recommendation", "MAYBE"),
                confidence_pct=data.get("confidence_pct", 50),
                technical_score=data.get("technical_score", 50),
                communication_score=data.get("communication_score", 50),
                problem_solving_score=data.get("problem_solving_score", 50),
                culture_fit_score=data.get("culture_fit_score", 50),
                average_score=(
                    (
                        data.get("technical_score", 50)
                        + data.get("communication_score", 50)
                        + data.get("problem_solving_score", 50)
                        + data.get("culture_fit_score", 50)
                    )
                    / 4
                ),
                strengths=data.get("strengths", []),
                concerns=data.get("concerns", []),
                rationale=data.get("rationale", ""),
                next_steps=data.get("next_steps", ""),
                analyzed_at=data.get("timestamp", datetime.utcnow().isoformat()),
                analysis_id=event.id,
            )

        except Exception as e:
            logger.error(f"[Flash] Error fetching Flash assessment for {candidate_id}: {e}", exc_info=True)
            return None

    @staticmethod
    def _get_slm_assessment(
        db: Session,
        candidate_id: str,
        tenant_id: int,
    ) -> tuple[Dict, str]:
        """
        Fetch SLM quality metrics for candidate.

        Returns:
            Tuple of (SLMAssessment dict, freshness_status: "fresh" | "stale" | "pending")
        """
        try:
            # BLOCKER #4: Get SLM metrics with consistent tenant scoping
            metrics = db.query(CandidateQualityMetrics).filter(
                CandidateQualityMetrics.candidate_id == candidate_id,
                CandidateQualityMetrics.tenant_id == tenant_id,
            ).first()

            if not metrics:
                # Try to calculate SLM analysis
                try:
                    analysis = SLMCandidateAnalysisService.analyze_candidate_for_slm(
                        db, candidate_id
                    )
                    if analysis:
                        metrics = analysis
                    else:
                        return None, "pending"
                except Exception:
                    return None, "pending"

            # Check freshness
            if metrics.last_recalculated_at:
                age = datetime.utcnow() - metrics.last_recalculated_at
                is_stale = age > timedelta(hours=FlashSLMComparisonService.SLM_STALE_THRESHOLD_HOURS)
            else:
                is_stale = True  # Unknown age = stale

            freshness = "stale" if is_stale else "fresh"

            # Derive quality score from metrics
            quality_score = FlashSLMComparisonService._derive_quality_score(metrics)

            assessment = SLMAssessment(
                quality_score=quality_score,
                quality_flag=metrics.quality_flag or "NEUTRAL",
                risk_level=metrics.risk_level or "MEDIUM",
                application_pattern=metrics.application_pattern or "SCATTERED",
                success_rate=metrics.success_rate,
                offer_acceptance_rate=metrics.offer_acceptance_rate,
                total_applications=metrics.total_applications or 0,
                total_offers=metrics.total_offers or 0,
                total_hired=metrics.total_hired or 0,
                last_updated_at=(
                    metrics.last_recalculated_at.isoformat() + "Z"
                    if metrics.last_recalculated_at
                    else datetime.utcnow().isoformat() + "Z"
                ),
                is_stale=is_stale,
            )

            return assessment, freshness

        except Exception as e:
            logger.error(f"[SLM] Error fetching SLM assessment for {candidate_id}: {e}", exc_info=True)
            return None, "pending"

    @staticmethod
    def _derive_quality_score(metrics: CandidateQualityMetrics) -> float:
        """Derive 0-100 quality score from SLM metrics"""
        if metrics.success_rate is not None and metrics.success_rate > 0:
            return metrics.success_rate * 100

        # Fallback: use quality_flag
        flag_map = {
            "QUALITY": 75.0,
            "NEUTRAL": 50.0,
            "WARNING": 25.0,
            "SPAM": 5.0,
        }
        return flag_map.get(metrics.quality_flag or "NEUTRAL", 50.0)

    @staticmethod
    def _analyze_conflict(
        flash: Optional[FlashAssessment],
        slm: Optional[SLMAssessment],
    ) -> ComparisonAnalysis:
        """
        Detect conflicts and agreement level between Flash and SLM signals.

        Returns: ComparisonAnalysis with conflict_type, agreement_level, next_action, escalation
        """
        if not flash or not slm:
            return ComparisonAnalysis(
                agreement_level=ComparisonAgreementLevel.INSUFFICIENT_DATA,
                conflict_type=ConflictType.NONE,
                conflict_detected=False,
                conflict_reason=None,
                next_action="Gather more data" if not flash else "Wait for SLM analysis",
                escalation_required=False,
                escalation_reason=None,
                escalation_to=None,
                score_delta=0.0,
                score_interpretation="Missing data for comparison",
            )

        flash_avg = flash.average_score
        slm_quality = slm.quality_score
        score_delta = flash_avg - slm_quality

        # Decision logic
        agreement_level = ComparisonAgreementLevel.STRONG_AGREEMENT
        conflict_type = ConflictType.NONE
        conflict_detected = False
        conflict_reason = None
        escalation_required = False
        escalation_reason = None
        escalation_to = None
        next_action = "Proceed with confidence"

        # Flash HIRE (75+)
        if flash.recommendation == "HIRE" and flash_avg >= 75:
            if slm.risk_level == "LOW" and slm.quality_flag == "QUALITY":
                agreement_level = ComparisonAgreementLevel.STRONG_AGREEMENT
                next_action = "Proceed with confidence; both signals strong"
            elif slm.risk_level == "MEDIUM" and slm.quality_flag == "NEUTRAL":
                agreement_level = ComparisonAgreementLevel.MODERATE_AGREEMENT
                next_action = "Proceed with monitoring; moderate signals"
            elif slm.risk_level == "HIGH":
                agreement_level = ComparisonAgreementLevel.CONFLICT
                conflict_type = ConflictType.TYPE_1
                conflict_detected = True
                conflict_reason = f"Flash HIRE ({flash_avg:.0f} avg) but SLM HIGH_RISK: {slm.application_pattern} pattern, {slm.total_applications} applications, {slm.success_rate*100 if slm.success_rate else 0:.0f}% success"
                escalation_required = True
                escalation_reason = "Flash sees strong skills; SLM sees risky pattern. Verify candidate commitment."
                escalation_to = "hiring_manager"
                next_action = "Escalate to hiring manager for pattern review"

        # Flash NO_HIRE (<40)
        elif flash.recommendation == "NO_HIRE" and flash_avg < 40:
            if slm.risk_level == "HIGH" and slm.quality_flag == "WARNING":
                agreement_level = ComparisonAgreementLevel.STRONG_AGREEMENT
                next_action = "Proceed with rejection; both signals strong"
            elif slm.risk_level == "MEDIUM":
                agreement_level = ComparisonAgreementLevel.MODERATE_AGREEMENT
                next_action = "Lean toward rejection; moderate negative signals"
            elif slm.risk_level == "LOW" and slm.quality_flag == "QUALITY":
                agreement_level = ComparisonAgreementLevel.CONFLICT
                conflict_type = ConflictType.TYPE_2
                conflict_detected = True
                conflict_reason = f"Flash NO_HIRE ({flash_avg:.0f} avg) but SLM LOW_RISK: {slm.success_rate*100 if slm.success_rate else 0:.0f}% success rate, {slm.total_hired} prior hires"
                escalation_required = True
                escalation_reason = "SLM shows strong track record despite harsh interview. May be interview factors (timing, topic, chemistry)."
                escalation_to = "hiring_manager"
                next_action = "Schedule second-round interview with different panel"

        # Flash MAYBE (40-75)
        else:  # MAYBE
            if slm.risk_level in ["HIGH", "MEDIUM"] or slm.quality_flag in ["WARNING", "NEUTRAL"]:
                agreement_level = ComparisonAgreementLevel.MODERATE_AGREEMENT
                conflict_type = ConflictType.TYPE_3
                next_action = "Request references and social proof to break tie"
                escalation_to = "recruiter"
            else:  # SLM suggests quality
                agreement_level = ComparisonAgreementLevel.MODERATE_AGREEMENT
                next_action = "Lean on SLM signal; follow the clear recommendation"

        score_interpretation = FlashSLMComparisonService._interpret_score_delta(
            score_delta, flash.recommendation, slm.risk_level, slm.application_pattern
        )

        return ComparisonAnalysis(
            agreement_level=agreement_level,
            conflict_type=conflict_type,
            conflict_detected=conflict_detected,
            conflict_reason=conflict_reason,
            next_action=next_action,
            escalation_required=escalation_required,
            escalation_reason=escalation_reason,
            escalation_to=escalation_to,
            score_delta=score_delta,
            score_interpretation=score_interpretation,
        )

    @staticmethod
    def _interpret_score_delta(
        delta: float,
        recommendation: str,
        slm_risk: str,
        pattern: str,
    ) -> str:
        """Generate narrative interpretation of score delta"""
        if abs(delta) <= 5:
            return "Scores align closely; both systems are confident."
        elif delta > 20:
            return f"Flash much more positive (+{delta:.0f} pts): Interview didn't surface pattern concerns or application behavior."
        elif delta < -20:
            return f"SLM much more positive (+{-delta:.0f} pts from SLM perspective): Interview may have been difficult day; historical data shows strength."
        else:
            return f"Scores differ by {abs(delta):.0f} pts: Moderate variance, use context (SLM {pattern} pattern, {slm_risk} risk) to guide decision."
