"""Timesheet Bulk Operations - Approve multiple timesheets, KPI tracking"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, date
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.timesheet import Timesheet
from app.core.logging import logger

class TimesheetBulkService:
    """Handles bulk timesheet operations and KPI tracking"""

    @staticmethod
    def get_pending_timesheets(
        db: Session,
        manager_id: Optional[str] = None,
        status: str = "SUBMITTED",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get pending timesheets for approval"""
        try:
            query = db.query(Timesheet).filter(Timesheet.status == status)

            if manager_id:
                query = query.filter(Timesheet.manager_id == manager_id)

            timesheets = query.order_by(Timesheet.created_at.desc()).limit(limit).all()

            return [
                {
                    "id": ts.id,
                    "employee_id": ts.employee_id,
                    "week_start": ts.week_start.isoformat() if hasattr(ts, 'week_start') and ts.week_start else None,
                    "hours_worked": ts.hours_worked,
                    "status": ts.status,
                    "submitted_at": ts.created_at.isoformat() if ts.created_at else None,
                    "manager_id": ts.manager_id
                }
                for ts in timesheets
            ]
        except Exception as e:
            logger.error(f"Failed to get pending timesheets: {e}", exc_info=True)
            raise

    @staticmethod
    def bulk_approve_timesheets(
        db: Session,
        timesheet_ids: List[str],
        approved_by: str,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Approve multiple timesheets in bulk"""
        try:
            approved_count = 0
            failed_count = 0
            failed_ids = []

            for ts_id in timesheet_ids:
                try:
                    timesheet = db.query(Timesheet).filter(Timesheet.id == ts_id).first()
                    if not timesheet:
                        failed_ids.append(ts_id)
                        failed_count += 1
                        continue

                    if timesheet.status not in ["SUBMITTED", "PENDING_APPROVAL"]:
                        failed_ids.append(ts_id)
                        failed_count += 1
                        continue

                    timesheet.status = "APPROVED"
                    timesheet.approved_at = datetime.utcnow()
                    timesheet.approved_by = approved_by
                    timesheet.approval_notes = notes
                    approved_count += 1

                except Exception as e:
                    logger.warning(f"Failed to approve timesheet {ts_id}: {e}")
                    failed_ids.append(ts_id)
                    failed_count += 1

            db.commit()
            logger.info(f"Bulk timesheet approval: {approved_count} approved, {failed_count} failed")

            return {
                "approved": approved_count,
                "failed": failed_count,
                "total": len(timesheet_ids),
                "failed_ids": failed_ids,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Bulk timesheet approval failed: {e}", exc_info=True)
            raise

    @staticmethod
    def bulk_reject_timesheets(
        db: Session,
        timesheet_ids: List[str],
        rejected_by: str,
        reason: str = ""
    ) -> Dict[str, Any]:
        """Reject multiple timesheets"""
        try:
            rejected_count = 0
            for ts_id in timesheet_ids:
                try:
                    timesheet = db.query(Timesheet).filter(Timesheet.id == ts_id).first()
                    if timesheet and timesheet.status in ["SUBMITTED", "PENDING_APPROVAL"]:
                        timesheet.status = "REJECTED"
                        timesheet.rejected_at = datetime.utcnow()
                        timesheet.rejected_by = rejected_by
                        timesheet.rejection_reason = reason
                        rejected_count += 1
                except Exception as e:
                    logger.warning(f"Failed to reject timesheet {ts_id}: {e}")

            db.commit()
            logger.info(f"Bulk timesheet rejection: {rejected_count} rejected")

            return {
                "rejected": rejected_count,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Bulk rejection failed: {e}", exc_info=True)
            raise

    @staticmethod
    def get_timesheet_kpis(
        db: Session,
        manager_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get timesheet KPIs for performance tracking"""
        try:
            query = db.query(Timesheet)

            if manager_id:
                query = query.filter(Timesheet.manager_id == manager_id)

            if start_date:
                query = query.filter(Timesheet.created_at >= start_date)
            if end_date:
                query = query.filter(Timesheet.created_at <= end_date)

            timesheets = query.all()

            total = len(timesheets)
            approved = sum(1 for ts in timesheets if ts.status == "APPROVED")
            pending = sum(1 for ts in timesheets if ts.status in ["SUBMITTED", "PENDING_APPROVAL"])
            rejected = sum(1 for ts in timesheets if ts.status == "REJECTED")

            approval_rate = (approved / total * 100) if total > 0 else 0
            avg_hours = sum(ts.hours_worked for ts in timesheets if ts.hours_worked) / total if total > 0 else 0

            return {
                "total_timesheets": total,
                "approved": approved,
                "pending": pending,
                "rejected": rejected,
                "approval_rate": round(approval_rate, 2),
                "average_hours": round(avg_hours, 2),
                "kpi_score": round(approval_rate, 2)  # KPI = approval rate %
            }
        except Exception as e:
            logger.error(f"Failed to get timesheet KPIs: {e}", exc_info=True)
            raise
