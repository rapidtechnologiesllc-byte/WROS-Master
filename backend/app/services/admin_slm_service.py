"""
Admin SLM Management Service
=============================
Allows admins to view, update, and monitor SLM patterns and learning
"""

from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)


class AdminSLMManager:
    """
    Manages SLM patterns for admin oversight and updates
    Tracks learning, pattern effectiveness, and allows manual adjustments
    """

    def __init__(self, db: Session):
        self.db = db

    def get_all_patterns(self) -> Dict:
        """
        Return all SLM patterns organized by complexity
        """
        from app.models.admin import SLMPattern

        simple_patterns = self.db.query(SLMPattern).filter(
            SLMPattern.complexity == "simple"
        ).all()

        moderate_patterns = self.db.query(SLMPattern).filter(
            SLMPattern.complexity == "moderate"
        ).all()

        complex_patterns = self.db.query(SLMPattern).filter(
            SLMPattern.complexity == "complex"
        ).all()

        return {
            "simple": [
                {
                    "id": p.id,
                    "pattern": p.pattern,
                    "lookup_type": p.lookup_type,
                    "usage_count": p.usage_count,
                    "accuracy": p.accuracy_percentage,
                    "created_at": p.created_at.isoformat(),
                    "last_used": p.last_used_at.isoformat() if p.last_used_at else None,
                    "enabled": p.enabled,
                    "added_by": p.added_by,
                }
                for p in simple_patterns
            ],
            "moderate": [
                {
                    "id": p.id,
                    "pattern": p.pattern,
                    "lookup_type": p.lookup_type,
                    "usage_count": p.usage_count,
                    "accuracy": p.accuracy_percentage,
                    "created_at": p.created_at.isoformat(),
                    "last_used": p.last_used_at.isoformat() if p.last_used_at else None,
                    "enabled": p.enabled,
                    "added_by": p.added_by,
                }
                for p in moderate_patterns
            ],
            "complex": [
                {
                    "id": p.id,
                    "pattern": p.pattern,
                    "lookup_type": p.lookup_type,
                    "usage_count": p.usage_count,
                    "accuracy": p.accuracy_percentage,
                    "created_at": p.created_at.isoformat(),
                    "last_used": p.last_used_at.isoformat() if p.last_used_at else None,
                    "enabled": p.enabled,
                    "added_by": p.added_by,
                }
                for p in complex_patterns
            ],
        }

    def add_pattern(
        self,
        pattern: str,
        complexity: str,
        lookup_type: str,
        added_by: str,
    ) -> Dict:
        """
        Add a new SLM pattern
        complexity: 'simple', 'moderate', 'complex'
        lookup_type: 'job_list', 'candidate_status', 'job_location', 'job_requirements', etc.
        """
        from app.models.admin import SLMPattern

        # Check if pattern already exists
        existing = self.db.query(SLMPattern).filter(
            SLMPattern.pattern == pattern,
            SLMPattern.complexity == complexity,
        ).first()

        if existing:
            return {
                "success": False,
                "error": "Pattern already exists",
                "pattern_id": existing.id,
            }

        new_pattern = SLMPattern(
            pattern=pattern,
            complexity=complexity,
            lookup_type=lookup_type,
            added_by=added_by,
            created_at=datetime.utcnow(),
            enabled=True,
            usage_count=0,
            accuracy_percentage=100,  # Start at 100%, adjust as data comes in
        )

        self.db.add(new_pattern)
        self.db.commit()

        logger.info(f"[ADMIN-SLM] Added pattern: {pattern} ({complexity})")

        return {
            "success": True,
            "pattern_id": new_pattern.id,
            "message": f"Pattern added: {pattern}",
        }

    def update_pattern(
        self,
        pattern_id: int,
        updates: Dict,
    ) -> Dict:
        """
        Update an existing pattern
        Can update: pattern, lookup_type, enabled status
        """
        from app.models.admin import SLMPattern

        pattern = self.db.query(SLMPattern).filter(
            SLMPattern.id == pattern_id
        ).first()

        if not pattern:
            return {"success": False, "error": "Pattern not found"}

        # Update allowed fields
        if "pattern" in updates:
            pattern.pattern = updates["pattern"]
        if "lookup_type" in updates:
            pattern.lookup_type = updates["lookup_type"]
        if "enabled" in updates:
            pattern.enabled = updates["enabled"]

        self.db.commit()

        logger.info(f"[ADMIN-SLM] Updated pattern {pattern_id}: {updates}")

        return {
            "success": True,
            "pattern_id": pattern_id,
            "message": "Pattern updated",
        }

    def delete_pattern(self, pattern_id: int) -> Dict:
        """
        Disable a pattern (soft delete - keeps history)
        """
        from app.models.admin import SLMPattern

        pattern = self.db.query(SLMPattern).filter(
            SLMPattern.id == pattern_id
        ).first()

        if not pattern:
            return {"success": False, "error": "Pattern not found"}

        pattern.enabled = False
        self.db.commit()

        logger.info(f"[ADMIN-SLM] Disabled pattern {pattern_id}")

        return {
            "success": True,
            "message": "Pattern disabled",
        }

    def get_pattern_analytics(self) -> Dict:
        """
        Get SLM performance analytics
        """
        from app.models.admin import SLMPattern, SLMQuestionLog

        # Get all enabled patterns
        patterns = self.db.query(SLMPattern).filter(
            SLMPattern.enabled == True
        ).all()

        # Get usage from last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_usage = self.db.query(SLMQuestionLog).filter(
            SLMQuestionLog.created_at > thirty_days_ago
        ).all()

        total_questions = len(recent_usage)
        slm_answered = len([u for u in recent_usage if u.source == "local_slm"])
        claude_answered = len([u for u in recent_usage if u.source == "claude"])

        local_pct = (slm_answered / total_questions * 100) if total_questions > 0 else 0

        # Calculate cost savings
        claude_cost_per_call = 0.015
        estimated_savings = slm_answered * claude_cost_per_call

        # Find top patterns
        top_patterns = (
            self.db.query(SLMPattern)
            .filter(SLMPattern.enabled == True)
            .order_by(SLMPattern.usage_count.desc())
            .limit(5)
            .all()
        )

        return {
            "total_patterns": len([p for p in patterns if p.enabled]),
            "simple_patterns": len([p for p in patterns if p.complexity == "simple"]),
            "moderate_patterns": len([p for p in patterns if p.complexity == "moderate"]),
            "complex_patterns": len([p for p in patterns if p.complexity == "complex"]),
            "total_questions_30days": total_questions,
            "slm_answered": slm_answered,
            "claude_answered": claude_answered,
            "local_slm_percentage": round(local_pct, 1),
            "estimated_savings_usd": round(estimated_savings, 2),
            "top_patterns": [
                {
                    "pattern": p.pattern,
                    "complexity": p.complexity,
                    "usage_count": p.usage_count,
                    "accuracy": p.accuracy_percentage,
                }
                for p in top_patterns
            ],
        }

    def get_learning_history(self, days: int = 30) -> List[Dict]:
        """
        Get SLM learning/update history
        """
        from app.models.admin import SLMPatternUpdate

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        updates = self.db.query(SLMPatternUpdate).filter(
            SLMPatternUpdate.created_at > cutoff_date
        ).order_by(SLMPatternUpdate.created_at.desc()).all()

        return [
            {
                "id": u.id,
                "pattern_id": u.pattern_id,
                "action": u.action,  # 'added', 'updated', 'disabled'
                "changes": json.loads(u.changes) if u.changes else {},
                "added_by": u.added_by,
                "created_at": u.created_at.isoformat(),
            }
            for u in updates
        ]

    def get_pattern_performance(self, pattern_id: int) -> Dict:
        """
        Get detailed performance metrics for a specific pattern
        """
        from app.models.admin import SLMPattern, SLMQuestionLog

        pattern = self.db.query(SLMPattern).filter(
            SLMPattern.id == pattern_id
        ).first()

        if not pattern:
            return {"success": False, "error": "Pattern not found"}

        # Get usage over time (last 30 days, daily)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        daily_usage = {}
        for i in range(30):
            day = (datetime.utcnow() - timedelta(days=i)).date()
            day_str = day.isoformat()

            count = self.db.query(SLMQuestionLog).filter(
                SLMQuestionLog.pattern_id == pattern_id,
                SLMQuestionLog.source == "local_slm",
            ).count()

            daily_usage[day_str] = count

        return {
            "pattern_id": pattern_id,
            "pattern": pattern.pattern,
            "complexity": pattern.complexity,
            "lookup_type": pattern.lookup_type,
            "total_usage": pattern.usage_count,
            "accuracy": pattern.accuracy_percentage,
            "enabled": pattern.enabled,
            "created_at": pattern.created_at.isoformat(),
            "last_used": pattern.last_used_at.isoformat()
            if pattern.last_used_at
            else None,
            "daily_usage_30days": daily_usage,
        }

    def bulk_import_patterns(
        self, patterns_list: List[Dict], added_by: str
    ) -> Dict:
        """
        Bulk import patterns from admin
        patterns_list: [{"pattern": "...", "complexity": "...", "lookup_type": "..."}, ...]
        """
        from app.models.admin import SLMPattern

        added = 0
        skipped = 0
        errors = []

        for item in patterns_list:
            try:
                # Check if exists
                existing = self.db.query(SLMPattern).filter(
                    SLMPattern.pattern == item["pattern"],
                    SLMPattern.complexity == item["complexity"],
                ).first()

                if existing:
                    skipped += 1
                    continue

                new_pattern = SLMPattern(
                    pattern=item["pattern"],
                    complexity=item["complexity"],
                    lookup_type=item.get("lookup_type", "general"),
                    added_by=added_by,
                    created_at=datetime.utcnow(),
                    enabled=True,
                    usage_count=0,
                    accuracy_percentage=100,
                )

                self.db.add(new_pattern)
                added += 1

            except Exception as e:
                errors.append(f"Error importing pattern: {item}: {str(e)}")

        self.db.commit()

        logger.info(f"[ADMIN-SLM] Bulk import: {added} added, {skipped} skipped")

        return {
            "success": True,
            "added": added,
            "skipped": skipped,
            "errors": errors,
        }

    def get_dashboard_data(self) -> Dict:
        """
        Get all data needed for admin dashboard
        """
        return {
            "patterns": self.get_all_patterns(),
            "analytics": self.get_pattern_analytics(),
            "learning_history": self.get_learning_history(days=30),
        }
