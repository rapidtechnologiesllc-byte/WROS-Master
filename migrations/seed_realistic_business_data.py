"""Seed realistic business data for scenario testing."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.candidate import Candidate
from app.models.user import Jobs, Interview
from app.models.offer_letter import OfferLetter
from app.models.employee import Employee
from app.models.opportunity import Opportunity
from app.models.agent_state_target import (
    AgentStateTarget, AgentActualPerformance, AgentFearScore, AgentIssue, AgentImprovement
)
from datetime import datetime, timedelta, date
import uuid
import random

def random_email(first, last):
    return f"{first.lower()}.{last.lower()}@blitzenx.com"

def seed_business_data():
    """Seed 59 candidates, 10 jobs, 6 opportunities, 4 onboarding, 50 employees."""

    db = SessionLocal()

    try:
        # Clear previous data
        db.query(Candidate).delete()
        db.query(Jobs).delete()
        db.query(Opportunity).delete()
        db.query(Employee).delete()
        db.query(Interview).delete()
        db.query(OfferLetter).delete()
        db.commit()

        print("[SCENARIO] Creating realistic business data...")

        # ============================================================
        # JOBS (10 open requisitions)
        # ============================================================
        print("\n[1] Creating 10 jobs...")
        jobs = []
        job_titles = [
            "Senior Guidewire Developer",
            "Guidewire InsuranceSuite Architect",
            "QA Automation Engineer",
            "Business Analyst - Insurance",
            "Guidewire Admin/Config Specialist",
            "Java Developer (Core Platform)",
            "Solutions Architect",
            "Performance Engineer",
            "DevOps Engineer",
            "Data Engineer - Analytics"
        ]

        for i, title in enumerate(job_titles):
            job = Jobs(
                jobID=f"job_{i+1:03d}",
                jobTitle=title,
                jobDescription=f"Role: {title}. Seeking experienced professional.",
                jobSkills="Python,SQL,Guidewire",
                jobExperience="5+ years",
                jobLocation="Remote",
                jobStatus="OPEN",
                jobCreatedAt=datetime.utcnow(),
                noOfPositions=random.randint(1, 3),
            )
            db.add(job)
            jobs.append(job)

        db.commit()
        print(f"  [OK] Created {len(jobs)} jobs")

        # ============================================================
        # CANDIDATES (59 in various pipeline stages)
        # ============================================================
        print("\n[2] Creating 59 candidates in pipeline...")
        candidates = []
        candidate_names = [
            ("Aditya", "Kumar"), ("Priya", "Singh"), ("Rahul", "Patel"), ("Neha", "Gupta"),
            ("Vikram", "Sharma"), ("Anjali", "Rao"), ("Arjun", "Verma"), ("Divya", "Nair"),
            ("Rohan", "Das"), ("Sneha", "Desai"), ("Karan", "Iyer"), ("Pooja", "Menon"),
            ("Sanjay", "Bhat"), ("Isha", "Pillai"), ("Nitin", "Reddy"), ("Richa", "Saxena"),
            ("Amit", "Joshi"), ("Priyanka", "Sharma"), ("Naveen", "Kumar"), ("Shreya", "Bose"),
            ("Harsh", "Malik"), ("Ananya", "Yadav"), ("Deepak", "Singh"), ("Megha", "Kapoor"),
            ("Aryan", "Tiwari"), ("Pooja", "Mishra"), ("Siddharth", "Kulkarni"), ("Diya", "Chatterjee"),
            ("Varun", "Agarwal"), ("Meera", "Pandey"), ("Rajesh", "Nair"), ("Kavya", "Sinha"),
            ("Nikhil", "Srivastava"), ("Ananya", "Verma"), ("Ravi", "Shankar"), ("Priya", "Malhotra"),
            ("Akshay", "Chopra"), ("Nikita", "Bansal"), ("Saurav", "Desai"), ("Sakshi", "Garg"),
            ("Kunal", "Saxena"), ("Aarav", "Sharma"), ("Anya", "Kapoor"), ("Bhavesh", "Joshi"),
            ("Chitra", "Nair"), ("Dhruv", "Rao"), ("Eshita", "Trivedi"), ("Faisal", "Khan"),
            ("Garima", "Pathak"), ("Harsh", "Saxena"), ("Ishangi", "Bhat"), ("Jayesh", "Desai"),
            ("Kavyaa", "Malhotra"), ("Lavanya", "Sharma"), ("Manish", "Patel"), ("Neelam", "Singh"),
            ("Omkar", "Gupta"), ("Pallavi", "Nair"), ("Qasim", "Ahmed"), ("Riya", "Pandey"),
        ]

        statuses = ["QUALIFIED", "SCREENED", "INTERVIEWED", "OFFER", "HIRED"]
        status_weights = [25, 20, 15, 10, 5]  # Most are early stage

        for i, (first, last) in enumerate(candidate_names):
            status = random.choices(statuses, weights=status_weights)[0]

            candidate = Candidate(
                candidateID=f"cand_{i+1:03d}",
                candidateEmail=random_email(first, last),
                candidateFirstName=first,
                candidateLastName=last,
                candidateRole="Candidate",
                candidateJobTitle=random.choice(job_titles),
                status=status,
                candidateCreatedAt=datetime.utcnow() - timedelta(days=random.randint(1, 60)),
                tenant_id="blitzenx",
            )
            db.add(candidate)
            candidates.append(candidate)

        db.commit()
        print(f"  [OK] Created {len(candidates)} candidates")

        # Count by stage
        for status in statuses:
            count = sum(1 for c in candidates if c.status == status)
            print(f"      - {status}: {count}")

        # ============================================================
        # OPPORTUNITIES (6 active client deals)
        # ============================================================
        print("\n[3] Creating 6 opportunities...")
        opportunities = []
        opp_names = [
            "Acme Insurance - Guidewire Implementation",
            "GlobalBank - Policy Admin System",
            "SafeInsure - Claims Processing",
            "MetroLife - Digital Transformation",
            "PremiumCare - Underwriting Automation",
            "CityRisk - Core System Migration"
        ]
        opp_values = [800_000, 1_200_000, 650_000, 950_000, 750_000, 1_100_000]

        for i, (name, value) in enumerate(zip(opp_names, opp_values)):
            opp = Opportunity(
                opportunityID=f"opp_{i+1:03d}",
                opportunityName=name,
                accountName=name.split(" - ")[0],
                estimatedValue=value,
                currency="USD",
                status="ACTIVE",
                createdAt=datetime.utcnow() - timedelta(days=random.randint(10, 90)),
                probability=random.choice([0.25, 0.5, 0.75, 1.0]),  # Sales probability
                expectedCloseDate=datetime.utcnow() + timedelta(days=random.randint(30, 180)),
                tenant_id="blitzenx",
            )
            db.add(opp)
            opportunities.append(opp)

        db.commit()
        print(f"  [OK] Created {len(opportunities)} opportunities")
        print(f"      Total pipeline value: ${sum(opp_values):,}")

        # ============================================================
        # EMPLOYEES (50 active workforce)
        # ============================================================
        print("\n[4] Creating 50 employees...")
        employees = []
        employee_names = [
            ("Avinash", "Mukund"), ("Sarah", "Johnson"), ("Michael", "Chen"), ("Emma", "Williams"),
            ("James", "Brown"), ("Lisa", "Anderson"), ("David", "Martinez"), ("Jennifer", "Taylor"),
            ("Robert", "Thomas"), ("Maria", "Garcia"), ("William", "Rodriguez"), ("Patricia", "Lee"),
            ("Richard", "White"), ("Linda", "Harris"), ("Joseph", "Martin"), ("Barbara", "Clark"),
            ("Thomas", "Lewis"), ("Nancy", "Robinson"), ("Charles", "Young"), ("Karen", "Hernandez"),
            ("Christopher", "King"), ("Betty", "Wright"), ("Daniel", "Lopez"), ("Margaret", "Hill"),
            ("Matthew", "Scott"), ("Sandra", "Green"), ("Anthony", "Adams"), ("Dorothy", "Nelson"),
            ("Mark", "Carter"), ("Carol", "Roberts"), ("Donald", "Phillips"), ("Ruth", "Campbell"),
            ("Steven", "Parker"), ("Katherine", "Evans"), ("Paul", "Edwards"), ("Diane", "Collins"),
            ("Andrew", "Reeves"), ("Julie", "Morris"), ("Joshua", "Murphy"), ("Joyce", "Cook"),
            ("Kenneth", "Morgan"), ("Evelyn", "Peterson"), ("Kevin", "Gray"), ("Anna", "Ramirez"),
            ("Brian", "James"), ("Judith", "Watson"), ("Edward", "Brooks"), ("Cheryl", "Chavez"),
            ("Ronald", "Bennett"), ("Mildred", "Fuller"),
        ]

        employee_statuses = ["ACTIVE", "ONBOARDING", "TRAINING", "BENCH"]
        status_weights_emp = [70, 10, 10, 10]

        onboarding_count = 0
        for i, (first, last) in enumerate(employee_names):
            status = random.choices(employee_statuses, weights=status_weights_emp)[0]
            if status == "ONBOARDING":
                onboarding_count += 1

            employee = Employee(
                id=f"emp_{i+1:03d}",
                email=random_email(first, last),
                first_name=first,
                last_name=last,
                status=status,
                hire_date=datetime.utcnow() - timedelta(days=random.randint(30, 1000)),
                cost_usd_cents=int(random.uniform(60_000, 200_000) * 100),
                tenant_id="blitzenx",
                business_unit="AXION",
            )
            db.add(employee)
            employees.append(employee)

        db.commit()
        print(f"  [OK] Created {len(employees)} employees")
        print(f"      - ACTIVE: {sum(1 for e in employees if e.status == 'ACTIVE')}")
        print(f"      - ONBOARDING: {sum(1 for e in employees if e.status == 'ONBOARDING')}")
        print(f"      - TRAINING: {sum(1 for e in employees if e.status == 'TRAINING')}")
        print(f"      - BENCH: {sum(1 for e in employees if e.status == 'BENCH')}")

        # ============================================================
        # INTERVIEWS (scheduled and completed)
        # ============================================================
        print("\n[5] Creating interviews...")
        interviewed_candidates = [c for c in candidates if c.status in ["INTERVIEWED", "OFFER", "HIRED"]]

        for candidate in interviewed_candidates[:15]:  # Sample of interviewed candidates
            interview = Interview(
                interviewID=f"int_{uuid.uuid4().hex[:8]}",
                candidateID=candidate.candidateID,
                interviewRound=1,
                interviewDate=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                interviewerName=f"interviewer{random.randint(1, 5)}@blitzenx.com",
                status="COMPLETED",
                feedback="Strong candidate, good fit",
                rating=random.choice([3, 4, 5]),  # Out of 5
                tenant_id="blitzenx",
            )
            db.add(interview)

        db.commit()
        print(f"  [OK] Created interviews for {len(interviewed_candidates[:15])} candidates")

        # ============================================================
        # OFFERS (for qualified candidates)
        # ============================================================
        print("\n[6] Creating offer letters...")
        offer_candidates = [c for c in candidates if c.status in ["OFFER", "HIRED"]]

        for candidate in offer_candidates:
            offer = OfferLetter(
                offerID=f"off_{uuid.uuid4().hex[:8]}",
                candidateID=candidate.candidateID,
                jobID=random.choice(jobs).jobID,
                offerDate=datetime.utcnow() - timedelta(days=random.randint(1, 15)),
                startDate=datetime.utcnow() + timedelta(days=random.randint(1, 30)),
                salary=int(random.uniform(80_000, 200_000) * 100),
                status="ACCEPTED" if candidate.status == "HIRED" else "PENDING",
                tenant_id="blitzenx",
            )
            db.add(offer)

        db.commit()
        print(f"  [OK] Created offers for {len(offer_candidates)} candidates")

        # ============================================================
        # UPDATE AGENT STATES BASED ON BUSINESS REALITY
        # ============================================================
        print("\n[7] Updating Agent State based on business metrics...")

        # Clear old agent state
        db.query(AgentImprovement).delete()
        db.query(AgentIssue).delete()
        db.query(AgentFearScore).delete()
        db.query(AgentActualPerformance).delete()
        db.query(AgentStateTarget).delete()
        db.commit()

        # THUNDER AGENT
        hired_count = sum(1 for c in candidates if c.status == "HIRED")
        qualified_count = sum(1 for c in candidates if c.status in ["QUALIFIED", "SCREENED", "INTERVIEWED", "OFFER", "HIRED"])

        thunder_fy_progress = (hired_count / 250) * 100
        thunder_2030_progress = (hired_count / 2000) * 100
        thunder_gap_fy = 250 - hired_count
        thunder_gap_2030 = 2000 - hired_count

        # Fear calculation
        gap_fy_pct = (thunder_gap_fy / 250) * 100
        gap_2030_pct = (thunder_gap_2030 / 2000) * 100
        max_gap_pct = max(gap_fy_pct, gap_2030_pct)
        thunder_fear = 20 + (max_gap_pct * 0.8)

        thunder = AgentStateTarget(
            id=str(uuid.uuid4()),
            agent_name="Thunder",
            agent_domain="recruitment",
            agent_tier="tier_1_core",
            contributes_to_revenue=False,
            contributes_to_headcount=True,
            strategic_importance="CRITICAL",
            how_helps_grow="AI recruiter: sources candidates → screens → interviews → offers → hires → feeds 2000 employee target",
            target_2030_value=2000,
            target_2030_unit="employees",
            fy_year=2026,
            fy_target_value=250,
            fy_target_unit="employees",
            acceleration_multiplier_for_fy=(250 / max(hired_count, 1)) if hired_count > 0 else 999,
            acceleration_multiplier_for_2030=(2000 / max(hired_count, 1)) if hired_count > 0 else 999,
            status="OPERATIONAL",
            enabled=True,
        )
        db.add(thunder)

        # Thunder performance
        thunder_perf = AgentActualPerformance(
            id=str(uuid.uuid4()),
            agent_name="Thunder",
            date="2026-08-09",
            actual_value=float(hired_count),
            actual_unit="employees",
            success_rate=random.uniform(92, 98),
            executions_count=qualified_count * 3,  # 3 touches per candidate
            avg_execution_time_ms=1200,
            error_count=int(qualified_count * 0.05),
            quality_score=85 + random.randint(0, 10),
            progress_to_fy_pct=thunder_fy_progress,
            progress_to_2030_pct=thunder_2030_progress,
        )
        db.add(thunder_perf)

        # Thunder fear
        thunder_fear_record = AgentFearScore(
            id=str(uuid.uuid4()),
            agent_name="Thunder",
            date="2026-08-09",
            fear_score=min(100, thunder_fear),
            base_fear=20.0,
            gap_from_fy_target=gap_fy_pct,
            gap_from_2030_target=gap_2030_pct,
            stress_level="motivated" if thunder_fear < 20 else
                         "neutral" if thunder_fear < 40 else
                         "concerned" if thunder_fear < 60 else
                         "desperate" if thunder_fear < 80 else "terrified",
            threat_level="none" if thunder_fear < 50 else
                         "warning" if thunder_fear < 70 else
                         "critical" if thunder_fear < 80 else "existential",
            is_kill_switch_candidate=thunder_fear > 85 and max_gap_pct > 50,
        )
        db.add(thunder_fear_record)

        # RESOURCE MANAGEMENT AGENT
        active_employees = sum(1 for e in employees if e.status == "ACTIVE")
        bench_employees = sum(1 for e in employees if e.status == "BENCH")
        utilization = (active_employees / max(len(employees), 1)) * 100

        resource_mgmt = AgentStateTarget(
            id=str(uuid.uuid4()),
            agent_name="Resource Management Agent",
            agent_domain="resource_management",
            agent_tier="tier_2_resource",
            contributes_to_revenue=True,
            contributes_to_headcount=True,
            strategic_importance="CRITICAL",
            how_helps_grow="Assigns employees to projects → drives 80% utilization → generates revenue",
            target_2030_value=80,
            target_2030_unit="%_utilization",
            fy_year=2026,
            fy_target_value=75,
            fy_target_unit="%_utilization",
            acceleration_multiplier_for_fy=75/max(utilization, 1),
            acceleration_multiplier_for_2030=80/max(utilization, 1),
            status="OPERATIONAL",
            enabled=True,
        )
        db.add(resource_mgmt)

        util_gap_fy = 75 - utilization
        util_gap_2030 = 80 - utilization
        max_util_gap = max(util_gap_fy, util_gap_2030)
        resource_fear = 20 + (max(max_util_gap, 0) * 0.8)

        resource_perf = AgentActualPerformance(
            id=str(uuid.uuid4()),
            agent_name="Resource Management Agent",
            date="2026-08-09",
            actual_value=utilization,
            actual_unit="%_utilization",
            success_rate=min(100, 90 + (utilization - 50) * 0.2),
            executions_count=len(employees),
            avg_execution_time_ms=850,
            error_count=int(len(employees) * 0.05),
            quality_score=80 + (utilization - 50) * 0.2,
            progress_to_fy_pct=(utilization / 75) * 100,
            progress_to_2030_pct=(utilization / 80) * 100,
        )
        db.add(resource_perf)

        resource_fear_record = AgentFearScore(
            id=str(uuid.uuid4()),
            agent_name="Resource Management Agent",
            date="2026-08-09",
            fear_score=min(100, resource_fear),
            base_fear=20.0,
            gap_from_fy_target=util_gap_fy,
            gap_from_2030_target=util_gap_2030,
            stress_level="motivated" if resource_fear < 20 else
                         "neutral" if resource_fear < 40 else
                         "concerned" if resource_fear < 60 else
                         "desperate" if resource_fear < 80 else "terrified",
            threat_level="none" if resource_fear < 50 else
                         "warning" if resource_fear < 70 else
                         "critical" if resource_fear < 80 else "existential",
            is_kill_switch_candidate=False,
        )
        db.add(resource_fear_record)

        # OPPORTUNITY TRACKER AGENT (Finance)
        total_pipeline = sum(opp.estimatedValue or 0 for opp in opportunities)
        pipeline_progress = (total_pipeline / 100_000_000) * 100

        opportunity = AgentStateTarget(
            id=str(uuid.uuid4()),
            agent_name="Opportunity Tracker Agent",
            agent_domain="finance",
            agent_tier="tier_3_finance",
            contributes_to_revenue=True,
            contributes_to_headcount=False,
            strategic_importance="HIGH",
            how_helps_grow="Tracks sales pipeline → forecasts revenue → feeds $100M revenue target",
            target_2030_value=100_000_000,
            target_2030_unit="USD_revenue",
            fy_year=2026,
            fy_target_value=15_000_000,
            fy_target_unit="USD_revenue",
            acceleration_multiplier_for_fy=(15_000_000 / max(total_pipeline, 1)) if total_pipeline > 0 else 999,
            acceleration_multiplier_for_2030=(100_000_000 / max(total_pipeline, 1)) if total_pipeline > 0 else 999,
            status="OPERATIONAL",
            enabled=True,
        )
        db.add(opportunity)

        opp_fear = 20 + ((100 - pipeline_progress) * 0.8) if pipeline_progress < 100 else 20

        opp_perf = AgentActualPerformance(
            id=str(uuid.uuid4()),
            agent_name="Opportunity Tracker Agent",
            date="2026-08-09",
            actual_value=float(total_pipeline),
            actual_unit="USD_revenue",
            success_rate=93.0,
            executions_count=len(opportunities),
            avg_execution_time_ms=650,
            error_count=0,
            quality_score=91,
            progress_to_fy_pct=min(100, (total_pipeline / 15_000_000) * 100),
            progress_to_2030_pct=pipeline_progress,
        )
        db.add(opp_perf)

        opp_fear_record = AgentFearScore(
            id=str(uuid.uuid4()),
            agent_name="Opportunity Tracker Agent",
            date="2026-08-09",
            fear_score=min(100, opp_fear),
            base_fear=20.0,
            gap_from_fy_target=(15_000_000 - total_pipeline) / 15_000_000 * 100 if total_pipeline < 15_000_000 else 0,
            gap_from_2030_target=(100_000_000 - total_pipeline) / 100_000_000 * 100 if total_pipeline < 100_000_000 else 0,
            stress_level="motivated" if opp_fear < 20 else
                         "neutral" if opp_fear < 40 else
                         "concerned" if opp_fear < 60 else
                         "desperate" if opp_fear < 80 else "terrified",
            threat_level="none" if opp_fear < 50 else
                         "warning" if opp_fear < 70 else
                         "critical" if opp_fear < 80 else "existential",
            is_kill_switch_candidate=False,
        )
        db.add(opp_fear_record)

        db.commit()

        print(f"  [OK] Updated agent states based on business reality:")
        print(f"      - Thunder: Hired {hired_count} (Fear {thunder_fear:.0f}/100)")
        print(f"      - Resource Mgmt: {utilization:.1f}% utilization (Fear {resource_fear:.0f}/100)")
        print(f"      - Opportunity Tracker: ${total_pipeline:,} pipeline (Fear {opp_fear:.0f}/100)")

        print("\n" + "="*70)
        print("[SUCCESS] Realistic business data seeded!")
        print("="*70)
        print(f"\nBUSINESS SNAPSHOT:")
        print(f"  Candidates: {len(candidates)} (qualified: {qualified_count}, hired: {hired_count})")
        print(f"  Jobs Open: {len(jobs)}")
        print(f"  Opportunities: {len(opportunities)} (pipeline: ${total_pipeline:,})")
        print(f"  Employees: {len(employees)} (active: {active_employees}, bench: {bench_employees})")
        print(f"  Utilization: {utilization:.1f}%")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_business_data()
