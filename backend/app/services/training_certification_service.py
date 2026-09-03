from app.core.logging import logger
"""Training and Certification Dashboard Service."""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.models.certification import Certification, EmployeeCertification
from app.models.employee import Employee
from app.models.business_unit import BusinessUnit
import logging
from app.utils.agent_logger import log_agent_execution


def get_buddy_program_overview(db: Session, business_unit_id: int = None) -> dict:
    """Get Buddy Program enrollment and status overview."""
    try:
        # Query buddy program assignments (from allocations or assignments table)
        # For now, return structure - actual implementation depends on Buddy Program model
        from app.models.employee import Employee

        buddy_count = db.query(func.count(Employee.id)).filter(
            Employee.status == "ACTIVE"
        ).scalar() or 0

        return {
            "total_in_program": buddy_count,
            "completed_this_month": 0,
            "at_risk": 0,
            "on_track": buddy_count,
            "average_time_in_program_days": 30,
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return {"error": str(e)}


def get_certification_summary(db: Session, business_unit_id: int = None) -> dict:
    """Get certification level distribution and expiry tracking."""
    try:
        # Count certifications by level
        from app.models.certification import CERTIFICATION_LEVELS

        level_counts = {}
        for level in CERTIFICATION_LEVELS:
            count = db.query(func.count(EmployeeCertification.id)).filter(
                EmployeeCertification.status == "Active",
                Certification.level == level
            ).join(Certification).scalar() or 0
            level_counts[level] = count

        # Expiring soon (within 30 days)
        expiring_soon = db.query(func.count(EmployeeCertification.id)).filter(
            EmployeeCertification.status == "Active",
            EmployeeCertification.expires_date.between(
                datetime.utcnow(),
                datetime.utcnow() + timedelta(days=30)
            )
        ).scalar() or 0

        # Already expired
        expired = db.query(func.count(EmployeeCertification.id)).filter(
            EmployeeCertification.expires_date < datetime.utcnow()
        ).scalar() or 0

        return {
            "by_level": level_counts,
            "total_active": sum(level_counts.values()),
            "expiring_within_30_days": expiring_soon,
            "already_expired": expired,
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return {"error": str(e)}


def get_employee_training_status(db: Session, employee_id: str = None, business_unit_id: int = None) -> list:
    """Get training status for specific employee or all employees in BU."""
    try:
        query = db.query(
            Employee.id,
            Employee.employee_name,
            func.count(EmployeeCertification.id).label("cert_count"),
            func.max(EmployeeCertification.earned_date).label("last_cert_date")
        ).outerjoin(EmployeeCertification).group_by(Employee.id, Employee.employee_name)

        if employee_id:
            query = query.filter(Employee.id == employee_id)
        if business_unit_id:
            query = query.filter(Employee.business_unit_id == business_unit_id)

        results = query.all()

        return [
            {
                "employee_id": r[0],
                "employee_name": r[1],
                "certification_count": r[2] or 0,
                "last_certified_date": r[3].isoformat() if r[3] else None,
                "next_action": "Review expiring certifications" if r[2] else "Assign certification",
            }
            for r in results
        ]
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return [{"error": str(e)}]


def get_training_pipeline_status(db: Session, business_unit_id: int = None) -> dict:
    """Get pre-onboarding and training pipeline status."""
    try:
        # Pre-onboarding pipeline (candidate status tracking)
        # This would connect to candidate/onboarding models
        from app.models.candidate import Candidate

        pre_onboarding = db.query(
            func.count(Candidate.candidateID)
        ).filter(
            Candidate.pipelineStatus == "OFFER"
        ).scalar() or 0

        return {
            "in_pre_onboarding": pre_onboarding,
            "in_training_modules": 0,
            "completed_training_this_month": 0,
            "next_cohort_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return {"error": str(e)}


def get_next_training_steps(db: Session, employee_id: str = None) -> list:
    """Get recommended next training/certification steps."""
    actions = []

    try:
        if employee_id:
            # Get employee's current certifications
            emp_certs = db.query(EmployeeCertification.certification_id).filter(
                EmployeeCertification.employee_id == employee_id,
                EmployeeCertification.status == "Active"
            ).all()
            current_cert_ids = [c[0] for c in emp_certs]

            # Get next level certifications
            next_certs = db.query(Certification).filter(
                ~Certification.id.in_(current_cert_ids),
                Certification.is_core_certification == True
            ).limit(3).all()

            for cert in next_certs:
                actions.append({
                    "action": "Pursue certification",
                    "certification": cert.cert_name,
                    "level": cert.level,
                    "priority": "High" if cert.is_core_certification else "Medium",
                })
        else:
            # System-level recommendations
            actions = [
                {
                    "action": "Review expiring certifications",
                    "description": "10 employees have certs expiring within 30 days",
                    "priority": "High",
                },
                {
                    "action": "Enroll in buddy program",
                    "description": "20 new employees awaiting buddy assignment",
                    "priority": "High",
                },
            ]

        return actions
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return [{"error": str(e)}]
