"""Finance Service - Invoice management, approval workflow, revenue recognition"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.invoice import Invoice
from app.models.revenue_recognition import RevenueRecognition
from app.core.logging import logger

class FinanceService:
    """Handles finance operations: invoicing, approval, revenue recognition"""

    @staticmethod
    def create_invoice(
        db: Session,
        opportunity_id: str,
        amount: float,
        currency: str = "USD",
        due_date: Optional[str] = None,
        description: str = "",
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new invoice"""
        try:
            invoice = Invoice(
                id=str(uuid4()),
                opportunity_id=opportunity_id,
                amount=amount,
                currency=currency,
                status="DRAFT",
                due_date=due_date,
                description=description,
                created_by=created_by or "system",
                created_at=datetime.utcnow(),
            )
            db.add(invoice)
            db.commit()

            logger.info(f"Invoice created: {invoice.id}, amount={amount}, opportunity={opportunity_id}")
            return {
                "id": invoice.id,
                "status": "DRAFT",
                "amount": amount,
                "created_at": invoice.created_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to create invoice: {e}", exc_info=True)
            raise ValueError(f"Invoice creation failed: {str(e)}")

    @staticmethod
    def submit_invoice_for_approval(
        db: Session,
        invoice_id: str,
        submitted_by: str
    ) -> Dict[str, Any]:
        """Submit invoice for finance approval"""
        try:
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise ValueError(f"Invoice not found: {invoice_id}")

            if invoice.status != "DRAFT":
                raise ValueError(f"Can only submit DRAFT invoices, current status: {invoice.status}")

            invoice.status = "PENDING_APPROVAL"
            invoice.submitted_at = datetime.utcnow()
            invoice.submitted_by = submitted_by
            db.commit()

            logger.info(f"Invoice submitted for approval: {invoice_id}")
            return {
                "id": invoice.id,
                "status": "PENDING_APPROVAL",
                "submitted_at": invoice.submitted_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to submit invoice: {e}", exc_info=True)
            raise

    @staticmethod
    def approve_invoice(
        db: Session,
        invoice_id: str,
        approved_by: str,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Approve invoice (Finance role required)"""
        try:
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise ValueError(f"Invoice not found: {invoice_id}")

            if invoice.status != "PENDING_APPROVAL":
                raise ValueError(f"Can only approve PENDING_APPROVAL invoices, current status: {invoice.status}")

            invoice.status = "APPROVED"
            invoice.approved_at = datetime.utcnow()
            invoice.approved_by = approved_by
            invoice.approval_notes = notes
            db.commit()

            logger.info(f"Invoice approved: {invoice_id}, approved_by={approved_by}")
            return {
                "id": invoice.id,
                "status": "APPROVED",
                "approved_at": invoice.approved_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to approve invoice: {e}", exc_info=True)
            raise

    @staticmethod
    def bulk_approve_invoices(
        db: Session,
        invoice_ids: List[str],
        approved_by: str
    ) -> Dict[str, Any]:
        """Bulk approve multiple invoices"""
        try:
            approved_count = 0
            failed_count = 0

            for invoice_id in invoice_ids:
                try:
                    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
                    if invoice and invoice.status == "PENDING_APPROVAL":
                        invoice.status = "APPROVED"
                        invoice.approved_at = datetime.utcnow()
                        invoice.approved_by = approved_by
                        approved_count += 1
                except Exception as e:
                   logger.error(f"Error: {str(e)}", exc_info=True)
                    logger.warning(f"Failed to approve invoice {invoice_id}: {e}")
                    failed_count += 1

            db.commit()
            logger.info(f"Bulk invoice approval: {approved_count} approved, {failed_count} failed")

            return {
                "approved": approved_count,
                "failed": failed_count,
                "total": len(invoice_ids)
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Bulk approval failed: {e}", exc_info=True)
            raise

    @staticmethod
    def recognize_revenue(
        db: Session,
        invoice_id: str,
        recognition_type: str = "FULL",  # FULL, PARTIAL, DEFERRED
        amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """Recognize revenue from approved invoice (SLM integration)"""
        try:
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise ValueError(f"Invoice not found: {invoice_id}")

            if invoice.status != "APPROVED":
                raise ValueError(f"Can only recognize revenue from APPROVED invoices")

            recognition_amount = amount or invoice.amount

            revenue = RevenueRecognition(
                id=str(uuid4()),
                invoice_id=invoice_id,
                amount=recognition_amount,
                recognition_type=recognition_type,
                status="RECOGNIZED",
                recognized_at=datetime.utcnow(),
                recognized_by="SLM_SYSTEM"
            )
            db.add(revenue)

            invoice.revenue_recognized = True
            invoice.revenue_recognized_at = datetime.utcnow()
            db.commit()

            logger.info(f"Revenue recognized: invoice={invoice_id}, amount={recognition_amount}")
            return {
                "revenue_id": revenue.id,
                "invoice_id": invoice_id,
                "amount": recognition_amount,
                "status": "RECOGNIZED"
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Revenue recognition failed: {e}", exc_info=True)
            raise
