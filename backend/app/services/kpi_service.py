"""KPI Service - Track and calculate key performance indicators across all systems"""
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session

from app.core.logging import logger

class KPIService:
    """Tracks KPIs for Spartan Phalanx formations"""

    # Recruitment Phalanx KPIs
    RECRUITMENT_KPIS = {
        "candidates_sourced": {"unit": "count", "target": 100, "period": "monthly"},
        "candidate_quality_score": {"unit": "%", "target": 85, "period": "weekly"},
        "time_to_hire": {"unit": "days", "target": 14, "period": "monthly"},
        "offer_acceptance_rate": {"unit": "%", "target": 80, "period": "monthly"},
        "interview_to_offer": {"unit": "%", "target": 40, "period": "weekly"},
    }

    # Resource Management Phalanx KPIs
    RESOURCE_KPIS = {
        "resource_utilization": {"unit": "%", "target": 85, "period": "weekly"},
        "allocation_fulfillment": {"unit": "%", "target": 95, "period": "weekly"},
        "demand_fulfillment": {"unit": "%", "target": 90, "period": "monthly"},
        "timesheet_approval_rate": {"unit": "%", "target": 95, "period": "weekly"},
        "average_billable_hours": {"unit": "hours", "target": 35, "period": "weekly"},
    }

    # Finance Phalanx KPIs
    FINANCE_KPIS = {
        "invoice_approval_rate": {"unit": "%", "target": 95, "period": "weekly"},
        "revenue_recognition_rate": {"unit": "%", "target": 100, "period": "weekly"},
        "average_invoice_amount": {"unit": "USD", "target": 50000, "period": "monthly"},
        "cash_flow_forecast_accuracy": {"unit": "%", "target": 90, "period": "monthly"},
        "payment_collection_rate": {"unit": "%", "target": 95, "period": "monthly"},
    }

    @staticmethod
    def calculate_kpi(
        db: Session,
        phalanx: str,  # "recruitment", "resource_management", "finance"
        kpi_name: str,
        period: str = "weekly"  # weekly, monthly, quarterly, annual
    ) -> Dict[str, Any]:
        """Calculate a specific KPI value"""
        try:
            now = datetime.utcnow()

            if phalanx == "recruitment":
                if kpi_name == "candidates_sourced":
                    return KPIService._get_recruitment_candidates(db, period)
                elif kpi_name == "time_to_hire":
                    return KPIService._get_time_to_hire(db, period)
                elif kpi_name == "offer_acceptance_rate":
                    return KPIService._get_offer_acceptance_rate(db, period)

            elif phalanx == "resource_management":
                if kpi_name == "resource_utilization":
                    return KPIService._get_resource_utilization(db, period)
                elif kpi_name == "timesheet_approval_rate":
                    return KPIService._get_timesheet_approval_rate(db, period)
                elif kpi_name == "demand_fulfillment":
                    return KPIService._get_demand_fulfillment(db, period)

            elif phalanx == "finance":
                if kpi_name == "invoice_approval_rate":
                    return KPIService._get_invoice_approval_rate(db, period)
                elif kpi_name == "revenue_recognition_rate":
                    return KPIService._get_revenue_recognition_rate(db, period)

            return {"status": "unknown", "value": 0, "period": period}

        except Exception as e:
            logger.error(f"Failed to calculate KPI {phalanx}.{kpi_name}: {e}", exc_info=True)
            raise

    @staticmethod
    def _get_recruitment_candidates(db: Session, period: str) -> Dict[str, Any]:
        """Get recruitment KPI: candidates sourced in period"""
        try:
            from app.models.candidate import Candidate

            start_date = KPIService._get_period_start(period)
            candidates = db.query(Candidate).filter(
                Candidate.created_at >= start_date
            ).count()

            target = KPIService.RECRUITMENT_KPIS["candidates_sourced"]["target"]
            achievement = (candidates / target * 100) if target > 0 else 0

            return {
                "kpi": "candidates_sourced",
                "value": candidates,
                "target": target,
                "achievement_percent": round(achievement, 2),
                "status": "healthy" if achievement >= 80 else "warning" if achievement >= 50 else "critical",
                "period": period
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"Could not calculate recruitment candidates KPI: {e}")
            return {"kpi": "candidates_sourced", "value": 0, "status": "unknown"}

    @staticmethod
    def _get_time_to_hire(db: Session, period: str) -> Dict[str, Any]:
        """Get recruitment KPI: average time-to-hire"""
        try:
            from app.models.user import Jobs

            start_date = KPIService._get_period_start(period)
            jobs = db.query(Jobs).filter(
                Jobs.closed_at >= start_date
            ).all()

            if not jobs:
                return {"kpi": "time_to_hire", "value": 0, "status": "unknown"}

            total_days = 0
            for job in jobs:
                if hasattr(job, 'created_at') and hasattr(job, 'closed_at'):
                    if job.created_at and job.closed_at:
                        total_days += (job.closed_at - job.created_at).days

            avg_time = total_days / len(jobs) if jobs else 0
            target = KPIService.RECRUITMENT_KPIS["time_to_hire"]["target"]
            achievement = (1 - min(avg_time / target, 1)) * 100 if target > 0 else 0

            return {
                "kpi": "time_to_hire",
                "value": round(avg_time, 1),
                "unit": "days",
                "target": target,
                "achievement_percent": round(achievement, 2),
                "status": "healthy" if avg_time <= target else "warning" if avg_time <= target * 1.2 else "critical",
                "period": period
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"Could not calculate time-to-hire KPI: {e}")
            return {"kpi": "time_to_hire", "value": 0, "status": "unknown"}

    @staticmethod
    def _get_offer_acceptance_rate(db: Session, period: str) -> Dict[str, Any]:
        """Get recruitment KPI: offer acceptance rate"""
        try:

            start_date = KPIService._get_period_start(period)
            total_offers = db.query(Candidate).filter(
                Candidate.status == "OFFER",
                Candidate.created_at >= start_date
            ).count()

            accepted_offers = db.query(Candidate).filter(
                Candidate.status == "HIRED",
                Candidate.created_at >= start_date
            ).count()

            acceptance_rate = (accepted_offers / total_offers * 100) if total_offers > 0 else 0
            target = KPIService.RECRUITMENT_KPIS["offer_acceptance_rate"]["target"]

            return {
                "kpi": "offer_acceptance_rate",
                "value": round(acceptance_rate, 2),
                "unit": "%",
                "target": target,
                "offers_made": total_offers,
                "offers_accepted": accepted_offers,
                "status": "healthy" if acceptance_rate >= 75 else "warning" if acceptance_rate >= 60 else "critical",
                "period": period
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"Could not calculate offer acceptance KPI: {e}")
            return {"kpi": "offer_acceptance_rate", "value": 0, "status": "unknown"}

    @staticmethod
    def _get_resource_utilization(db: Session, period: str) -> Dict[str, Any]:
        """Get resource management KPI: resource utilization %"""
        try:
            from app.models.employee_allocation import EmployeeAllocation

            start_date = KPIService._get_period_start(period)
            allocations = db.query(EmployeeAllocation).filter(
                EmployeeAllocation.start_date >= start_date
            ).all()

            if not allocations:
                return {"kpi": "resource_utilization", "value": 0, "status": "unknown"}

            # Count active allocations as billable
            active_count = sum(1 for a in allocations if hasattr(a, 'status') and a.status == "ACTIVE")
            total_count = len(allocations)
            utilization = (active_count / total_count * 100) if total_count > 0 else 0

            target = KPIService.RESOURCE_KPIS["resource_utilization"]["target"]
            return {
                "kpi": "resource_utilization",
                "value": round(utilization, 2),
                "unit": "%",
                "target": target,
                "status": "healthy" if utilization >= 80 else "warning" if utilization >= 60 else "critical",
                "period": period
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"Could not calculate resource utilization KPI: {e}")
            return {"kpi": "resource_utilization", "value": 0, "status": "unknown"}

    @staticmethod
    def _get_timesheet_approval_rate(db: Session, period: str) -> Dict[str, Any]:
        """Get resource management KPI: timesheet approval rate"""
        try:
            from app.models.timesheet import Timesheet

            start_date = KPIService._get_period_start(period)
            total = db.query(Timesheet).filter(
                Timesheet.created_at >= start_date
            ).count()

            approved = db.query(Timesheet).filter(
                Timesheet.status == "APPROVED",
                Timesheet.created_at >= start_date
            ).count()

            approval_rate = (approved / total * 100) if total > 0 else 0
            target = KPIService.RESOURCE_KPIS["timesheet_approval_rate"]["target"]

            return {
                "kpi": "timesheet_approval_rate",
                "value": round(approval_rate, 2),
                "unit": "%",
                "target": target,
                "timesheets_submitted": total,
                "timesheets_approved": approved,
                "status": "healthy" if approval_rate >= 90 else "warning" if approval_rate >= 70 else "critical",
                "period": period
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"Could not calculate timesheet approval KPI: {e}")
            return {"kpi": "timesheet_approval_rate", "value": 0, "status": "unknown"}

    @staticmethod
    def _get_demand_fulfillment(db: Session, period: str) -> Dict[str, Any]:
        """Get resource management KPI: demand fulfillment %"""
        try:
            from app.models.resource_demand import ResourceDemand

            demands = db.query(ResourceDemand).all()
            if not demands:
                return {"kpi": "demand_fulfillment", "value": 0, "status": "unknown"}

            total_needed = sum(d.quantity_needed for d in demands if hasattr(d, 'quantity_needed'))
            total_fulfilled = sum(d.quantity_fulfilled for d in demands if hasattr(d, 'quantity_fulfilled'))

            fulfillment = (total_fulfilled / total_needed * 100) if total_needed > 0 else 0
            target = KPIService.RESOURCE_KPIS["demand_fulfillment"]["target"]

            return {
                "kpi": "demand_fulfillment",
                "value": round(fulfillment, 2),
                "unit": "%",
                "target": target,
                "quantity_needed": total_needed,
                "quantity_fulfilled": total_fulfilled,
                "status": "healthy" if fulfillment >= 85 else "warning" if fulfillment >= 65 else "critical",
                "period": period
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"Could not calculate demand fulfillment KPI: {e}")
            return {"kpi": "demand_fulfillment", "value": 0, "status": "unknown"}

    @staticmethod
    def _get_invoice_approval_rate(db: Session, period: str) -> Dict[str, Any]:
        """Get finance KPI: invoice approval rate"""
        try:
            from app.models.invoice import Invoice

            start_date = KPIService._get_period_start(period)
            total = db.query(Invoice).filter(
                Invoice.created_at >= start_date
            ).count()

            approved = db.query(Invoice).filter(
                Invoice.status == "APPROVED",
                Invoice.created_at >= start_date
            ).count()

            approval_rate = (approved / total * 100) if total > 0 else 0
            target = KPIService.FINANCE_KPIS["invoice_approval_rate"]["target"]

            return {
                "kpi": "invoice_approval_rate",
                "value": round(approval_rate, 2),
                "unit": "%",
                "target": target,
                "invoices_submitted": total,
                "invoices_approved": approved,
                "status": "healthy" if approval_rate >= 90 else "warning" if approval_rate >= 70 else "critical",
                "period": period
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"Could not calculate invoice approval KPI: {e}")
            return {"kpi": "invoice_approval_rate", "value": 0, "status": "unknown"}

    @staticmethod
    def _get_revenue_recognition_rate(db: Session, period: str) -> Dict[str, Any]:
        """Get finance KPI: revenue recognition rate"""
        try:
            from app.models.revenue_recognition import RevenueRecognition

            start_date = KPIService._get_period_start(period)
            approved_invoices = db.query(Invoice).filter(
                Invoice.status == "APPROVED",
                Invoice.created_at >= start_date
            ).count()

            recognized = db.query(RevenueRecognition).filter(
                RevenueRecognition.created_at >= start_date
            ).count()

            recognition_rate = (recognized / approved_invoices * 100) if approved_invoices > 0 else 0
            target = KPIService.FINANCE_KPIS["revenue_recognition_rate"]["target"]

            return {
                "kpi": "revenue_recognition_rate",
                "value": round(recognition_rate, 2),
                "unit": "%",
                "target": target,
                "approved_invoices": approved_invoices,
                "revenues_recognized": recognized,
                "status": "healthy" if recognition_rate >= 95 else "warning" if recognition_rate >= 75 else "critical",
                "period": period
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"Could not calculate revenue recognition KPI: {e}")
            return {"kpi": "revenue_recognition_rate", "value": 0, "status": "unknown"}

    @staticmethod
    def _get_period_start(period: str) -> datetime:
        """Get start date for period"""
        now = datetime.utcnow()
        if period == "weekly":
            return now - timedelta(days=7)
        elif period == "monthly":
            return now - timedelta(days=30)
        elif period == "quarterly":
            return now - timedelta(days=90)
        elif period == "annual":
            return now - timedelta(days=365)
        else:
            return now - timedelta(days=7)

    @staticmethod
    def get_phalanx_health_score(
        db: Session,
        phalanx: str,  # "recruitment", "resource_management", "finance"
        period: str = "weekly"
    ) -> Dict[str, Any]:
        """Calculate overall Phalanx health score (0-100)"""
        try:
            kpi_map = {
                "recruitment": KPIService.RECRUITMENT_KPIS,
                "resource_management": KPIService.RESOURCE_KPIS,
                "finance": KPIService.FINANCE_KPIS
            }

            if phalanx not in kpi_map:
                return {"phalanx": phalanx, "health_score": 0, "status": "unknown"}

            kpis = kpi_map[phalanx]
            scores = []

            for kpi_name in kpis.keys():
                try:
                    kpi_result = KPIService.calculate_kpi(db, phalanx, kpi_name, period)
                    if "achievement_percent" in kpi_result:
                        scores.append(kpi_result["achievement_percent"])
                    elif "value" in kpi_result and "target" in kpi_result:
                        achievement = (kpi_result["value"] / kpi_result["target"] * 100) if kpi_result["target"] > 0 else 0
                        scores.append(min(achievement, 100))
                except:
                    pass

            avg_score = sum(scores) / len(scores) if scores else 0

            return {
                "phalanx": phalanx,
                "health_score": round(avg_score, 2),
                "status": "healthy" if avg_score >= 85 else "warning" if avg_score >= 70 else "critical",
                "kpi_count": len(scores),
                "period": period
            }
        except Exception as e:
            logger.error(f"Failed to calculate phalanx health: {e}", exc_info=True)
            return {"phalanx": phalanx, "health_score": 0, "status": "unknown"}
