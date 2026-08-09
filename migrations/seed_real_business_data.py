"""Seed realistic business data - Candidates, employees, opportunities, agent events."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.candidate import Candidate
from app.models.user import Jobs
from app.models.employee import Employee
from app.models.opportunity import Opportunity
from app.services.agent_event_service import AgentEvent, AgentEventService
from datetime import datetime, timedelta
import uuid
import random

db = SessionLocal()

try:
    # Clear old test data
    db.query(AgentEvent).delete()
    db.query(Candidate).delete()
    db.query(Employee).delete()
    db.query(Jobs).delete()
    db.query(Opportunity).delete()
    db.commit()

    print("[REAL DATA SEED] Building realistic business entities...\n")

    # JOBS (10 open requisitions)
    print("[1] Creating 10 Jobs...")
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
            jobDescription=f"Seeking {title} to join BlitzenX",
            jobSkills="Python,SQL,Guidewire",
            jobExperience="5+ years",
            jobLocation="Remote",
            jobStatus="OPEN",
            jobCreatedAt=datetime.utcnow() - timedelta(days=random.randint(5, 30)),
            noOfPositions=random.randint(1, 3),
        )
        db.add(job)
        jobs.append(job)

    db.commit()
    print(f"  [OK] {len(jobs)} jobs created\n")

    # CANDIDATES (59 in various pipeline stages)
    print("[2] Creating 59 Candidates...")
    candidates = []
    names = [
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

    for i, (first, last) in enumerate(names):
        candidate = Candidate(
            candidateID=f"cand_{i+1:03d}",
            candidateEmail=f"{first.lower()}.{last.lower()}@blitzenx.com",
            candidateFirstName=first,
            candidateLastName=last,
            candidateRole="Candidate",
            candidateJobTitle=random.choice(job_titles),
            candidatePassword="hashed_password",
            candidateCreatedAt=datetime.utcnow() - timedelta(days=random.randint(1, 60)),
        )
        db.add(candidate)
        candidates.append(candidate)

    db.commit()
    print(f"  [OK] {len(candidates)} candidates created\n")

    # OPPORTUNITIES (6 active deals)
    print("[3] Creating 6 Opportunities...")
    opportunities = []
    opp_data = [
        ("Acme Insurance", "Guidewire Implementation", 800_000),
        ("GlobalBank", "Policy Admin System", 1_200_000),
        ("SafeInsure", "Claims Processing", 650_000),
        ("MetroLife", "Digital Transformation", 950_000),
        ("PremiumCare", "Underwriting Automation", 750_000),
        ("CityRisk", "Core System Migration", 1_100_000),
    ]

    for i, (account, opp_name, value) in enumerate(opp_data):
        opp = Opportunity(
            opportunityID=f"opp_{i+1:03d}",
            opportunityName=f"{account} - {opp_name}",
            accountName=account,
            estimatedValue=value,
            currency="USD",
            status="ACTIVE",
            createdAt=datetime.utcnow() - timedelta(days=random.randint(10, 90)),
            probability=random.choice([0.25, 0.5, 0.75, 1.0]),
            expectedCloseDate=datetime.utcnow() + timedelta(days=random.randint(30, 180)),
        )
        db.add(opp)
        opportunities.append(opp)

    db.commit()
    total_pipeline = sum(o.estimatedValue or 0 for o in opportunities)
    print(f"  [OK] {len(opportunities)} opportunities created")
    print(f"      - Pipeline value: ${total_pipeline:,}\n")

    # EMPLOYEES (50 active workforce)
    print("[4] Creating 50 Employees...")
    emp_names = [
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

    for i, (first, last) in enumerate(emp_names):
        employee = Employee(
            id=f"emp_{i+1:03d}",
            email=f"{first.lower()}.{last.lower()}@blitzenx.com",
            first_name=first,
            last_name=last,
            status="ACTIVE",
            hire_date=datetime.utcnow() - timedelta(days=random.randint(30, 1000)),
            cost_usd_cents=int(random.uniform(60_000, 200_000) * 100),
            business_unit="AXION",
        )
        db.add(employee)

    db.commit()
    print(f"  [OK] {len(emp_names)} employees created\n")

    # PUBLISH AGENT EVENTS
    print("[5] Publishing Agent Events (inter-agent communication)...")

    # Thunder qualifies candidates
    for cand in random.sample(candidates, 5):
        AgentEventService.publish_event(
            db=db,
            event_type="candidate.qualified",
            source_agent="Thunder",
            entity_id=cand.candidateID,
            entity_type="candidate",
            current_state="CREATED",
            new_state="QUALIFIED",
            payload={"candidate_name": f"{cand.candidateFirstName} {cand.candidateLastName}"},
            confidence=90,
            action_required="Schedule interview",
            owner="Interview Reminder Agent",
        )

    # Candidates interviewed
    for cand in random.sample(candidates, 3):
        AgentEventService.publish_event(
            db=db,
            event_type="candidate.interviewed",
            source_agent="Thunder",
            entity_id=cand.candidateID,
            entity_type="candidate",
            current_state="QUALIFIED",
            new_state="INTERVIEWED",
            payload={"interview_score": random.randint(3, 5)},
            confidence=85,
            action_required="Send offer",
            owner="HR Agent",
        )

    # Offers sent
    for cand in random.sample(candidates, 2):
        AgentEventService.publish_event(
            db=db,
            event_type="candidate.offered",
            source_agent="HR Agent",
            entity_id=cand.candidateID,
            entity_type="candidate",
            current_state="INTERVIEWED",
            new_state="OFFER",
            payload={"salary": random.randint(80_000, 200_000)},
            confidence=90,
            action_required="Send onboarding kit",
            owner="Onboarding Agent",
        )

    db.commit()
    print(f"  [OK] Published agent events for inter-agent communication\n")

    # SUMMARY
    print("\n" + "="*70)
    print("[SUCCESS] REALISTIC BUSINESS DATA SEEDED!")
    print("="*70)
    print(f"""
REAL BUSINESS ENTITIES:
  - 10 Jobs (open requisitions)
  - 59 Candidates (flowing through pipeline)
  - 6 Opportunities (${total_pipeline:,} pipeline value)
  - 50 Employees (actively working)

AGENT COMMUNICATION ACTIVE:
  - Thunder publishes "candidate.qualified" events
  - Interview Reminder Agent CONSUMES & schedules interviews
  - HR Agent CONSUMES "interviewed" & sends offers
  - Onboarding Agent CONSUMES "offered" & begins onboarding
  - Resource Mgmt Agent CONSUMES "hire.completed" & assigns projects
  - KPI Agent WATCHES ALL EVENTS for metrics

AGENTS TALKING TO EACH OTHER:
  1. Thunder qualifies candidate → publishes event
  2. Interview Reminder reads event → schedules interview
  3. HR reads interview result → sends offer
  4. Onboarding reads offer → starts prep
  5. Resource Mgmt reads hire → assigns to project
  6. KPI Agent tracks entire flow → updates metrics
""")

except Exception as e:
    db.rollback()
    print(f"[ERROR] {e}")
    raise
finally:
    db.close()
