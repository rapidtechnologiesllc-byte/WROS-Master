"""Demand Management Service - Manage resource demand and fulfillment"""
import logging
from typing import Any, Dict, Optional
from datetime import datetime, date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.logging import logger

class DemandManagementService:
    """Manages resource demand: creation, adjustment, fulfillment tracking"""

    @staticmethod
    def create_demand(
        db: Session,
        resource_type: str,  # "DEVELOPER", "QA", "DESIGNER", etc.
        quantity: int,
        start_date: date,
        end_date: date,
        business_unit_id: str,
        project_id: Optional[str] = None,
        created_by: str = "system"
    ) -> Dict[str, Any]:
        """Create a resource demand"""
        try:
            from app.models.resource_demand import ResourceDemand

            demand = ResourceDemand(
                id=str(uuid4()),
                resource_type=resource_type,
                quantity_needed=quantity,
                quantity_fulfilled=0,
                start_date=start_date,
                end_date=end_date,
                business_unit_id=business_unit_id,
                project_id=project_id,
                status="OPEN",
                created_by=created_by,
                created_at=datetime.utcnow()
            )
            db.add(demand)
            db.commit()

            logger.info(f"Demand created: {demand.id}, type={resource_type}, qty={quantity}")
            return {
                "id": demand.id,
                "resource_type": resource_type,
                "quantity_needed": quantity,
                "status": "OPEN",
                "created_at": demand.created_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to create demand: {e}", exc_info=True)
            raise ValueError(f"Demand creation failed: {str(e)}")

    @staticmethod
    def adjust_demand_quantity(
        db: Session,
        demand_id: str,
        new_quantity: int,
        adjusted_by: str
    ) -> Dict[str, Any]:
        """Adjust resource demand quantity"""
        try:

            demand = db.query(ResourceDemand).filter(ResourceDemand.id == demand_id).first()
            if not demand:
                raise ValueError(f"Demand not found: {demand_id}")

            old_quantity = demand.quantity_needed
            demand.quantity_needed = new_quantity
            demand.adjusted_at = datetime.utcnow()
            demand.adjusted_by = adjusted_by
            db.commit()

            logger.info(f"Demand adjusted: {demand_id}, {old_quantity}→{new_quantity}")
            return {
                "id": demand.id,
                "old_quantity": old_quantity,
                "new_quantity": new_quantity,
                "adjusted_at": demand.adjusted_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to adjust demand: {e}", exc_info=True)
            raise

    @staticmethod
    def close_demand(
        db: Session,
        demand_id: str,
        reason: str = "FULFILLED",
        closed_by: str = "system"
    ) -> Dict[str, Any]:
        """Close a resource demand"""
        try:

            demand = db.query(ResourceDemand).filter(ResourceDemand.id == demand_id).first()
            if not demand:
                raise ValueError(f"Demand not found: {demand_id}")

            demand.status = "CLOSED"
            demand.closure_reason = reason
            demand.closed_at = datetime.utcnow()
            demand.closed_by = closed_by
            db.commit()

            logger.info(f"Demand closed: {demand_id}, reason={reason}")
            return {
                "id": demand.id,
                "status": "CLOSED",
                "reason": reason,
                "closed_at": demand.closed_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to close demand: {e}", exc_info=True)
            raise

    @staticmethod
    def get_demand_fulfillment_status(
        db: Session,
        demand_id: str
    ) -> Dict[str, Any]:
        """Get fulfillment status for a demand"""
        try:

            demand = db.query(ResourceDemand).filter(ResourceDemand.id == demand_id).first()
            if not demand:
                raise ValueError(f"Demand not found: {demand_id}")

            quantity_needed = demand.quantity_needed
            quantity_fulfilled = demand.quantity_fulfilled
            fulfillment_percent = (quantity_fulfilled / quantity_needed * 100) if quantity_needed > 0 else 0

            return {
                "demand_id": demand.id,
                "resource_type": demand.resource_type,
                "quantity_needed": quantity_needed,
                "quantity_fulfilled": quantity_fulfilled,
                "quantity_remaining": quantity_needed - quantity_fulfilled,
                "fulfillment_percent": round(fulfillment_percent, 2),
                "status": demand.status,
                "start_date": demand.start_date.isoformat() if hasattr(demand, 'start_date') else None,
                "end_date": demand.end_date.isoformat() if hasattr(demand, 'end_date') else None
            }
        except Exception as e:
            logger.error(f"Failed to get fulfillment status: {e}", exc_info=True)
            raise
