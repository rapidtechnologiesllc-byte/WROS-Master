"""
SLM Export Service - Feeds employee intelligence to P&L and all agents

Exports employee performance, availability, utilization from SLM.
Used by all agents: Revenue, Cost, Allocation, Recruitment, etc.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


class SLMExportService:
    """Service for exporting SLM (employee intelligence) data to other systems"""

    @staticmethod
    def export_performance_scores(db: Session, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Export employee performance scores for P&L calculations.

        Used by: Bonus Agent, Revenue Agent, Sourcing Agent (performance benchmarks)
        Frequency: Daily (9 PM UTC)

        Returns: {
            "export_date": "2026-09-18",
            "employees": [
                {
                    "id": "emp_123",
                    "name": "Alice",
                    "performance_score": 92,  # 0-100
                    "performance_trend": "improving",  # improving|stable|declining
                    "skills": [
                        {"name": "Python", "level": "Expert", "years": 5},
                        {"name": "AWS", "level": "Intermediate", "years": 2}
                    ],
                    "last_updated": "2026-09-18T14:00:00Z"
                }
            ]
        }
        """
        try:
            # For now, return mock data (will query actual SLM when integrated)
            export_date = date or datetime.utcnow().strftime("%Y-%m-%d")

            # Mock employee data (will be replaced with actual SLM queries)
            mock_employees = [
                {
                    "id": "emp_001",
                    "name": "Alice",
                    "performance_score": 92,
                    "performance_trend": "improving",
                    "skills": [
                        {"name": "Python", "level": "Expert", "years": 5},
                        {"name": "AWS", "level": "Expert", "years": 3}
                    ],
                    "last_updated": datetime.utcnow().isoformat() + "Z"
                },
                {
                    "id": "emp_002",
                    "name": "Bob",
                    "performance_score": 78,
                    "performance_trend": "stable",
                    "skills": [
                        {"name": "Python", "level": "Intermediate", "years": 2},
                        {"name": "React", "level": "Intermediate", "years": 2}
                    ],
                    "last_updated": datetime.utcnow().isoformat() + "Z"
                },
                {
                    "id": "emp_003",
                    "name": "Carol",
                    "performance_score": 88,
                    "performance_trend": "improving",
                    "skills": [
                        {"name": "Kubernetes", "level": "Expert", "years": 4},
                        {"name": "AWS", "level": "Expert", "years": 4}
                    ],
                    "last_updated": datetime.utcnow().isoformat() + "Z"
                }
            ]

            return {
                "export_date": export_date,
                "employees": mock_employees,
                "total_count": len(mock_employees)
            }
        except Exception as e:
            logger.error(f"Error exporting performance scores: {e}", exc_info=True)
            raise

    @staticmethod
    def export_available_employees(db: Session) -> Dict[str, Any]:
        """
        Export employees available for allocation (real-time).

        Used by: Allocation Agent (find available people)
        Frequency: Real-time (event-driven when status changes)

        Returns: [
            {
                "employee_id": "emp_123",
                "name": "Alice",
                "status": "available",  # available|allocated|bench|training
                "bench_start_date": "2026-09-10",
                "bench_duration_days": 8,
                "skills": ["Python", "AWS"],
                "performance_score": 92,
                "billable_rate": 180,
                "available_hours_per_week": 40
            }
        ]
        """
        try:
            # Mock available employees (will query actual SLM when integrated)
            available = [
                {
                    "employee_id": "emp_001",
                    "name": "Alice",
                    "status": "bench",
                    "bench_start_date": "2026-09-10",
                    "bench_duration_days": 8,
                    "skills": ["Python", "AWS"],
                    "performance_score": 92,
                    "billable_rate": 180,
                    "available_hours_per_week": 40
                },
                {
                    "employee_id": "emp_003",
                    "name": "Carol",
                    "status": "bench",
                    "bench_start_date": "2026-09-16",
                    "bench_duration_days": 2,
                    "skills": ["Kubernetes", "AWS"],
                    "performance_score": 88,
                    "billable_rate": 200,
                    "available_hours_per_week": 40
                }
            ]

            return {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "available_employees": available,
                "available_count": len(available)
            }
        except Exception as e:
            logger.error(f"Error exporting available employees: {e}", exc_info=True)
            raise

    @staticmethod
    def export_utilization_snapshot(db: Session) -> Dict[str, Any]:
        """
        Export company-wide utilization metrics.

        Used by: Utilization Agent, P&L Cost Agent
        Frequency: Daily (8 AM UTC)

        Returns: {
            "snapshot_date": "2026-09-18",
            "company_utilization_pct": 87.5,
            "target_utilization_pct": 90,
            "variance": -2.5,
            "employees_total": 45,
            "employees_allocated": 42,
            "employees_bench": 3,
            "bench_cost_per_day": 1200,
            "bench_cost_trend": "increasing",
            "utilization_by_skill": {...}
        }
        """
        try:
            return {
                "snapshot_date": datetime.utcnow().strftime("%Y-%m-%d"),
                "company_utilization_pct": 87.5,
                "target_utilization_pct": 90,
                "variance": -2.5,
                "status": "slightly_below_target",
                "employees_total": 45,
                "employees_allocated": 42,
                "employees_bench": 3,
                "bench_cost_per_day": 1200,
                "bench_cost_weekly": 6000,
                "bench_cost_trend": "decreasing",
                "bench_runway_days": 45,
                "utilization_by_skill": {
                    "Python": {"utilization_pct": 92, "employees": 15},
                    "AWS": {"utilization_pct": 85, "employees": 12},
                    "Kubernetes": {"utilization_pct": 100, "employees": 3},
                    "React": {"utilization_pct": 78, "employees": 8}
                },
                "alerts": [
                    {
                        "type": "utilization_decline",
                        "severity": "medium",
                        "message": "Utilization declining 2% per week. At current rate, hit 75% in 4 weeks.",
                        "action": "Increase project allocation or reduce headcount"
                    }
                ]
            }
        except Exception as e:
            logger.error(f"Error exporting utilization snapshot: {e}", exc_info=True)
            raise

    @staticmethod
    def export_project_profitability(db: Session) -> Dict[str, Any]:
        """
        Export project-level cost and revenue data.

        Used by: Margin Agent, Allocation Agent (ranking projects)
        Frequency: Daily (8 AM UTC)

        Returns: {
            "snapshot_date": "2026-09-18",
            "projects": [
                {
                    "project_id": "proj_45",
                    "project_name": "Client X - Custom Development",
                    "status": "active",
                    "assigned_employees": 5,
                    "billable_hours_this_week": 160,
                    "revenue_projected": 500000,
                    "cost_projected": 350000,
                    "margin_usd": 150000,
                    "margin_pct": 30,
                    "priority_for_staffing": "high"
                }
            ]
        }
        """
        try:
            # Mock project data (will query actual projects when integrated)
            return {
                "snapshot_date": datetime.utcnow().strftime("%Y-%m-%d"),
                "projects": [
                    {
                        "project_id": "proj_001",
                        "project_name": "Client A - Premium Support",
                        "status": "active",
                        "assigned_employees": 3,
                        "billable_hours_this_week": 120,
                        "revenue_projected": 500000,
                        "cost_projected": 300000,
                        "margin_usd": 200000,
                        "margin_pct": 40,
                        "priority_for_staffing": "high"
                    },
                    {
                        "project_id": "proj_002",
                        "project_name": "Client B - Implementation",
                        "status": "active",
                        "assigned_employees": 2,
                        "billable_hours_this_week": 80,
                        "revenue_projected": 200000,
                        "cost_projected": 170000,
                        "margin_usd": 30000,
                        "margin_pct": 15,
                        "priority_for_staffing": "medium"
                    },
                    {
                        "project_id": "proj_003",
                        "project_name": "Internal - Tool Development",
                        "status": "active",
                        "assigned_employees": 1,
                        "billable_hours_this_week": 40,
                        "revenue_projected": 100000,
                        "cost_projected": 95000,
                        "margin_usd": 5000,
                        "margin_pct": 5,
                        "priority_for_staffing": "low"
                    }
                ],
                "total_projects": 3,
                "average_margin_pct": 20
            }
        except Exception as e:
            logger.error(f"Error exporting project profitability: {e}", exc_info=True)
            raise

    @staticmethod
    def export_hiring_pipeline_benchmark(db: Session) -> Dict[str, Any]:
        """
        Export performance benchmarks for sourcing/hiring agents.

        Used by: Sourcing Agent, Screening Agent (quality targets)
        Frequency: Weekly (Monday 9 AM UTC)

        Returns: {
            "benchmark_date": "2026-09-18",
            "by_skill": {
                "Python": {
                    "average_performance_score": 85,
                    "top_performers_count": 5,
                    "years_experience_median": 5,
                    "billing_rate_average": 165,
                    "quality_benchmark": 80  # Candidates must score >=80
                }
            }
        }
        """
        try:
            return {
                "benchmark_date": datetime.utcnow().strftime("%Y-%m-%d"),
                "by_skill": {
                    "Python": {
                        "average_performance_score": 85,
                        "top_performers_count": 5,
                        "years_experience_median": 5,
                        "billing_rate_average": 165,
                        "quality_benchmark": 80  # Screening gate
                    },
                    "AWS": {
                        "average_performance_score": 87,
                        "top_performers_count": 3,
                        "years_experience_median": 4,
                        "billing_rate_average": 190,
                        "quality_benchmark": 82
                    },
                    "Kubernetes": {
                        "average_performance_score": 90,
                        "top_performers_count": 3,
                        "years_experience_median": 6,
                        "billing_rate_average": 200,
                        "quality_benchmark": 85
                    }
                },
                "hiring_quality_target": 75,  # Screening: must score >=75
                "interview_pass_rate_target": 60  # Interview: 60% should be hired
            }
        except Exception as e:
            logger.error(f"Error exporting hiring benchmarks: {e}", exc_info=True)
            raise
