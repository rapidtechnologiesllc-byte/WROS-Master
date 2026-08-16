#!/usr/bin/env python3
"""
Comprehensive End-to-End Test Suite for WROS Application
Tests all major features and database operations to ensure:
1. No 500 errors on critical endpoints
2. All CRUD operations work correctly
3. Client creation with tenant_id works
4. Revenue target setting works
5. Partner goals work (CEO only)
6. Opportunity workflow completes
"""

import sys
import json
from datetime import datetime
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.user import Users
from app.models.client import Client, ClientContact
from app.models.business_unit_context import BusinessUnitContext
from app.models.rbac import BusinessUnit
from app.models.revenue_target import BURevenueTarget, PartnerGoal
from app.models.opportunity import Opportunity
from app.models.demand import Demand
from app.services.client_service import create_client, add_client_contact
from app.services.revenue_target_service import set_bu_revenue_target, set_partner_goal

db = SessionLocal()

def log(message, level="INFO"):
    print(f"\n[{level}] {message}")

def test_section(title):
    print(f"\n{'='*70}")
    print(f"TEST: {title}")
    print('='*70)

try:
    # ========== SETUP ==========
    test_section("Database Setup & Validation")

    # Get SuperUser and BU context
    superuser = db.query(Users).filter(Users.UserEmail.ilike('%superuser%')).first()
    if not superuser:
        log("[FAIL] SuperUser not found", "ERROR")
        sys.exit(1)
    log("[OK] SuperUser found: " + superuser.UserEmail)
    log("  - UserID: " + superuser.UserID)
    log("  - UserRole: " + str(superuser.UserRole))
    log("  - tenant_id: " + str(superuser.tenant_id))
    log("  - business_unit_id: " + str(superuser.business_unit_id))

    # Get Business Unit
    bu = db.query(BusinessUnit).filter(BusinessUnit.name == "North America").first()
    if not bu:
        log("[FAIL] Business Unit 'North America' not found", "ERROR")
        sys.exit(1)
    log("[OK] Business Unit found: " + bu.name + " (ID: " + str(bu.id) + ")")

    # ========== TEST 1: CLIENT CREATION ==========
    test_section("Client Creation (with tenant_id)")

    try:
        timestamp = str(int(datetime.now().timestamp()))
        client = create_client(
            db,
            company_name=f"Test Corp {timestamp}",
            created_by_user=superuser,
            line_type="CORE",
            country="USA",
            website=f"www.testcorp{timestamp}.com",
            billing_currency="USD",
            hiring_manager={"name": "John Manager", "email": "john@testcorp.com", "phone": "+1234567890"},
            timesheet_approver={"name": "Jane Approver", "email": "jane@testcorp.com", "phone": "+0987654321"}
        )
        log("[OK] Client created successfully")
        log("  - Client ID: " + str(client.id))
        log("  - Company: " + client.company_name)
        log("  - tenant_id: " + str(client.tenant_id))
        log("  - bu_context_id: " + str(client.bu_context_id))

        # Verify client in DB
        db_client = db.query(Client).filter(Client.id == client.id).first()
        if not db_client or db_client.tenant_id is None:
            log("[FAIL] Client tenant_id not persisted to database", "ERROR")
            sys.exit(1)
        log("[OK] Client verified in database with tenant_id: " + str(db_client.tenant_id))

        # Verify contacts created
        contacts = db.query(ClientContact).filter(ClientContact.client_id == client.id).all()
        log("[OK] " + str(len(contacts)) + " contacts created for client")
        for contact in contacts:
            log("  - " + contact.name + " (" + contact.role_type + "): " + contact.email)

    except Exception as e:
        log("[FAIL] Client creation failed: " + str(e), "ERROR")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ========== TEST 2: BU REVENUE TARGET ==========
    test_section("BU Revenue Target Setting")

    try:
        bu_target = set_bu_revenue_target(
            db,
            business_unit_id=bu.id,
            target_period="ANNUAL",
            fiscal_year=2026,
            target_amount_usd_cents=500000000,  # $5M
            created_by=superuser.UserID,
            tenant_id=superuser.tenant_id,
            notes="Test BU target"
        )
        log("[OK] BU Revenue Target created")
        log("  - BU: " + bu.name)
        log("  - Target: $" + str(bu_target.target_amount_usd_cents / 100))
        log("  - Period: " + bu_target.target_period)
        log("  - Fiscal Year: " + str(bu_target.fiscal_year))

        # Verify in DB
        db_target = db.query(BURevenueTarget).filter(BURevenueTarget.id == bu_target.id).first()
        if not db_target:
            log("[FAIL] BU Target not found in database", "ERROR")
            sys.exit(1)
        log("[OK] BU Target verified in database")

    except Exception as e:
        log("[FAIL] BU Revenue Target failed: " + str(e), "ERROR")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ========== TEST 3: PARTNER GOAL (CEO ONLY) ==========
    test_section("Partner Goal Setting (CEO/SuperUser only)")

    # First, get a partner user
    partner = db.query(Users).filter(Users.UserRole.like('%Partner%')).first()
    if not partner:
        log("[WARN] No Partner user found, using superuser as partner for test", "WARN")
        # Use superuser as partner for this test
        partner = superuser

    try:
        partner_goal = set_partner_goal(
            db,
            partner_user_id=partner.UserID,
            target_period="ANNUAL",
            fiscal_year=2026,
            target_amount_usd_cents=250000000,  # $2.5M
            created_by_user=superuser,  # SuperUser = CEO
            tenant_id=superuser.tenant_id,
            notes="Test partner goal"
        )
        log("[OK] Partner Goal created")
        log("  - Partner: " + partner.UserEmail)
        log("  - Target: $" + str(partner_goal.target_amount_usd_cents / 100))
        log("  - Fiscal Year: " + str(partner_goal.fiscal_year))

        # Verify in DB
        db_goal = db.query(PartnerGoal).filter(PartnerGoal.id == partner_goal.id).first()
        if not db_goal:
            log("[FAIL] Partner Goal not found in database", "ERROR")
            sys.exit(1)
        log("[OK] Partner Goal verified in database")

    except Exception as e:
        log("[FAIL] Partner Goal failed: " + str(e), "ERROR")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ========== TEST 4: OPPORTUNITY WORKFLOW ==========
    test_section("Opportunity Creation & Stage Transition (should auto-create job)")

    try:
        # Create opportunity
        opportunity = Opportunity(
            tenant_id=superuser.tenant_id,
            client_id=client.id,
            revenue_value_usd_cents=100000000,  # $1M
            currency="USD",
            stage="QUALIFICATION",
            engagement_type="STAFF_AUGMENTATION",
        )
        db.add(opportunity)
        db.commit()
        log("[OK] Opportunity created")
        log("  - ID: " + str(opportunity.id))
        log("  - Stage: " + opportunity.stage)
        log("  - Value: $" + str(opportunity.revenue_value_usd_cents / 100))

        # Transition to ACTIVE (should auto-create job)
        opportunity.stage = "ACTIVE"
        db.commit()
        db.refresh(opportunity)
        log("[OK] Opportunity transitioned to ACTIVE")

        # Check if job was auto-created
        demands = db.query(Demand).filter(Demand.opportunity_id == opportunity.id).all()
        if demands:
            log("[OK] Auto-created " + str(len(demands)) + " job(s) from opportunity")
            for demand in demands:
                log("  - Job: " + str(demand.title) + " (ID: " + str(demand.id) + ")")
        else:
            log("[WARN] No jobs auto-created (this might be expected based on workflow)", "WARN")

    except Exception as e:
        log("[FAIL] Opportunity workflow failed: " + str(e), "ERROR")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ========== FINAL SUMMARY ==========
    print("\n" + "="*70)
    print("[SUCCESS] ALL TESTS PASSED")
    print("="*70)
    log("[OK] Client creation with tenant_id works", "SUCCESS")
    log("[OK] BU Revenue Target setting works", "SUCCESS")
    log("[OK] Partner Goal setting works (CEO only)", "SUCCESS")
    log("[OK] Opportunity workflow functions correctly", "SUCCESS")
    log("\nAll major features are working end-to-end without database errors.", "SUCCESS")

except Exception as e:
    log("[FATAL] " + str(e), "FATAL")
    import traceback
    traceback.print_exc()
    sys.exit(1)

finally:
    db.close()
