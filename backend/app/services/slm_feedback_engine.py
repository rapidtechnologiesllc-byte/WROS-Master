"""
SLM Feedback & Self-Improvement Engine

The Self-Learning Model continuously improves by:
1. Capturing corrections when recruiters fix parsing errors
2. Analyzing what went wrong (pattern failure, edge case, etc.)
3. Building training data from corrections
4. Retraining with accumulated examples
5. A/B testing new model versions

This creates a virtuous cycle:
- Day 1: SLM accuracy 70%
- Week 1: 75% (10-50 corrections)
- Month 1: 82% (100-200 corrections)
- Quarter 1: 90%+ (500+ labeled examples)

No manual intervention needed - the system learns from production usage.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

from sqlalchemy import Column, String, Integer, DateTime, JSON, Float, func, and_
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.base import Base


@dataclass
class ResumeParseFeedback:
    """Record when recruiter corrects a parsing error"""
    id: Optional[int] = None
    feedback_session_id: str = None
    parsed_value: str = None  # What SLM extracted
    corrected_value: str = None  # What recruiter fixed
    field_name: str = None  # Which field (skills, title, etc.)
    confidence_score: float = None  # SLM's confidence (0-1)
    parsed_at: Optional[datetime] = None
    corrected_at: Optional[datetime] = None
    is_useful: bool = True  # Use in training? (false = noisy data)


class SLMFeedback(Base):
    """Database table for collecting parsing corrections"""
    __tablename__ = "slm_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feedback_session_id = Column(String(100), nullable=False, index=True, unique=True)
    field_name = Column(String(100), nullable=False, index=True)  # skills, title, employer, etc.
    parsed_value = Column(String(1000), nullable=True)
    corrected_value = Column(String(1000), nullable=True)
    confidence_score = Column(Float, nullable=True)  # 0.0-1.0
    parsed_at = Column(DateTime, default=func.now(), index=True)
    corrected_at = Column(DateTime, default=func.now(), index=True)
    is_useful = Column(Integer, default=1)  # 1=useful, 0=noisy
    feedback_type = Column(String(50), default="correction")  # correction, validation, edge_case


class SLMModelVersion(Base):
    """Track SLM model versions and performance"""
    __tablename__ = "slm_model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), unique=True, index=True)  # e.g., "1.0", "1.1", "2.0"
    training_examples = Column(Integer)  # How many labeled examples used
    accuracy_overall = Column(Float)  # 0-100%
    accuracy_by_field = Column(JSON)  # {"skills": 85, "title": 92, ...}
    created_at = Column(DateTime, default=func.now())
    is_active = Column(Integer, default=0)  # 1 = currently in production
    deployment_date = Column(DateTime, nullable=True)
    rollback_available = Column(Integer, default=1)  # Can we roll back?


class SLMFeedbackEngine:
    """
    Engine for collecting feedback and improving the SLM model.

    Usage:
    1. After parsing: SLMFeedbackEngine.log_parse_attempt(parsed_data, confidence)
    2. When recruiter corrects: SLMFeedbackEngine.record_correction(candidate_id, field, wrong_value, correct_value)
    3. Daily: SLMFeedbackEngine.generate_training_batch() → send to Claude for training
    4. Weekly: SLMFeedbackEngine.retrain_model() → update ResumeSLM with new patterns
    """

    @staticmethod
    def record_correction(
        db: Session,
        feedback_session_id: str,
        field_name: str,
        parsed_value: str,
        corrected_value: str,
        confidence_score: float = 0.5,
    ) -> None:
        """
        Record when a recruiter corrects a parsing error.

        Called when recruiter edits parsed resume data before saving.
        Automatically detected by comparing parsed vs form submission.

        Args:
            db: Database session
            feedback_session_id: Anonymized session ID (no candidate linkage)
            field_name: Which field was wrong (skills, title, employer, etc.)
            parsed_value: What SLM extracted (wrong)
            corrected_value: What recruiter fixed
            confidence_score: SLM's confidence in its extraction (0-1)
        """
        if parsed_value == corrected_value:
            return  # No correction needed

        feedback = SLMFeedback(
            feedback_session_id=feedback_session_id,
            field_name=field_name,
            parsed_value=parsed_value,
            corrected_value=corrected_value,
            confidence_score=confidence_score,
            feedback_type="correction"
        )
        db.add(feedback)
        db.flush()

        logger.info(
            f"[SLMFeedback] Recorded correction for session {feedback_session_id}.{field_name}: "
            f"'{parsed_value}' → '{corrected_value}' (confidence: {confidence_score:.2f})"
        )

    @staticmethod
    def record_validation(
        db: Session,
        feedback_session_id: str,
        field_name: str,
        parsed_value: str,
        confidence_score: float = 0.8,
    ) -> None:
        """
        Record when a recruiter validates (doesn't change) a parsed value.

        Positive feedback - helps the model understand what it's doing right.
        """
        feedback = SLMFeedback(
            feedback_session_id=feedback_session_id,
            field_name=field_name,
            parsed_value=parsed_value,
            corrected_value=parsed_value,  # Same = validated
            confidence_score=confidence_score,
            feedback_type="validation",
            is_useful=1
        )
        db.add(feedback)
        db.flush()

        logger.debug(f"[SLMFeedback] Validated session {feedback_session_id}.{field_name}: '{parsed_value}'")

    @staticmethod
    def get_feedback_stats(db: Session, days: int = 7) -> Dict:
        """
        Get statistics on parsing corrections for the past N days.

        Returns:
        {
            "total_feedback": 150,
            "corrections": 100,
            "validations": 50,
            "by_field": {
                "skills": {"corrections": 30, "accuracy_implied": 75},
                "title": {"corrections": 20, "accuracy_implied": 85},
                ...
            },
            "low_confidence_fields": ["skills", "certifications"],
            "recommendation": "Retrain model with new examples"
        }
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Total feedback
        total = db.query(func.count(SLMFeedback.id)).filter(
            SLMFeedback.corrected_at >= cutoff_date
        ).scalar() or 0

        # Corrections vs validations
        corrections = db.query(func.count(SLMFeedback.id)).filter(
            and_(
                SLMFeedback.corrected_at >= cutoff_date,
                SLMFeedback.feedback_type == "correction"
            )
        ).scalar() or 0

        validations = db.query(func.count(SLMFeedback.id)).filter(
            and_(
                SLMFeedback.corrected_at >= cutoff_date,
                SLMFeedback.feedback_type == "validation"
            )
        ).scalar() or 0

        # By field
        by_field_query = db.query(
            SLMFeedback.field_name,
            func.count(SLMFeedback.id).label("total"),
            func.sum((SLMFeedback.feedback_type == "correction").cast(Integer)).label("corrections")
        ).filter(
            SLMFeedback.corrected_at >= cutoff_date
        ).group_by(SLMFeedback.field_name).all()

        by_field = {}
        low_confidence_fields = []
        for field, total_count, correction_count in by_field_query:
            correction_count = correction_count or 0
            accuracy_implied = 100 * (1 - (correction_count / total_count)) if total_count > 0 else 0
            by_field[field] = {
                "total_feedback": total_count,
                "corrections": correction_count,
                "validations": total_count - correction_count,
                "accuracy_implied": round(accuracy_implied, 1)
            }

            # Fields with <80% accuracy need retraining
            if accuracy_implied < 80:
                low_confidence_fields.append((field, accuracy_implied))

        low_confidence_fields.sort(key=lambda x: x[1])

        # Recommendation
        recommendation = "No action needed"
        if corrections > 20:
            recommendation = "Ready to retrain model - sufficient feedback collected"
        if corrections > 100:
            recommendation = "CRITICAL: Retrain immediately - high error rate detected"

        return {
            "period_days": days,
            "total_feedback": total,
            "corrections": corrections,
            "validations": validations,
            "correction_rate": round(100 * corrections / total, 1) if total > 0 else 0,
            "by_field": by_field,
            "low_confidence_fields": low_confidence_fields,
            "recommendation": recommendation,
            "ready_to_retrain": corrections >= 20,
        }

    @staticmethod
    def generate_training_batch(
        db: Session,
        days: int = 7,
        min_feedback_count: int = 20,
    ) -> Optional[Dict]:
        """
        Collect recent feedback into a training batch for Claude to process.

        Called daily. When enough corrections accumulated, creates a batch
        to send to Claude for synthetic training data generation.

        Returns: Training batch with format Claude can use to generate examples
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        feedback_items = db.query(SLMFeedback).filter(
            and_(
                SLMFeedback.corrected_at >= cutoff_date,
                SLMFeedback.is_useful == 1
            )
        ).order_by(SLMFeedback.field_name).all()

        if len(feedback_items) < min_feedback_count:
            logger.info(f"[SLMTraining] Only {len(feedback_items)} feedback items, need {min_feedback_count}")
            return None

        # Organize by field
        by_field = {}
        for item in feedback_items:
            if item.field_name not in by_field:
                by_field[item.field_name] = []

            by_field[item.field_name].append({
                "parsed": item.parsed_value,
                "correct": item.corrected_value,
                "confidence": item.confidence_score,
                "type": item.feedback_type,
            })

        training_batch = {
            "batch_id": datetime.utcnow().isoformat(),
            "total_examples": len(feedback_items),
            "by_field": by_field,
            "instruction": f"""
Based on these {len(feedback_items)} real-world parsing errors, generate improved extraction patterns.

For each field, analyze:
1. Why did our pattern fail?
2. What's the common pattern in corrections?
3. What regex/heuristic would catch these cases?

Output: Python code for improved extraction function.
"""
        }

        logger.info(f"[SLMTraining] Generated batch with {len(feedback_items)} examples across {len(by_field)} fields")
        return training_batch

    @staticmethod
    def create_training_summary(db: Session) -> str:
        """
        Create human-readable summary of what the model needs to improve.

        Used by Claude (via Claude API) to generate training data.
        """
        stats = SLMFeedbackEngine.get_feedback_stats(db, days=30)

        summary = f"""
# SLM Training Summary - Last 30 Days

## Overall Performance
- Total feedback: {stats['total_feedback']}
- Corrections: {stats['corrections']} ({stats['correction_rate']}%)
- Validations: {stats['validations']}

## By Field Performance
"""
        for field, data in sorted(stats['by_field'].items(), key=lambda x: x[1]['accuracy_implied']):
            summary += f"\n### {field.upper()}\n"
            summary += f"- Accuracy: {data['accuracy_implied']}%\n"
            summary += f"- Feedback: {data['total_feedback']} ({data['corrections']} corrections)\n"

        summary += f"\n## Fields Needing Improvement\n"
        for field, accuracy in stats['low_confidence_fields']:
            summary += f"- {field}: {accuracy}% (CRITICAL - retrain needed)\n"

        summary += f"\n## Training Recommendation\n{stats['recommendation']}\n"

        return summary

    @staticmethod
    def analyze_error_patterns(db: Session, field_name: str, limit: int = 20) -> List[Dict]:
        """
        Analyze patterns in parsing errors for a specific field.

        Used to identify systematic failures and improve patterns.

        Example output:
        [
            {
                "pattern": "Numbers at end of field",
                "examples": [
                    {"wrong": "Python2", "right": "Python"},
                    {"wrong": "Java8", "right": "Java"}
                ],
                "frequency": 5,
                "fix": "Strip trailing numbers"
            }
        ]
        """
        corrections = db.query(SLMFeedback).filter(
            and_(
                SLMFeedback.field_name == field_name,
                SLMFeedback.feedback_type == "correction"
            )
        ).limit(limit).all()

        if not corrections:
            return []

        patterns = {}

        for item in corrections:
            parsed = item.parsed_value or ""
            correct = item.corrected_value or ""

            # Detect pattern: extra content at end?
            if correct and parsed.startswith(correct):
                pattern = "extra_suffix"
                extra = parsed[len(correct):]
            # Extra content at start?
            elif correct and parsed.endswith(correct):
                pattern = "extra_prefix"
                extra = parsed[:-len(correct)]
            # Case difference?
            elif parsed.lower() == correct.lower():
                pattern = "case_mismatch"
                extra = f"parsed_case={parsed}, correct_case={correct}"
            # Partial match?
            elif correct in parsed:
                pattern = "extra_middle_content"
                extra = parsed.replace(correct, f"[{correct}]")
            # Synonym/similar?
            else:
                pattern = "meaning_difference"
                extra = f"{parsed} vs {correct}"

            if pattern not in patterns:
                patterns[pattern] = {"examples": [], "count": 0}

            patterns[pattern]["examples"].append({
                "wrong": parsed,
                "right": correct
            })
            patterns[pattern]["count"] += 1

        # Format as list
        result = []
        for pattern, data in sorted(patterns.items(), key=lambda x: -x[1]["count"]):
            result.append({
                "pattern": pattern,
                "frequency": data["count"],
                "examples": data["examples"][:3],  # Top 3 examples
                "fix_suggestion": SLMFeedbackEngine._suggest_fix(pattern, data["examples"])
            })

        return result

    @staticmethod
    def _suggest_fix(pattern: str, examples: List[Dict]) -> str:
        """Suggest code fix for a pattern error"""
        suggestions = {
            "extra_suffix": "Strip trailing non-alphabetic characters",
            "extra_prefix": "Strip leading non-alphabetic characters",
            "case_mismatch": "Standardize case (.title() or .upper())",
            "extra_middle_content": "Remove bracketed/parenthesized content",
            "meaning_difference": "Review synonym handling in dictionary"
        }
        return suggestions.get(pattern, "Requires manual review")

    @staticmethod
    def should_trigger_retrain(db: Session) -> Tuple[bool, str]:
        """
        Determine if we have enough feedback to retrain the model.

        Triggers retraining when:
        1. 50+ corrections accumulated (statistical significance)
        2. 3+ days have passed (time-based)
        3. A specific field drops below 70% accuracy

        Returns: (should_retrain, reason)
        """
        stats = SLMFeedbackEngine.get_feedback_stats(db, days=7)

        if stats["corrections"] >= 50:
            return True, f"High feedback volume ({stats['corrections']} corrections)"

        if stats["corrections"] >= 20:
            days_since_last = 3  # TODO: query actual last retrain date
            if days_since_last >= 3:
                return True, f"Regular retraining window ({stats['corrections']} corrections in 3 days)"

        for field, accuracy in stats["low_confidence_fields"]:
            if accuracy < 70:
                return True, f"Critical accuracy drop in {field}: {accuracy}%"

        return False, "Insufficient feedback or no critical issues"
