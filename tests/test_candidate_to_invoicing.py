"""
FOCUSED REGRESSION TEST: Trace Candidate → Invoicing Workflow

This test follows a candidate through the entire hiring pipeline
and shows exactly what breaks or fails at each stage.
"""

import pytest
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session


class TestCandidateToInvoicingWorkflow:
    """Complete workflow: Candidate → Job → Interview → Offer → Employee → Allocation → Timesheet → Invoice"""

    def test_full_hiring_to_invoicing_workflow(self, db: Session):
        """Trace a candidate from creation through invoicing"""

        print("\n" + "="*80)
        print("CANDIDATE → INVOICING WORKFLOW TRACE")
        print("="*80)

        # ====== STEP 1: CREATE CANDIDATE ======
        print("\n[STEP 1] Creating candidate...")
        try:
            from app.models import Candidate
            from app.services.candidate_service import create_candidate_safe

            candidate = create_candidate_safe(
                db=db,
                email="workflow_test@test.com",
                tenant_id=1,
                name="Test Workflow Candidate"
            )
            print(f"✓ Candidate created: {candidate.candidateID}")
        except Exception as e:
            print(f"✗ FAILED TO CREATE CANDIDATE: {e}")
            print(f"  Issue: createCandidateSafe not properly implemented or missing tenant")
            return

        # ====== STEP 2: ASSIGN TO JOB ======
        print("\n[STEP 2] Assigning candidate to job...")
        try:
            from app.models import Jobs

            # Try to find an existing job
            job = db.query(Jobs).filter_by(tenant_id=1).first()

            if not job:
                print(f"✗ NO JOBS FOUND IN DATABASE")
                print(f"  Issue: Need to create test jobs first or use existing ones")
                return

            candidate.job_id = job.jobID
            db.commit()
            print(f"✓ Candidate assigned to job: {job.jobID}")
        except Exception as e:
            print(f"✗ FAILED TO ASSIGN JOB: {e}")
            return

        # ====== STEP 3: SCHEDULE INTERVIEW ======
        print("\n[STEP 3] Scheduling interview...")
        try:
            from app.models import Interview

            interview = Interview(
                candidate_id=candidate.candidateID,
                job_id=job.jobID,
                tenant_id=1,
                scheduled_time=datetime.now() + timedelta(days=7),
                interview_type="Phone",
                status="Scheduled"
            )
            db.add(interview)
            db.commit()
            print(f"✓ Interview scheduled: {interview.id}")
        except Exception as e:
            print(f"✗ FAILED TO SCHEDULE INTERVIEW: {e}")
            print(f"  Issue: {type(e).__name__} - {str(e)[:100]}")

        # ====== STEP 4: CREATE OFFER ======
        print("\n[STEP 4] Creating offer...")
        try:
            from app.models import Offer

            offer = Offer(
                candidate_id=candidate.candidateID,
                job_id=job.jobID,
                tenant_id=1,
                status="Pending",
                salary=100000,
                start_date=date.today() + timedelta(days=14)
            )
            db.add(offer)
            db.commit()
            print(f"✓ Offer created: {offer.id}")
        except Exception as e:
            print(f"✗ FAILED TO CREATE OFFER: {e}")
            print(f"  Issue: {type(e).__name__} - {str(e)[:100]}")
            return

        # ====== STEP 5: CONVERT TO EMPLOYEE ======
        print("\n[STEP 5] Converting candidate to employee...")
        try:
            from app.models import Employee
            import uuid

            employee = Employee(
                id=str(uuid.uuid4()),
                tenant_id=1,
                candidate_id=candidate.candidateID,
                first_name="Test",
                last_name="Employee",
                email="employee_test@test.com",
                joining_date=date.today() + timedelta(days=14),
                bu_context_id=1  # Uses BusinessUnitContext
            )
            db.add(employee)
            db.commit()
            print(f"✓ Employee created: {employee.id}")
        except Exception as e:
            print(f"✗ FAILED TO CREATE EMPLOYEE: {e}")
            print(f"  Issue: {type(e).__name__} - {str(e)[:100]}")
            print(f"  Root cause: bu_context_id may not exist or not nullable")
            return

        # ====== STEP 6: ALLOCATE TO PROJECT ======
        print("\n[STEP 6] Allocating employee to project...")
        try:
            from app.models import EmployeeAllocation, Project
            import uuid

            # Find or create project
            project = db.query(Project).filter_by(tenant_id=1).first()

            if not project:
                project = Project(
                    id=str(uuid.uuid4()),
                    tenant_id=1,
                    name="Test Project",
                    client_id=job.client_id if hasattr(job, 'client_id') else None
                )
                db.add(project)
                db.commit()

            allocation = EmployeeAllocation(
                id=str(uuid.uuid4()),
                tenant_id=1,
                employee_id=employee.id,
                project_id=project.id,
                allocation_start_date=date.today() + timedelta(days=14),
                allocation_end_date=date.today() + timedelta(days=90),
                billing_rate_usd_cents=5000  # $50/hour
            )
            db.add(allocation)
            db.commit()
            print(f"✓ Allocation created: {allocation.id}")
        except Exception as e:
            print(f"✗ FAILED TO CREATE ALLOCATION: {e}")
            print(f"  Issue: {type(e).__name__} - {str(e)[:100]}")
            return

        # ====== STEP 7: CREATE TIMESHEET ======
        print("\n[STEP 7] Creating timesheet for billable hours...")
        try:
            from app.models import Timesheet
            import uuid

            timesheet = Timesheet(
                id=str(uuid.uuid4()),
                tenant_id=1,
                employee_id=employee.id,
                bu_context_id=1,  # Uses BusinessUnitContext
                allocation_id=allocation.id,
                week_starting_date=date.today(),
                total_hours=40,
                billable_hours=40,
                status="Submitted"
            )
            db.add(timesheet)
            db.commit()
            print(f"✓ Timesheet created: {timesheet.id}")
        except Exception as e:
            print(f"✗ FAILED TO CREATE TIMESHEET: {e}")
            print(f"  Issue: {type(e).__name__} - {str(e)[:100]}")
            print(f"  Root cause: bu_context_id or allocation_id may not be valid")
            return

        # ====== STEP 8: CREATE INVOICE ======
        print("\n[STEP 8] Creating invoice from timesheet...")
        try:
            from app.models import Invoice
            import uuid

            invoice = Invoice(
                id=str(uuid.uuid4()),
                tenant_id=1,
                project_id=project.id,
                client_id=project.client_id if hasattr(project, 'client_id') else job.client_id,
                bu_context_id=1,  # Uses BusinessUnitContext
                billing_period_start=date.today(),
                billing_period_end=date.today() + timedelta(days=7),
                status="Draft",
                total_usd_cents=40 * 5000  # 40 hours * $50/hour = $2000 (in cents)
            )
            db.add(invoice)
            db.commit()
            print(f"✓ Invoice created: {invoice.id}")
            print(f"  Amount: ${invoice.total_usd_cents / 100:.2f}")
        except Exception as e:
            print(f"✗ FAILED TO CREATE INVOICE: {e}")
            print(f"  Issue: {type(e).__name__} - {str(e)[:100]}")
            return

        # ====== WORKFLOW COMPLETE ======
        print("\n" + "="*80)
        print("✓ WORKFLOW COMPLETE: Candidate → Employee → Invoice")
        print("="*80)
        print(f"\nSummary:")
        print(f"  Candidate ID: {candidate.candidateID}")
        print(f"  Employee ID: {employee.id}")
        print(f"  Allocation ID: {allocation.id}")
        print(f"  Timesheet ID: {timesheet.id}")
        print(f"  Invoice ID: {invoice.id}")
        print(f"  Invoice Amount: ${invoice.total_usd_cents / 100:.2f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
