#!/usr/bin/env python3
"""Assign business unit to Partner test user and create sample data."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.user import Users
from app.models.rbac import BusinessUnit
from app.models.client import Client
from app.models.invoice import Invoice
from datetime import datetime, timedelta
import uuid

def setup_partner_bu():
    """Assign BU to Partner user and create sample invoice data."""

    db = SessionLocal()
    try:
        # Find Partner user
        partner = db.query(Users).filter(Users.UserEmail == "partnertest@blitzenx.com").first()
        if not partner:
            print("[ERROR] Partner user not found: partnertest@blitzenx.com")
            return

        print(f"[OK] Found Partner user: {partner.UserName} (ID: {partner.UserID})")

        # Find or create North America BU
        bu = db.query(BusinessUnit).filter(BusinessUnit.bu_code == "NA").first()
        if not bu:
            print("[INFO] Creating NA Business Unit...")
            bu = BusinessUnit(
                name="North America",
                bu_code="NA",
                tenant_id=1,
                is_active=True,
                continent="North America"
            )
            db.add(bu)
            db.commit()
            db.refresh(bu)

        print(f"[OK] Using BU: {bu.name} (ID: {bu.id})")

        # Assign BU to Partner
        if not partner.business_unit_id:
            partner.business_unit_id = bu.id
            db.add(partner)
            db.commit()
            print(f"[OK] Assigned BU {bu.name} to Partner user")
        else:
            print(f"[OK] Partner already has BU assigned (ID: {partner.business_unit_id})")

        # Create sample client for this BU
        sample_client = db.query(Client).filter(
            Client.business_unit_id == bu.id,
            Client.company_name == "Sample Tech Client"
        ).first()

        if not sample_client:
            print("[INFO] Creating sample client...")
            sample_client = Client(
                company_name="Sample Tech Client",
                business_unit_id=bu.id,
                tenant_id=1
            )
            db.add(sample_client)
            db.commit()
            db.refresh(sample_client)
            print(f"[OK] Created sample client (ID: {sample_client.id})")
        else:
            print(f"[OK] Sample client already exists (ID: {sample_client.id})")

        # Create sample invoices for this month
        today = datetime.utcnow()
        period_start = today.replace(day=1)

        # Check if invoice already exists
        existing_invoice = db.query(Invoice).filter(
            Invoice.business_unit_id == bu.id,
            Invoice.created_at >= period_start
        ).first()

        if not existing_invoice:
            print("[INFO] Creating sample invoice...")
            invoice = Invoice(
                invoice_id=str(uuid.uuid4()),
                business_unit_id=bu.id,
                client_id=sample_client.id if sample_client else None,
                total_amount_usd_cents=50000000,  # $500,000
                status="APPROVED",
                created_at=today,
                tenant_id=1,
                billable_hours=160
            )
            db.add(invoice)
            db.commit()
            print(f"[OK] Created sample invoice with $500,000 revenue")
        else:
            print("[OK] Invoice already exists for this month")

        print("\n[SUCCESS] Partner BU setup complete!")
        print(f"  - Partner: {partner.UserName}")
        print(f"  - BU: {bu.name}")
        print(f"  - Sample Revenue: $500,000")

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    setup_partner_bu()
